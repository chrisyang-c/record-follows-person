"""HTTP authorization boundary. Internal graph/domain calls are not HTTP credentials.

Every route is classified explicitly; new routes fail closed until added here. Patient
authorization precedes snapshots, model calls and filesystem access. UI cookies and role
headers never confer authority. This is local-account security, not a production IdP.
"""

from __future__ import annotations

import json
import re
import secrets
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core import security
from core.settings import get_settings
from graphs import registry
from record import care_circle as cc
from record.store import get_store

actor: ContextVar[dict[str, Any] | None] = ContextVar("http_actor", default=None)
ALL = set(cc.ALL_SCOPES)
PUBLIC = {
    ("GET", "/health"),
    ("GET", "/meta/dimensions"),
    ("GET", "/meta/red-flags"),
    ("POST", "/login"),
}
SAFE = {"GET", "HEAD", "OPTIONS"}
ID = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")


def deny(reason: str, status: int = 403) -> None:
    raise HTTPException(status, {"message": "未獲授權", "reason": reason})


def current() -> dict[str, Any]:
    value = actor.get()
    if value is None:
        deny("authentication_required", 401)
    return value


def effective_scopes(pid: str, identity: dict[str, Any] | None = None) -> list[str]:
    identity = identity or current()
    if not isinstance(pid, str) or not ID.fullmatch(pid):
        return []
    # A changed registry role cannot reuse grants for a previous role.
    out: list[str] = []
    for grant in cc.active_members(pid):
        if (
            grant.member_id == identity["who"]
            and grant.role == identity["role"]
            and identity["purpose"] in grant.allowed_purposes
        ):
            out.extend(s for s in grant.scopes if s not in out)
    return out


def require(pid: str, scopes: set[str] | None = None, roles: set[str] | None = None) -> None:
    it = current()
    if roles and it["role"] not in roles:
        deny("role_not_allowed")
    got = effective_scopes(pid)
    if not got:
        deny("no_active_grant_for_purpose")
    if scopes and not scopes.issubset(got):
        deny("scope_missing")
    if not get_store().exists(pid):
        deny("record_not_authorized")


def is_manager(pid: str, who: str | None = None, purpose: str | None = None) -> bool:
    it = actor.get()
    who = it["who"] if it else who
    purpose = it["purpose"] if it else purpose
    identity = cc.whoami(who)
    if not identity:
        return False
    return any(
        m.member_id == who
        and m.role == identity["role"]
        and m.can_manage
        and (purpose is None or purpose in m.allowed_purposes)
        for m in cc.active_members(pid)
    )


def visible(pid: str, scopes: set[str] = ALL) -> bool:
    """Domain tests may call projection functions directly; HTTP always has an actor."""
    return actor.get() is None or scopes.issubset(effective_scopes(pid))


def visible_patients(scopes: set[str] = ALL) -> list[str]:
    return [pid for pid in get_store().list_patients() if visible(pid, scopes)]


@contextmanager
def _cohort_db():
    db = sqlite3.connect(get_store().root / "_security.sqlite3", timeout=10)
    db.execute(
        "CREATE TABLE IF NOT EXISTS http_round_cohorts "
        "(thread_id TEXT PRIMARY KEY, patients TEXT NOT NULL)"
    )
    try:
        with db:
            yield db
    finally:
        db.close()


def save_cohort(thread_id: str, patients: list[str]) -> None:
    if actor.get() is None:
        return
    with _cohort_db() as db:
        db.execute(
            "INSERT OR IGNORE INTO http_round_cohorts VALUES (?, ?)",
            (thread_id, json.dumps(sorted(patients))),
        )


def thread_patients(thread_id: str) -> list[str]:
    row = registry.get(thread_id)
    if not row:
        deny("thread_not_authorized")
    if row["graph"] == "round":
        with _cohort_db() as db:
            hit = db.execute(
                "SELECT patients FROM http_round_cohorts WHERE thread_id = ?", (thread_id,)
            ).fetchone()
        if not hit:
            deny("round_cohort_not_registered")
        return json.loads(hit[0])
    return [row["patient_id"]]


def thread_visible(thread_id: str) -> bool:
    if actor.get() is None:
        return True
    try:
        return all(visible(pid) for pid in thread_patients(thread_id))
    except HTTPException:
        return False


