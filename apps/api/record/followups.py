"""Durable follow-up work items and a local outbox.

The clinical document remains the source of truth.  This module adds the missing execution
layer: an approved ``FollowUp`` becomes one idempotent task, and the worker moves due tasks to
``queued`` while writing a deduplicated outbox row.  Delivery is deliberately ``displayed_only``
until a real notification provider is configured; a task is never silently lost.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from record_schema import FollowUp, FollowUpTask

from core.ids import new_id
from record.store import get_store

_IDEMPOTENCY = "idempotency_key"
_locks: dict[str, threading.RLock] = {}
_guard = threading.Lock()


def _lock(patient_id: str) -> threading.RLock:
    key = f"{get_store().root.resolve()}::{patient_id}"
    with _guard:
        return _locks.setdefault(key, threading.RLock())


def _paths(patient_id: str) -> tuple[Path, Path]:
    root = get_store().dir(patient_id) / "tasks"
    return root / "followups.json", root / "outbox.jsonl"


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _load(patient_id: str) -> list[FollowUpTask]:
    path, _ = _paths(patient_id)
    if not path.exists():
        return []
    return [
        FollowUpTask.model_validate(row) for row in json.loads(path.read_text(encoding="utf-8"))
    ]


def _save(patient_id: str, rows: list[FollowUpTask]) -> None:
    path, _ = _paths(patient_id)
    _write_atomic(path, json.dumps([r.model_dump(mode="json") for r in rows], ensure_ascii=False))


def schedule(
    patient_id: str,
    follow_up: FollowUp,
    *,
    source_thread: str,
    idempotency_key: str | None = None,
) -> FollowUpTask:
    """Create one task, or return the existing task for the same source operation."""
    key = idempotency_key or f"{source_thread}:{follow_up.question}"
    with _lock(patient_id):
        rows = _load(patient_id)
        existing = next((row for row in rows if row.idempotency_key == key), None)
        if existing:
            return existing
        task = FollowUpTask(
            id=new_id("followup"),
            patient_id=patient_id,
            source_thread=source_thread,
            question=follow_up.question,
            due_at=follow_up.due_at,
            set_by=follow_up.set_by,
            idempotency_key=key,
        )
        _save(patient_id, [*rows, task])
        return task


def list_tasks(patient_id: str, status: str | None = None) -> list[FollowUpTask]:
    with _lock(patient_id):
        rows = _load(patient_id)
    if status:
        rows = [row for row in rows if row.status == status]
    return sorted(rows, key=lambda row: row.due_at)


def _append_outbox(path: Path, task: FollowUpTask, now: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_id": f"outbox_{task.id}",
        "kind": "follow_up_due",
        "task_id": task.id,
        "patient_id": task.patient_id,
        "question": task.question,
        "due_at": task.due_at.isoformat(),
        "queued_at": now.isoformat(),
        "delivery": "displayed_only",
    }
    existing_ids = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                existing_ids.add(json.loads(line).get("event_id"))
    if event["event_id"] in existing_ids:
        return
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def dispatch_due(now: datetime | None = None) -> list[FollowUpTask]:
    """Queue every due pending task once and return the tasks queued in this scan."""
    now = now or datetime.now(UTC)
    queued: list[FollowUpTask] = []
    for patient_id in get_store().list_patients():
        with _lock(patient_id):
            rows = _load(patient_id)
            changed = False
            _, outbox = _paths(patient_id)
            for index, row in enumerate(rows):
                if row.status != "pending" or row.due_at > now:
                    continue
                updated = row.model_copy(
                    update={"status": "queued", "attempts": row.attempts + 1, "queued_at": now}
                )
                _append_outbox(outbox, updated, now)
                rows[index] = updated
                queued.append(updated)
                changed = True
            if changed:
                _save(patient_id, rows)
    return queued


def acknowledge(
    task_id: str, *, answer: str | None = None, patient_id: str | None = None
) -> FollowUpTask:
    """Acknowledge a queued task.  The clinical answer is not written to the timeline here."""
    patient_ids = [patient_id] if patient_id else get_store().list_patients()
    for pid in patient_ids:
        with _lock(pid):
            rows = _load(pid)
            for index, row in enumerate(rows):
                if row.id != task_id:
                    continue
                updated = row.model_copy(
                    update={
                        "status": "acknowledged",
                        "answer": answer,
                        "answered_at": datetime.now(UTC),
                    }
                )
                rows[index] = updated
                _save(pid, rows)
                return updated
    raise KeyError(task_id)


def close(task_id: str, *, patient_id: str | None = None) -> FollowUpTask:
    """Close a task after the human review has consumed its answer."""
    patient_ids = [patient_id] if patient_id else get_store().list_patients()
    for pid in patient_ids:
        with _lock(pid):
            rows = _load(pid)
            for index, row in enumerate(rows):
                if row.id != task_id:
                    continue
                updated = row.model_copy(update={"status": "closed"})
                rows[index] = updated
                _save(pid, rows)
                return updated
    raise KeyError(task_id)


def outbox(patient_id: str) -> list[dict[str, Any]]:
    _, path = _paths(patient_id)
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
