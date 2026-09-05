"""Sensor events (channel 4) — records/{patient_id}/sensor_events.jsonl.

The event layer turns a raw wearable signal into a「可能跌倒」event with status pending →
verified (caregiver's four-button answer) → closed. Not a timeline entry: the timeline only
receives the nurse-approved Incident/IncidentFile that the Path A graph writes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from record_schema import SensorEvent, SensorVerification

from record.store import get_store


def _file(patient_id: str):
    return get_store().dir(patient_id) / "sensor_events.jsonl"


def list_events(patient_id: str, status: str | None = None) -> list[SensorEvent]:
    f = _file(patient_id)
    if not f.exists():
        return []
    rows = [
        SensorEvent.model_validate_json(x)
        for x in f.read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    return [e for e in rows if status is None or e.status == status]


def get(patient_id: str, event_id: str) -> SensorEvent | None:
    return next((e for e in list_events(patient_id) if e.id == event_id), None)


def _save_all(patient_id: str, rows: list[SensorEvent]) -> None:
    f = _file(patient_id)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("".join(e.model_dump_json() + "\n" for e in rows), encoding="utf-8")


def create(patient_id: str, event: SensorEvent) -> SensorEvent:
    rows = list_events(patient_id)
    rows.append(event)
    _save_all(patient_id, rows)
    return event


def update(patient_id: str, event: SensorEvent) -> SensorEvent:
    rows = [event if e.id == event.id else e for e in list_events(patient_id)]
    _save_all(patient_id, rows)
    return event


def pending(patient_id: str) -> SensorEvent | None:
    rows = list_events(patient_id, status="pending")
    return rows[-1] if rows else None


def verify(patient_id: str, event_id: str, choice: str, text: str, by: str) -> SensorEvent:
    ev = get(patient_id, event_id)
    if ev is None:
        raise KeyError(event_id)
    ev.verification = SensorVerification(choice=choice, text=text, by=by, ts=datetime.now(UTC))  # type: ignore[arg-type]
    ev.status = "verified"
    return update(patient_id, ev)


def nurse_view(e: SensorEvent) -> dict[str, Any]:
    """Nurse-only: the raw values."""
    return e.model_dump(mode="json")


def public_view(e: SensorEvent) -> dict[str, Any]:
    """Caregiver / doctor / patient: what happened and what was verified — no raw values, no
    confidence, no percentages (CLAUDE.md §1)."""
    return {
        "id": e.id,
        "ts": e.ts.isoformat(),
        "kind": e.kind,
        "location": e.location,
        "status": e.status,
        "verification": e.verification.model_dump(mode="json") if e.verification else None,
        "thread_id": e.thread_id,
        "nurse_notified": bool(e.thread_id),
    }