def project(data: Any, role: str | None = None) -> Any:
    """Response-only projection; never rewrite the stored evidence/provenance."""
    role = role or (actor.get() or {}).get("role", "nurse")
    if role == "nurse":
        return data
    if isinstance(data, list):
        return [project(v, role) for v in data]
    if not isinstance(data, dict):
        return data
    hidden = {
        "confidence",
        "probability",
        "sensor_event",
        "nurse_section",
        "onsite_assessment",
        "red_flags",
        "red_flag_lines",
        "accel_peak_g",
        "orientation_change_deg",
        "still_seconds",
        "hr_before",
        "hr_after",
        "spo2_after",
        "hard_flag",
    }
    result = {k: project(v, role) for k, v in data.items() if k not in hidden}
    if "activity" in result:
        result["activity"] = [public_activity(v) for v in data.get("activity", [])]
    return result


def public_activity(data: dict[str, Any]) -> dict[str, Any]:
    if (actor.get() or {}).get("role", "nurse") == "nurse":
        return data
    return {k: data[k] for k in ("type", "name", "plain", "ms") if k in data}


def document_visible(doc_type: str, role: str | None = None) -> bool:
    role = role or (actor.get() or {}).get("role", "nurse")
    if role in ("family", "caregiver"):
        return doc_type == "caregiver_notes"
    if role in {"doctor", "patient"}:
        return doc_type in {"round_page", "caregiver_notes"}
    return True


def check_actor_fields(body: Any, patients: list[str]) -> None:
    if not isinstance(body, dict):
        return
    it = current()
    for key in ("caregiver_id", "nurse_id", "head_nurse", "granted_by"):
        if body.get(key) and body[key] != it["who"]:
            deny("actor_mismatch")
    if body.get("role_view") and body["role_view"] != (
        "caregiver" if it["role"] == "family" else it["role"]
    ):
        deny("role_mismatch")

    # These fields can cause cross-patient writes during graph resume.
    def check(value: Any) -> None:
        if isinstance(value, dict):
            for key, val in value.items():
                if key == "patient_id" and val not in patients:
                    deny("patient_outside_cohort")
                if key == "patient_ids" and (
                    not isinstance(val, list) or any(p not in patients for p in val)
                ):
                    deny("patient_outside_cohort")
                check(val)
        elif isinstance(value, list):
            for val in value:
                check(val)

    check(body)


