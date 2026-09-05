"""Per-resident conversation store (照服員 ↔ agent 的持續對話串).

records/{patient_id}/conversation.jsonl  — append-only messages (caregiver / agent / system)
records/{patient_id}/conversation_state.json — the open intake session (phase, Path A thread)

Every caregiver turn and every agent reply is a *record line* with provenance
(caregiver_said / ai_extracted / system_derived). It is NOT a timeline entry: CLAUDE.md §1/§4
reserve the timeline for nurse-approved entries (timeline_write asserts approved+confirmed_by),
so the conversation lives beside the timeline and is shown in the timeline tab as「對話」rows;
the approved Observation lands in the timeline when the nurse confirms (see docs/DECISIONS.md).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from record_schema import Provenance

from core.ids import new_id
from core.settings import get_settings
from record.store import get_store

TAIPEI = ZoneInfo("Asia/Taipei")

Role = Literal["caregiver", "agent", "system"]
Kind = Literal["message", "question", "summary", "closing", "event", "error"]


class ConvMessage(BaseModel):
    id: str
    patient_id: str
    session_id: str
    role: Role
    kind: Kind = "message"
    text: str
    ts: str
    meta: dict[str, Any] = Field(
        default_factory=dict
    )  # dimension, reason, red, thread_id, activity…


class SessionState(BaseModel):
    session_id: str
    dialog_id: str
    phase: Literal["intake", "confirm", "red", "closed"] = "intake"
    thread_id: str | None = None  # Path A thread once the nurse was notified
    started: str
    closed: str | None = None
    closed_reason: str | None = None  # "confirmed" | "restart" | "expired" | …
    pending_event_id: str | None = None  # channel 4「可能跌倒」waiting for the four-button answer


def is_expired(s: SessionState, now: datetime | None = None) -> str | None:
    """Why an open session should be closed: older than SESSION_EXPIRY_H hours, or started on
    another Taiwan-local day. None when still valid."""
    now = now or datetime.now(UTC)
    started = datetime.fromisoformat(s.started)
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    hours = get_settings().SESSION_EXPIRY_H
    if now - started > timedelta(hours=hours):
        return f"超過 {hours} 小時"
    if started.astimezone(TAIPEI).date() != now.astimezone(TAIPEI).date():
        return "跨日"
    return None


def _dir(patient_id: str):
    return get_store().dir(patient_id)


def messages(patient_id: str, limit: int | None = None) -> list[ConvMessage]:
    f = _dir(patient_id) / "conversation.jsonl"
    if not f.exists():
        return []
    rows = [
        ConvMessage.model_validate_json(x)
        for x in f.read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    return rows[-limit:] if limit else rows


def append(
    patient_id: str,
    role: Role,
    text: str,
    session_id: str,
    kind: Kind = "message",
    meta: dict[str, Any] | None = None,
    author: str | None = None,
) -> ConvMessage:
    ts = datetime.now(UTC)
    msg = ConvMessage(
        id=new_id("msg", ts),
        patient_id=patient_id,
        session_id=session_id,
        role=role,
        kind=kind,
        text=text,
        ts=ts.isoformat(),
        meta=meta or {},
    )
    d = _dir(patient_id)
    d.mkdir(parents=True, exist_ok=True)
    with (d / "conversation.jsonl").open("a", encoding="utf-8") as f:
        f.write(msg.model_dump_json() + "\n")
    source = {"caregiver": "caregiver_said", "agent": "ai_extracted", "system": "system_derived"}[
        role
    ]
    store = get_store()
    store._append_provenance(  # noqa: SLF001 — conversation lines carry provenance like everything else
        patient_id,
        ref=msg.id,
        field=kind,
        prov=Provenance(source=source, author=author or role, ts=ts, language_original="zh-TW"),  # type: ignore[arg-type]
    )
    for step in (meta or {}).get("activity") or []:
        store._append_provenance(  # noqa: SLF001
            patient_id,
            ref=msg.id,
            field=f"activity:{step.get('name')}",
            prov=Provenance(source="system_derived", author="intake_agent", ts=ts),
        )
    return msg


def session(patient_id: str) -> SessionState | None:
    f = _dir(patient_id) / "conversation_state.json"
    if not f.exists():
        return None
    return SessionState.model_validate_json(f.read_text(encoding="utf-8"))


def save_session(patient_id: str, s: SessionState) -> None:
    d = _dir(patient_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "conversation_state.json").write_text(s.model_dump_json(indent=1), encoding="utf-8")


def open_session(patient_id: str) -> SessionState:
    """The current intake session; a new one starts after the previous was closed — or after it
    expired (SESSION_EXPIRY_H hours / a new Taiwan-local day), in which case the old one is
    closed with ``closed_reason="expired"`` and a system line is appended to the conversation."""
    s = session(patient_id)
    ts = datetime.now(UTC)
    if s and s.phase != "closed":
        why = is_expired(s, ts)
        if why is None:
            return s
        s.phase, s.closed, s.closed_reason = "closed", ts.isoformat(), "expired"
        save_session(patient_id, s)
        append(
            patient_id,
            "system",
            f"上一段對話已自動結束（{why}），這是新的一段。",
            s.session_id,
            kind="event",
            meta={"expired": why},
        )
    s = SessionState(
        session_id=new_id("ses", ts), dialog_id=new_id("dlg", ts), started=ts.isoformat()
    )
    save_session(patient_id, s)
    return s


def close_session(patient_id: str, reason: str = "closed") -> None:
    s = session(patient_id)
    if s:
        s.phase = "closed"
        s.closed = datetime.now(UTC).isoformat()
        s.closed_reason = reason
        save_session(patient_id, s)


def session_turns(patient_id: str, session_id: str) -> list[dict[str, Any]]:
    """Caregiver messages of a session as intake Turns (answer paired with the agent question)."""
    turns: list[dict[str, Any]] = []
    last_q: ConvMessage | None = None
    for m in messages(patient_id):
        if m.session_id != session_id:
            continue
        if m.role == "agent" and m.kind == "question":
            last_q = m
        elif m.role == "caregiver":
            turns.append(
                {
                    "text": m.text,
                    # the bare question (the shown reply may carry the red-flag intro line)
                    "question": (last_q.meta.get("question") or last_q.text) if last_q else None,
                    "dimension": (last_q.meta.get("dimension") if last_q else None),
                    "phase": (last_q.meta.get("phase") if last_q else None),
                    "ts": m.ts,
                }
            )
            last_q = None
    return turns


def system_event(patient_id: str, text: str, meta: dict[str, Any] | None = None) -> ConvMessage:
    s = session(patient_id)
    sid = s.session_id if s else open_session(patient_id).session_id
    return append(patient_id, "system", text, sid, kind="event", meta=meta, author="system")
