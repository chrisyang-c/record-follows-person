"""Security primitives use only a tiny temporary registry, never the shared seeded store."""

from __future__ import annotations

import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest

from core import security
from record import care_circle
from record.store import RecordStore

PASSWORD = "independent-test-password"


@pytest.fixture(autouse=True)
def fresh_runner():
    """Override graph/seed fixtures: this module has no graph or real-record dependency."""


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    store = RecordStore(tmp_path / "records")
    monkeypatch.setattr(security, "get_store", lambda: store)
    monkeypatch.setattr(care_circle, "get_store", lambda: store)
    care_circle.save_identities(
        {
            "nurse_one": {"name": "Synthetic Nurse", "role": "nurse"},
            "P001": {"name": "Synthetic Patient", "role": "patient", "patient_id": "P001"},
        }
    )
    clock = [1_800_000_000.0]
    monkeypatch.setattr(security, "_now", lambda: clock[0])
    return store, clock


def rows(store, table):
    with sqlite3.connect(store.root / "_security.sqlite3") as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(f"SELECT * FROM {table}")]


def test_salted_personal_credentials_and_generic_failure(isolated):
    store, _ = isolated
    security.set_password("nurse_one", PASSWORD)
    security.set_password("P001", PASSWORD)
    credentials = rows(store, "credentials")
    assert all(row["iterations"] == 600_000 for row in credentials)
    assert credentials[0]["salt"] != credentials[1]["salt"]
    assert credentials[0]["password_hash"] != credentials[1]["password_hash"]
    assert "role" not in credentials[0]
    assert PASSWORD.encode() not in (store.root / "_security.sqlite3").read_bytes()
    assert security.authenticate("nurse_one", PASSWORD, "peer-one")["role"] == "nurse"
    assert security.authenticate("nurse_one", "wrong", "peer-one") is None
    assert security.authenticate("unknown", PASSWORD, "peer-one") is None
    assert security.authenticate("nurse_one", "x" * 1025, "peer-one") is None


def test_provision_requires_existing_identity_and_strong_length(isolated):
    with pytest.raises(ValueError):
        security.set_password("missing", PASSWORD)
    with pytest.raises(ValueError):
        security.set_password("nurse_one", "1943")
    with pytest.raises(ValueError):
        security.create_session("nurse_one", "care")


def test_sessions_store_only_hash_and_expire_at_eight_hours(isolated):
    store, clock = isolated
    security.set_password("nurse_one", PASSWORD)
    session = security.create_session("nurse_one", "care", "P001")
    database = (store.root / "_security.sqlite3").read_bytes()
    assert session["token"].encode() not in database
    assert session["csrf_token"].encode() not in database
    stored = rows(store, "sessions")[0]
    assert stored["token_hash"] == hashlib.sha256(session["token"].encode()).hexdigest()
    assert set(stored).isdisjoint({"token", "password", "csrf_token", "role"})
    assert "token" not in security.get_session(session["token"])
    assert security.get_session(session["token"])["csrf_token"] == session["csrf_token"]
    duration = datetime.fromisoformat(session["expires_at"]) - datetime.fromisoformat(
        session["created_at"]
    )
    assert duration.total_seconds() == 8 * 3600
    clock[0] += security.SESSION_SECONDS - 1
    assert security.get_session(session["token"])
    clock[0] += 1
    assert security.get_session(session["token"]) is None


def test_session_nonces_revocation_and_password_reset(isolated):
    security.set_password("nurse_one", PASSWORD)
    first = security.create_session("nurse_one", "care", "P001")
    second = security.create_session("nurse_one", "care", "P001")
    assert first["token"] != second["token"]
    assert first["csrf_token"] != second["csrf_token"]
    security.revoke_session(first["token"])
    security.revoke_session(first["token"])
    assert security.get_session(first["token"]) is None
    assert security.get_session(second["token"])
    security.set_password("nurse_one", "replacement-test-password")
    assert security.get_session(second["token"]) is None
    assert security.authenticate("nurse_one", PASSWORD, "peer") is None
    assert security.authenticate("nurse_one", "replacement-test-password", "peer")
    assert len([e for e in security.audit_entries("P001") if e["action"] == "session.revoked"]) == 1