def route_policy(request: Request, body: Any) -> list[str]:
    path, method = request.url.path, request.method
    it = current()
    if path in {"/auth/session", "/whoami"} and method == "GET":
        return []
    if path == "/auth/logout" and method == "POST":
        return []
    if path == "/residents" and method == "GET":
        return visible_patients({"who"})
    if path.startswith("/home/") and method == "GET":
        if path.rsplit("/", 1)[-1] != ("caregiver" if it["role"] == "family" else it["role"]):
            deny("role_mismatch")
        return visible_patients({"who", "timeline", "docs"} if it["role"] == "doctor" else ALL)
    if path in {"/nurse/inbox", "/threads", "/trace"} and method == "GET":
        if it["role"] != "nurse":
            deny("role_not_allowed")
        return visible_patients()
    if path in {"/round/start", "/round/start/stream"} and method == "POST":
        patients = get_store().list_patients()
        if not patients:
            deny("empty_cohort")
        for pid in patients:
            require(pid, ALL, {"nurse"})
        return patients
    match = re.fullmatch(r"/threads/(.+)/(state|resume|caregiver-report)", path)
    if match or path.startswith("/debug/trace/"):
        tid = match[1] if match else path.removeprefix("/debug/trace/")
        operation = match[2] if match else "trace"
        if method != ("POST" if operation in {"resume", "caregiver-report"} else "GET"):
            deny("method_not_allowed")
        patients = thread_patients(tid)
        for pid in patients:
            require(
                pid,
                ALL,
                {"nurse"} if operation != "caregiver-report" else {"caregiver", "family", "nurse"},
            )
        if operation == "resume" and registry.get(tid)["graph"] == "round":
            if isinstance(body, dict) and isinstance(body.get("edits"), dict):
                if not set(body["edits"]).issubset(patients):
                    deny("patient_outside_cohort")
        check_actor_fields(body, patients)
        return patients
    if (
        path in {"/path-a/start", "/shift/start", "/intake/preview", "/intake/turn"}
        and method == "POST"
    ):
        pid = body.get("patient_id") if isinstance(body, dict) else None
        require(
            pid,
            ALL,
            {"nurse", "caregiver", "family"}
            if path in {"/shift/start", "/path-a/start"}
            else {"nurse"},
        )
        check_actor_fields(body, [pid])
        return [pid]
    if path == "/ingest/order/preview" and method == "POST":
        if it["role"] != "nurse":
            deny("role_not_allowed")
        return []
    if path.startswith("/sim/fall/") and method == "POST":
        if not get_settings().ENABLE_DEMO_SIMULATION or it["role"] != "nurse":
            deny("simulation_disabled_or_forbidden")
        hid = path.rsplit("/", 1)[-1]
        for pid in visible_patients():
            if get_store().load_profile(pid).health_id == hid:
                return [pid]
        deny("record_not_authorized")
    match = re.fullmatch(
        r"/(patients|records|me|twin|round-pages|caregiver-notes|trends|ingest/vitals|ingest/discharge|ingest/fhir)/([^/]+)(.*)",
        path,
    )
    if not match:
        deny("route_not_allowed")  # includes worker/scan and unclassified routes
    group, pid, suffix = match.groups()
    scopes, roles = ALL, None
    if group == "patients":
        table = {
            ("GET", "/summary"): set(),
            ("GET", "/care-circle"): {"who"},
            ("POST", "/care-circle"): {"who"},
            ("GET", "/access-log"): {"who"},
            ("GET", "/conversation"): {"talk"},
            ("POST", "/talk"): ALL,
            ("GET", "/vitals-bands"): {"who", "timeline"},
        }
        if suffix.startswith("/care-circle/") and suffix.endswith("/revoke") and method == "POST":
            scopes = {"who"}
        elif re.fullmatch(r"/events/[^/]+/verify", suffix) and method == "POST":
            scopes, roles = ALL, {"patient", "family", "caregiver", "nurse"}
        elif (method, suffix) in table:
            scopes = table[(method, suffix)]
        else:
            deny("route_not_allowed")
        if suffix == "/summary":
            tab = request.query_params.get("tab")
            if tab:
                if tab not in ALL:
                    deny("invalid_scope")
                scopes = {tab}
        if suffix == "/vitals-bands":
            roles = {"nurse"}
        if suffix == "/talk":
            roles = {"patient", "family", "caregiver", "nurse"}
    elif group == "records" and method == "GET":
        if suffix in {"", "/provenance"}:
            roles = {"nurse"}
        elif suffix == "/timeline":
            scopes = {"timeline"}
        elif suffix == "/documents" or re.fullmatch(r"/documents/[A-Za-z0-9_-]+", suffix):
            scopes = {"docs"}
        elif suffix == "/follow-ups":
            scopes, roles = {"timeline"}, {"nurse"}
        elif re.fullmatch(r"/follow-ups/[A-Za-z0-9_-]+/ack", suffix) and method == "POST":
            scopes, roles = {"timeline"}, {"nurse"}
        else:
            deny("route_not_allowed")
    elif group == "me":
        if (method, suffix) == ("GET", "/timeline"):
            scopes = {"timeline"}
        elif (method, suffix) == ("POST", "/ask"):
            scopes = ALL  # current agent reads profile/baseline as well as T+D
        elif (method, suffix) != ("GET", "/home"):
            deny("route_not_allowed")
    elif method == "GET" and not suffix:
        if group in {"round-pages", "caregiver-notes"}:
            scopes = {"docs"}
            if group == "round-pages":
                roles = {"nurse", "doctor", "patient"}
        elif group in {"trends", "ingest/vitals", "ingest/discharge"}:
            scopes = {"who", "docs" if group == "ingest/discharge" else "timeline"}
            roles = {"nurse"}
        elif group == "ingest/fhir" and method in {"GET", "POST"} and not suffix:
            scopes = {"who"}
            roles = {"nurse"}
        elif group != "twin":
            deny("route_not_allowed")
    else:
        deny("route_not_allowed")
    require(pid, scopes, roles)
    if group == "patients" and (suffix.startswith("/care-circle") or suffix == "/access-log"):
        if not is_manager(pid):
            deny("patient_management_required")
    check_actor_fields(body, [pid])
    return [pid]


class PolicyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS":
            return await call_next(request)
        request_id = uuid4().hex
        it = None
        patients: list[str] = []
        context_token = None
        peer = request.client.host if request.client else "unknown"
        try:
            if request.method not in SAFE:
                origin = request.headers.get("origin")
                allowed = {x.strip() for x in get_settings().AUTH_ALLOWED_ORIGINS.split(",")}
                if origin and origin not in allowed:
                    deny("origin_not_allowed")
            if (request.method, path) in PUBLIC:
                response = await call_next(request)
                response.headers["Cache-Control"] = "no-store"
                return response
            it = security.get_session(request.cookies.get("rfp_session", ""))
            if not it:
                deny("authentication_required", 401)
            it = {**it, "purpose": request.headers.get("X-Purpose", it["purpose"])}
            if it["purpose"] not in cc.PURPOSES:
                deny("invalid_purpose")
            context_token = actor.set(it)
            if request.method not in SAFE and not secrets.compare_digest(
                request.headers.get("X-CSRF-Token", "").encode(), it["csrf_token"].encode()
            ):
                deny("csrf_failed")
            for name, key in (("x-who", "who"), ("x-role", "role")):
                if request.headers.get(name) and request.headers[name] != it[key]:
                    deny("actor_mismatch")
            body = None
            if request.method not in SAFE:
                if "application/json" not in request.headers.get("content-type", ""):
                    if path != "/auth/logout":
                        deny("json_required", 415)
                raw = await request.body()
                try:
                    body = json.loads(raw) if raw else {}
                except (ValueError, UnicodeDecodeError):
                    deny("invalid_json", 400)
            patients = route_policy(request, body)
            # Replace rather than trust legacy header parameters in existing handlers.
            request.scope["headers"] = [
                (k, v)
                for k, v in request.scope["headers"]
                if k.lower() not in {b"x-who", b"x-role"}
            ]
            request.scope["headers"].extend(
                [(b"x-who", it["who"].encode()), (b"x-role", it["role"].encode())]
            )
            for pid in patients or [None]:
                grants = (
                    [
                        g.grant_id
                        for g in cc.active_members(pid)
                        if g.member_id == it["who"] and it["purpose"] in g.allowed_purposes
                    ]
                    if pid
                    else []
                )
                security.audit(
                    pid,
                    it["who"],
                    f"{request.method} {path}",
                    outcome="allowed",
                    purpose=it["purpose"],
                    resource=path,
                    peer=peer,
                    details={
                        "request_id": request_id,
                        "reason": "policy_allowed",
                        "grant_ids": grants,
                    },
                )
            response = await call_next(request)
            if response.status_code >= 400:
                for pid in patients or [None]:
                    security.audit(
                        pid,
                        it["who"],
                        f"{request.method} {path}",
                        outcome="denied" if response.status_code == 403 else "failed",
                        purpose=it["purpose"],
                        resource=path,
                        details={
                            "request_id": request_id,
                            "reason": "handler_rejected",
                            "status": response.status_code,
                        },
                    )
            # Uniform response projection also closes raw timeline/document JSON routes.
            if (
                "application/json" in response.headers.get("content-type", "")
                and it["role"] != "nurse"
                and path not in {"/auth/session", "/auth/logout", "/whoami"}
            ):
                content = b"".join([part async for part in response.body_iterator])
                headers = {
                    k: v
                    for k, v in response.headers.items()
                    if k not in {"content-length", "content-type"}
                }
                response = JSONResponse(
                    project(json.loads(content)), status_code=response.status_code, headers=headers
                )
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Request-ID"] = request_id
            return response
        except HTTPException as exc:
            # Do not include request bodies, passwords, cookies or untrusted query strings.
            match = re.match(r"/(?:patients|records|me|twin)/([A-Za-z0-9_-]+)(?:/|$)", path)
            denied_pid = match[1] if match else (patients[0] if patients else None)
            security.audit(
                denied_pid,
                it["who"] if it else None,
                f"{request.method} {path}",
                outcome="denied",
                purpose=it.get("purpose") if it else None,
                details={
                    "request_id": request_id,
                    "reason": exc.detail.get("reason")
                    if isinstance(exc.detail, dict)
                    else exc.detail,
                },
            )
            return JSONResponse(
                {"detail": exc.detail},
                status_code=exc.status_code,
                headers={"Cache-Control": "no-store", "X-Request-ID": request_id},
            )
        finally:
            if context_token is not None:
                actor.reset(context_token)
