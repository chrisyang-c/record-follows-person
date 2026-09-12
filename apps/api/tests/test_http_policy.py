"""Exercise the HTTP boundary with real sessions and isolated synthetic records.

No handler, authentication, or consent decision is mocked. The suite deliberately does not
enter TestClient's lifespan: the background scheduler is unrelated to HTTP authorization.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

ALL_SCOPES = ["who", "timeline", "docs", "talk"]
NURSE = "nurse_lin"
PASSWORD_TEMPLATE = "demo-{}-2026!"


@pytest.fixture(scope="module")
def seed_template(tmp_path_factory):
    return tmp_path_factory.mktemp("http-policy-template") / "records"


@pytest.fixture
def records_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seed_template: Path):
    """Override the inherited shared seed so revoke/purpose tests cannot affect each other."""
    from core.settings import get_settings
    from core.trace import clear_for_tests
    from graphs import runner
    from graphs.checkpointer import get_checkpointer
    from record.store import get_store

    root = tmp_path / "records"
    for name, value in {
        "RECORDS_ROOT": str(root),
        "MODEL_PROVIDER": "mock",
        "DATABASE_URL": "",
        "OPENAI_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
        "LINE_CHANNEL_TOKEN": "",
        "LINE_FAMILY_TO": "",
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    get_store.cache_clear()
    get_checkpointer.cache_clear()
    runner.reset_for_tests()
    clear_for_tests()

    import seed

    if seed_template.exists():
        shutil.copytree(seed_template, root)
    else:
        seed.seed(root, quiet=True, end_date=datetime.now(UTC).date() - timedelta(days=1))
        shutil.copytree(root, seed_template)
    yield root

    runner.reset_for_tests()
    get_checkpointer.cache_clear()
    get_store.cache_clear()
    get_settings.cache_clear()
    clear_for_tests()


@pytest.fixture
def client(records_root: Path):
    from main import app

    http = TestClient(app)
    yield http
    http.close()


def login(
    client: TestClient,
    who: str = NURSE,
    *,
    patient_id: str = "P001",
    purpose: str = "treatment",
) -> dict[str, str]:
    response = client.post(
        "/login",
        json={
            "who": who,
            "password": PASSWORD_TEMPLATE.format(who),
            "patient_id": patient_id,
            "purpose": purpose,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["who"] == who
    assert body["purpose"] == purpose
    assert body["csrf_token"] and body["expires_at"]
    assert client.cookies.get("rfp_session")
    assert client.cookies.get("rfp_csrf")
    assert "password" not in body
    return {"X-CSRF-Token": body["csrf_token"]}


def replace_grant(
    patient_id: str = "P001",
    who: str = NURSE,
    *,
    scopes: list[str] | None = None,
    purposes: list[str] | None = None,
    can_manage: bool = False,
):
    from record import care_circle as cc

    member = next(m for m in cc.active_members(patient_id) if m.member_id == who)
    member = member.model_copy(
        update={
            "scopes": ALL_SCOPES if scopes is None else scopes,
            "allowed_purposes": ["treatment"] if purposes is None else purposes,
            "can_manage": can_manage,
        }
    )
    cc.grant(patient_id, member)
    return member


def assert_no_sensitive_fields(value: Any) -> None:
    forbidden = {
        "confidence",
        "accel_peak_g",
        "orientation_change_deg",
        "still_seconds",
        "hr_before",
        "hr_after",
        "spo2_after",
    }
    if isinstance(value, dict):
        assert not forbidden.intersection(value), value
        for child in value.values():
            assert_no_sensitive_fields(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_sensitive_fields(child)


def test_public_health_does_not_enumerate_patients(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert "records" not in response.json()
    assert all(pid not in response.text for pid in ("P001", "P002", "P003"))


@pytest.mark.parametrize(
    "forged_headers",
    [{}, {"X-Who": NURSE}, {"X-Who": NURSE, "X-Role": "nurse"}],
)
def test_anonymous_and_forged_headers_cannot_read_protected_routes(
    client: TestClient, forged_headers: dict[str, str]
):
    client.cookies.set("me", NURSE)
    paths = [
        "/residents",
        "/home/nurse",
        "/whoami?me=nurse_lin",
        "/twin/P001",
        "/me/P001/home",
        "/me/P001/timeline",
        "/patients/P001/vitals-bands",
        "/records/P001",
        "/records/P001/timeline",
        "/records/P001/documents",
        "/records/P001/documents/unknown",
        "/records/P001/provenance",
        "/round-pages/P001",
        "/caregiver-notes/P001",
        "/patients/P001/summary",
        "/patients/P001/care-circle",
        "/patients/P001/access-log",
        "/patients/P001/conversation",
        "/trends/P001",
        "/threads",
        "/threads/P001:shift:2099-01-01/state",
        "/debug/trace/P001:shift:2099-01-01",
        "/trace",
        "/nurse/inbox",
        "/ingest/vitals/P001",
        "/ingest/discharge/P001",
    ]
    for path in paths:
        response = client.get(path, headers=forged_headers)
        assert response.status_code == 401, (path, response.status_code, response.text)


def test_anonymous_cannot_start_or_mutate_workflows(client: TestClient):
    requests = [
        ("/sim/fall/P-0000001", {}),
        ("/patients/P001/talk", {"text": "今天吃半碗"}),
        ("/patients/P001/events/unknown/verify", {"choice": "fine"}),
        ("/intake/preview", {"patient_id": "P001", "text": "今天吃半碗"}),
        ("/intake/turn", {"patient_id": "P001", "turns": [{"text": "今天吃半碗"}]}),
        ("/path-a/start", {"patient_id": "P001", "text": "今天吃半碗"}),
        ("/shift/start", {"patient_id": "P001", "text": "今天吃半碗"}),
        ("/round/start", {}),
        ("/round/start/stream", {}),
        ("/threads/P001:shift:2099-01-01/resume", {"action": "accept", "nurse_id": NURSE}),
        ("/threads/P001:shift:2099-01-01/caregiver-report", {"turns": []}),
        ("/patients/P001/care-circle/nurse_huang/revoke", {}),
        ("/me/P001/ask", {"question": "最近吃得如何？"}),
        ("/ingest/order/preview", {"text": "每日量體重"}),
    ]
    for path, body in requests:
        response = client.post(path, json=body, headers={"X-Who": NURSE, "X-Role": "nurse"})
        assert response.status_code == 401, (path, response.status_code, response.text)


def test_invalid_password_does_not_create_a_session(client: TestClient):
    response = client.post(
        "/login", json={"who": NURSE, "password": "wrong-password", "purpose": "treatment"}
    )
    assert response.status_code == 401
    assert not client.cookies.get("rfp_session")


def test_patient_code_is_not_an_actor_credential(client: TestClient):
    response = client.post("/login", json={"who": NURSE, "patient_id": "P001", "code": "1940"})
    assert response.status_code in (401, 422)
    assert not client.cookies.get("rfp_session")


def test_session_actor_cannot_be_replaced_by_identity_headers(client: TestClient):
    login(client, "P001", purpose="self-care")
    response = client.get(
        "/records/P002", headers={"X-Who": NURSE, "X-Role": "nurse", "X-Purpose": "treatment"}
    )
    assert response.status_code == 403
    response = client.get("/whoami?me=nurse_lin", headers={"X-Who": NURSE})
    assert response.status_code == 403
    response = client.get("/whoami")
    assert response.status_code == 200 and response.json()["who"] == "P001"


def test_write_requires_the_session_csrf_token(client: TestClient):
    from record import care_circle as cc

    valid_headers = login(client, "P001", purpose="self-care")
    assert cc.scopes_for("P001", "nurse_huang")
    path = "/patients/P001/care-circle/nurse_huang/revoke"
    for headers in ({}, {"X-CSRF-Token": "not-the-session-token"}):
        response = client.post(path, json={}, headers=headers)
        assert response.status_code == 403
        assert cc.scopes_for("P001", "nurse_huang")
    response = client.post(path, json={}, headers=valid_headers)
    assert response.status_code == 200, response.text
    assert not cc.scopes_for("P001", "nurse_huang")


def test_foreign_origin_cannot_mutate_even_with_csrf_token(client: TestClient):
    from record import care_circle as cc

    headers = login(client, "P001", purpose="self-care")
    headers["Origin"] = "https://untrusted.invalid"
    response = client.post(
        "/patients/P001/care-circle/nurse_huang/revoke", json={}, headers=headers
    )
    assert response.status_code == 403
    assert cc.scopes_for("P001", "nurse_huang")


def test_patient_cannot_manage_someone_elses_circle(client: TestClient):
    from record import care_circle as cc

    headers = login(client, "P001", purpose="self-care")
    before = [m.model_dump(mode="json") for m in cc.members("P002")]
    response = client.post(
        "/patients/P002/care-circle",
        headers=headers,
        json={
            "member_id": "P001",
            "role": "patient",
            "scopes": ALL_SCOPES,
            "granted_by": "P001",
            "purpose": "越權測試",
            "allowed_purposes": ["self-care"],
            "can_manage": True,
        },
    )
    assert response.status_code == 403
    response = client.post(
        "/patients/P002/care-circle/nurse_huang/revoke", json={}, headers=headers
    )
    assert response.status_code == 403
    assert [m.model_dump(mode="json") for m in cc.members("P002")] == before


def test_family_requires_explicit_management_permission(client: TestClient):
    replace_grant(who="fam_P001", purposes=["caregiving"], can_manage=False)
    headers = login(client, "fam_P001", purpose="caregiving")
    response = client.post(
        "/patients/P001/care-circle/nurse_huang/revoke", json={}, headers=headers
    )
    assert response.status_code == 403


def test_summary_serializes_only_the_granted_data(client: TestClient):
    from record import conversation as conv

    replace_grant(scopes=["who"])
    conv.append("P001", "caregiver", "PRIVATE-CONVERSATION-MARKER", "policy-test")
    login(client)
    response = client.get("/patients/P001/summary?tab=who")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["allowed_tabs"] == ["who"]
    assert body["profile"]["patient_id"] == "P001"
    for key in (
        "timeline",
        "documents",
        "conversation",
        "session",
        "pending",
        "sensor_events",
        "changed_dimensions",
        "trend_lines",
        "notes_count",
        "recorded_today",
    ):
        assert not body.get(key), (key, body.get(key))
    assert "PRIVATE-CONVERSATION-MARKER" not in response.text
    for tab in ("timeline", "docs", "talk"):
        assert client.get(f"/patients/P001/summary?tab={tab}").status_code == 403


def test_scope_checked_on_legacy_and_aggregate_routes(client: TestClient):
    replace_grant(scopes=["who"])
    headers = login(client)
    for path in (
        "/records/P001",
        "/records/P001/timeline",
        "/records/P001/documents",
        "/patients/P001/conversation",
        "/patients/P001/vitals-bands",
        "/twin/P001",
        "/me/P001/timeline",
    ):
        response = client.get(path)
        assert response.status_code == 403, (path, response.status_code, response.text)
    response = client.post("/me/P001/ask", json={"question": "最近如何？"}, headers=headers)
    assert response.status_code == 403


def test_ask_requires_document_scope_as_well_as_timeline(client: TestClient):
    replace_grant(scopes=["who", "timeline"])
    headers = login(client)
    response = client.post("/me/P001/ask", json={"question": "最近如何？"}, headers=headers)
    assert response.status_code == 403


def test_request_purpose_must_match_current_grant(client: TestClient):
    replace_grant(purposes=["treatment"])
    login(client)
    assert client.get("/patients/P001/summary?tab=who").status_code == 200
    response = client.get("/patients/P001/summary?tab=who", headers={"X-Purpose": "caregiving"})
    assert response.status_code == 403
    response = client.get("/patients/P001/summary?tab=who", headers={"X-Purpose": "marketing"})
    assert response.status_code == 403


def test_legacy_empty_allowed_purposes_is_not_implicitly_authorized(client: TestClient):
    from record import care_circle as cc

    login(client)
    members = cc.members("P001")
    for member in members:
        if member.member_id == NURSE:
            member.allowed_purposes = []
    # Reproduce persisted legacy data, bypassing the validation on *new* grants only.
    cc._save("P001", members)
    response = client.get("/patients/P001/summary?tab=who")
    assert response.status_code == 403


def test_revocation_invalidates_access_without_logging_out(client: TestClient):
    from record import care_circle as cc

    login(client)
    assert client.get("/patients/P001/summary?tab=who").status_code == 200
    cc.revoke("P001", NURSE, by="P001")
    assert client.get("/patients/P001/summary?tab=who").status_code == 403
    # Authenticating the actor again must not silently regrant patient consent.
    response = client.post(
        "/login",
        json={"who": NURSE, "password": PASSWORD_TEMPLATE.format(NURSE), "patient_id": "P001"},
    )
    assert response.status_code == 403
    assert not cc.scopes_for("P001", NURSE)
    assert client.get("/patients/P001/summary?tab=who").status_code == 403


def test_expired_grant_is_rechecked_on_an_existing_session(client: TestClient):
    from record import care_circle as cc

    login(client)
    members = cc.members("P001")
    now = datetime.now(UTC)
    for member in members:
        if member.member_id == NURSE:
            member.valid_from = now - timedelta(days=2)
            member.valid_to = now - timedelta(seconds=1)
    cc._save("P001", members)
    assert client.get("/patients/P001/summary?tab=who").status_code == 403


@pytest.mark.parametrize("path", ["/round/start", "/round/start/stream"])
def test_round_requires_access_to_the_whole_cohort(client: TestClient, path: str):
    from graphs import registry
    from record import care_circle as cc

    headers = login(client)
    cc.revoke("P003", NURSE, by="P003")
    before = registry.list_threads()
    response = client.post(path, json={}, headers=headers)
    assert response.status_code == 403
    assert registry.list_threads() == before


def test_unknown_thread_is_denied_without_creating_registry_state(client: TestClient):
    from graphs import registry

    login(client)
    thread = "P001:shift:2099-01-01"
    assert registry.get(thread) is None
    for path in (f"/threads/{thread}/state", f"/debug/trace/{thread}"):
        response = client.get(path)
        assert response.status_code == 403, (path, response.status_code, response.text)
        assert registry.get(thread) is None


def test_foreign_thread_is_denied_before_snapshot(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from graphs import registry, runner
    from record import care_circle as cc

    headers = login(client)
    cc.revoke("P002", NURSE, by="P002")
    thread = "P002:shift:2099-01-01"
    registry.upsert(thread, graph="shift", patient_id="P002", status="interrupted")

    def forbidden_snapshot(*args, **kwargs):
        pytest.fail("Unauthorized requests reached snapshot(), which writes the registry")

    monkeypatch.setattr(runner, "snapshot", forbidden_snapshot)
    for path in (f"/threads/{thread}/state", f"/debug/trace/{thread}"):
        assert client.get(path).status_code == 403
    response = client.post(
        f"/threads/{thread}/resume", json={"action": "accept", "nurse_id": NURSE}, headers=headers
    )
    assert response.status_code == 403


@pytest.mark.parametrize("field", ["nurse_id", "head_nurse"])
def test_workflow_actor_cannot_be_supplied_by_body(client: TestClient, field: str):
    from graphs import registry

    headers = login(client)
    thread = "P001:shift:2099-01-01"
    registry.upsert(thread, graph="shift", patient_id="P001", status="interrupted")
    response = client.post(
        f"/threads/{thread}/resume",
        json={"action": "accept", field: "nurse_huang"},
        headers=headers,
    )
    assert response.status_code == 403


def test_caregiver_cannot_forge_the_report_author_or_nurse_view(client: TestClient):
    headers = login(client, "cg_xiaofang", purpose="caregiving")
    response = client.post(
        "/shift/start",
        json={"patient_id": "P001", "text": "今天吃半碗", "caregiver_id": NURSE},
        headers=headers,
    )
    assert response.status_code == 403
    response = client.post(
        "/patients/P001/talk", json={"text": "今天吃半碗", "role_view": "nurse"}, headers=headers
    )
    assert response.status_code == 403


def test_grant_actor_cannot_be_forged_in_body(client: TestClient):
    headers = login(client, "P001", purpose="self-care")
    response = client.post(
        "/patients/P001/care-circle",
        headers=headers,
        json={
            "member_id": "nurse_huang",
            "role": "nurse",
            "scopes": ["who"],
            "granted_by": "P002",
            "purpose": "護理查閱",
            "allowed_purposes": ["treatment"],
        },
    )
    assert response.status_code == 403


def test_patient_cannot_access_nurse_or_operations_routes(client: TestClient):
    headers = login(client, "P001", purpose="self-care")
    for path in (
        "/records/P001",
        "/patients/P001/vitals-bands",
        "/nurse/inbox",
        "/trace",
        "/ingest/vitals/P001",
        "/home/nurse",
    ):
        response = client.get(path)
        assert response.status_code == 403, (path, response.status_code, response.text)
    assert client.post("/worker/scan", json={}, headers=headers).status_code == 403
    assert client.post("/worker/scan", json={}, headers=login(client)).status_code == 403


def test_trace_excludes_foreign_and_unattributed_entries(client: TestClient):
    from core.trace import trace
    from record import care_circle as cc

    login(client)
    cc.revoke("P002", NURSE, by="P002")
    trace("policy_test", patient_id="P001", output="VISIBLE-P001")
    trace("policy_test", patient_id="P002", output="PRIVATE-P002")
    trace("policy_test", run_id="unknown-run", output="PRIVATE-UNKNOWN-RUN")
    response = client.get("/trace?kind=policy_test")
    assert response.status_code == 200, response.text
    assert "VISIBLE-P001" in response.text
    assert "PRIVATE-P002" not in response.text
    assert "PRIVATE-UNKNOWN-RUN" not in response.text
    # A substring query must never turn an otherwise denied trace into an allowed one.
    response = client.get("/trace?contains=PRIVATE")
    assert response.status_code == 200
    assert "PRIVATE-P002" not in response.text and "PRIVATE-UNKNOWN-RUN" not in response.text


def test_clinical_projection_removes_raw_values_from_non_nurse_json(client: TestClient):
    from ingest.vitals import simulate_fall
    from record import events

    events.create("P001", simulate_fall("P001", "P-0000001"))
    login(client, "cg_xiaofang", purpose="caregiving")
    response = client.get("/patients/P001/summary")
    assert response.status_code == 200, response.text
    assert response.json()["timeline"]
    assert_no_sensitive_fields(response.json())
    response = client.get("/records/P001/timeline")
    assert response.status_code == 200, response.text
    assert response.json()
    assert_no_sensitive_fields(response.json())


def test_logout_revokes_and_clears_both_cookies(client: TestClient):
    headers = login(client)
    token = client.cookies.get("rfp_session")
    assert client.post("/auth/logout", json={}, headers=headers).status_code == 200
    assert not client.cookies.get("rfp_session") and not client.cookies.get("rfp_csrf")
    client.cookies.set("rfp_session", token)
    assert client.get("/records/P001").status_code == 401


def test_login_validation_does_not_echo_password(client: TestClient):
    password = "never-echo-this-secret" * 60
    response = client.post("/login", json={"who": NURSE, "password": password})
    assert response.status_code == 422
    assert "never-echo-this-secret" not in response.text
    assert "input" not in response.json()["detail"][0]


def test_denied_purpose_is_visible_in_patient_audit(client: TestClient):
    login(client)
    denied = client.get("/records/P001", headers={"X-Purpose": "caregiving"})
    assert denied.status_code == 403
    request_id = denied.headers["X-Request-ID"]
    login(client, "P001", purpose="self-care")
    audit = client.get("/patients/P001/access-log").json()["items"]
    entry = next(e for e in audit if e.get("request_id") == request_id)
    assert entry["outcome"] == "denied" and entry["purpose"] == "caregiving"
    assert entry["reason"] == "no_active_grant_for_purpose"


def test_reissued_grants_preserve_history_and_distinct_versions(client: TestClient):
    from record import care_circle as cc

    previous = next(m for m in cc.active_members("P001") if m.member_id == NURSE)
    replacement = replace_grant(scopes=["who"])
    assert previous.grant_id != replacement.grant_id
    old = next(m for m in cc.members("P001") if m.grant_id == previous.grant_id)
    assert old.revoked_at is not None


def test_round_resume_cannot_inject_a_patient_or_reuse_revoked_cohort(
    client: TestClient, monkeypatch
):
    from graphs import registry, runner
    from record import care_circle as cc

    headers = login(client)
    tid = "ALL:round:2099-01-01"

    def start(*args, **kwargs):
        registry.upsert(tid, graph="round", patient_id="ALL", status="interrupted")
        return {"thread_id": tid, "graph": "round", "status": "interrupted"}

    monkeypatch.setattr(runner, "start", start)
    assert client.post("/round/start", json={}, headers=headers).status_code == 200
    monkeypatch.setattr(runner, "resume", lambda *args: pytest.fail("Unauthorized resume executed"))
    response = client.post(
        f"/threads/{tid}/resume",
        json={"orders": [{"patient_id": "P999", "text": "synthetic"}]},
        headers=headers,
    )
    assert response.status_code == 403
    cc.revoke("P003", NURSE, by="P003")
    assert (
        client.post(
            f"/threads/{tid}/resume", json={"patient_ids": ["P001"]}, headers=headers
        ).status_code
        == 403
    )