def test_session_reads_current_identity_not_cached_role(isolated):
    security.set_password("nurse_one", PASSWORD)
    session = security.create_session("nurse_one", "care")
    identities = care_circle.identities()
    identities["nurse_one"] = {"name": "Renamed Synthetic Caregiver", "role": "caregiver"}
    care_circle.save_identities(identities)
    current = security.get_session(session["token"])
    assert current["role"] == "caregiver" and current["name"] == "Renamed Synthetic Caregiver"
    identities.pop("nurse_one")
    care_circle.save_identities(identities)
    assert security.get_session(session["token"]) is None
    assert security.authenticate("nurse_one", PASSWORD, "peer") is None


def test_disabled_identity_and_forged_tokens_fail_closed(isolated):
    security.set_password("nurse_one", PASSWORD)
    session = security.create_session("nurse_one", "care")
    identities = care_circle.identities()
    identities["nurse_one"]["disabled"] = True
    care_circle.save_identities(identities)
    assert security.get_session(session["token"]) is None
    assert security.authenticate("nurse_one", PASSWORD, "peer") is None
    for token in (None, "", "me=nurse_one", "x" * 513, session["csrf_token"]):
        assert security.get_session(token) is None


def test_account_throttle_is_independent_of_peer_and_expires(isolated, monkeypatch):
    _, clock = isolated
    monkeypatch.setattr(security, "ACCOUNT_ATTEMPT_LIMIT", 2)
    security.set_password("nurse_one", PASSWORD)
    assert security.authenticate("nurse_one", "wrong", "peer-one") is None
    assert security.authenticate("nurse_one", "wrong", "peer-two") is None
    with pytest.raises(security.AuthenticationRateLimited) as failure:
        security.authenticate("nurse_one", PASSWORD, "peer-three")
    assert failure.value.retry_after == security.LOGIN_WINDOW_SECONDS
    clock[0] += security.LOGIN_WINDOW_SECONDS
    assert security.authenticate("nurse_one", PASSWORD, "peer-three")


def test_peer_throttle_covers_unknown_accounts(isolated, monkeypatch):
    monkeypatch.setattr(security, "PEER_ATTEMPT_LIMIT", 2)
    security.authenticate("unknown-one", "wrong", "same-peer")
    security.authenticate("unknown-two", "wrong", "same-peer")
    with pytest.raises(security.AuthenticationRateLimited):
        security.authenticate("unknown-three", "wrong", "same-peer")
    assert security.authenticate("unknown-three", "wrong", "other-peer") is None


def test_success_does_not_use_throttle_slots_or_reset_others(isolated, monkeypatch):
    monkeypatch.setattr(security, "PEER_ATTEMPT_LIMIT", 2)
    security.set_password("nurse_one", PASSWORD)
    security.authenticate("unknown-one", "wrong", "peer")
    assert security.authenticate("nurse_one", PASSWORD, "peer")
    assert security.authenticate("nurse_one", PASSWORD, "peer")
    security.authenticate("unknown-two", "wrong", "peer")
    with pytest.raises(security.AuthenticationRateLimited):
        security.authenticate("nurse_one", PASSWORD, "peer")


def test_concurrent_attempts_reserve_slots_atomically(isolated, monkeypatch):
    monkeypatch.setattr(security, "ACCOUNT_ATTEMPT_LIMIT", 2)

    def try_sign_in(number):
        try:
            assert security.authenticate("unknown", "wrong", f"peer-{number}") is None
            return "denied"
        except security.AuthenticationRateLimited:
            return "limited"

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(try_sign_in, range(5)))
    assert results.count("denied") == 2 and results.count("limited") == 3


def test_audit_is_patient_scoped_and_redacts_secrets(isolated):
    security.audit("P001", "nurse_one", "read", outcome="allowed", purpose="care")
    security.audit("P002", "nurse_one", "read", outcome="denied", purpose="research")
    security.audit(
        "P001",
        "nurse_one",
        "update",
        outcome="denied",
        details={
            "password": PASSWORD,
            "nested": [{"csrf_token": "secret-value"}],
            "reason": "scope",
        },
    )
    entries = security.audit_entries("P001")
    assert len(entries) == 2
    assert entries[0]["action"] == "update"
    assert entries[0]["details"] == {
        "password": "[REDACTED]",
        "nested": [{"csrf_token": "[REDACTED]"}],
        "reason": "scope",
    }
    assert len(security.audit_entries("P001", limit=1)) == 1
    assert security.audit_entries("P001", limit=0) == []


def test_session_rejects_empty_purpose(isolated):
    security.set_password("nurse_one", PASSWORD)
    with pytest.raises(ValueError):
        security.create_session("nurse_one", "   ")
