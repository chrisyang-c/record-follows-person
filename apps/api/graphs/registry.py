"""Thread registry: which graph threads exist, what they wait for, and their deadlines.

Postgres table when DATABASE_URL is set (created by graphs/migrate.py); in-memory otherwise.
Used by the nurse inbox (API) and the timeout worker."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.settings import get_settings

_MEM: dict[str, dict[str, Any]] = {}

DDL = """
CREATE TABLE IF NOT EXISTS threads (
  thread_id        TEXT PRIMARY KEY,
  graph            TEXT NOT NULL,
  patient_id       TEXT NOT NULL,
  status           TEXT NOT NULL,
  interrupt_type   TEXT,
  deadline         TIMESTAMPTZ,
  escalation_level INT DEFAULT 0,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def _conn():
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(get_settings().DATABASE_URL, autocommit=True, row_factory=dict_row)


def _use_db() -> bool:
    return bool(get_settings().DATABASE_URL) and _db_ok()


_db_state: dict[str, bool] = {}


def _db_ok() -> bool:
    if "ok" not in _db_state:
        try:
            with _conn() as c:
                c.execute("SELECT 1 FROM threads LIMIT 1")
            _db_state["ok"] = True
        except Exception:  # noqa: BLE001
            _db_state["ok"] = False
    return _db_state["ok"]


def reset_for_tests() -> None:
    _MEM.clear()
    _db_state.clear()


def upsert(thread_id: str, **fields: Any) -> None:
    now = datetime.now(UTC)
    if _use_db():
        cols = {
            k: v
            for k, v in fields.items()
            if k
            in ("graph", "patient_id", "status", "interrupt_type", "deadline", "escalation_level")
        }
        cols.setdefault("status", "running")
        with _conn() as c:
            c.execute(
                """
                INSERT INTO threads
                  (thread_id, graph, patient_id, status, interrupt_type, deadline, escalation_level)
                VALUES
                  (%(thread_id)s, %(graph)s, %(patient_id)s, %(status)s, %(interrupt_type)s,
                   %(deadline)s, %(escalation_level)s)
                ON CONFLICT (thread_id) DO UPDATE SET
                  status = EXCLUDED.status, interrupt_type = EXCLUDED.interrupt_type,
                  deadline = EXCLUDED.deadline, escalation_level = EXCLUDED.escalation_level,
                  updated_at = now()
                """,
                {
                    "thread_id": thread_id,
                    "graph": cols.get("graph", _MEM.get(thread_id, {}).get("graph", "?")),
                    "patient_id": cols.get(
                        "patient_id", _MEM.get(thread_id, {}).get("patient_id", "?")
                    ),
                    "status": cols["status"],
                    "interrupt_type": cols.get("interrupt_type"),
                    "deadline": cols.get("deadline"),
                    "escalation_level": cols.get("escalation_level", 0),
                },
            )
    row = _MEM.setdefault(thread_id, {"thread_id": thread_id, "created_at": now})
    row.update(fields)
    row["updated_at"] = now


def get(thread_id: str) -> dict[str, Any] | None:
    if _use_db():
        with _conn() as c:
            r = c.execute("SELECT * FROM threads WHERE thread_id = %s", (thread_id,)).fetchone()
            return dict(r) if r else None
    return _MEM.get(thread_id)


def list_threads(status: str | None = None, graph: str | None = None) -> list[dict[str, Any]]:
    if _use_db():
        q = "SELECT * FROM threads WHERE 1=1"
        params: list[Any] = []
        if status:
            q += " AND status = %s"
            params.append(status)
        if graph:
            q += " AND graph = %s"
            params.append(graph)
        q += " ORDER BY updated_at DESC"
        with _conn() as c:
            return [dict(r) for r in c.execute(q, params).fetchall()]
    rows = [
        r
        for r in _MEM.values()
        if (not status or r.get("status") == status) and (not graph or r.get("graph") == graph)
    ]
    return sorted(
        rows, key=lambda r: r.get("updated_at") or datetime.min.replace(tzinfo=UTC), reverse=True
    )


def overdue(now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(UTC)
    return [
        r
        for r in list_threads(status="interrupted")
        if r.get("deadline") is not None
        and r["deadline"] <= now
        and r.get("interrupt_type") == "nurse_review"
    ]
