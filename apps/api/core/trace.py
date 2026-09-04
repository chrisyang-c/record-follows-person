"""Agent / LLM call trace — the evidence that agents actually run.

Every model call, every next-question decision (with the model's `reason`), every deep-agent
run and every subagent tool call appends one JSON line to records/_trace/<date>.jsonl
(records/ is git-ignored) and to an in-memory ring buffer. Entries are tagged with the current
`thread_id` / `dialog_id` / `run_id` (contextvars) so GET /debug/trace/{thread_id} can list one
conversation's calls with prompt summary, output, reason and duration.
"""

from __future__ import annotations

import contextvars
import json
import threading
import time
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from core.settings import get_settings

_BUF: deque[dict[str, Any]] = deque(maxlen=2000)
_LOCK = threading.Lock()
_THREAD: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_thread", default=None)
_DIALOG: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_dialog", default=None)
_RUN: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_run", default=None)


@contextmanager
def tagged(
    thread_id: str | None = None, dialog_id: str | None = None, run_id: str | None = None
) -> Iterator[None]:
    tokens = []
    if thread_id is not None:
        tokens.append((_THREAD, _THREAD.set(thread_id)))
    if dialog_id is not None:
        tokens.append((_DIALOG, _DIALOG.set(dialog_id)))
    if run_id is not None:
        tokens.append((_RUN, _RUN.set(run_id)))
    try:
        yield
    finally:
        for var, tok in tokens:
            var.reset(tok)


def current_tags() -> dict[str, str | None]:
    return {"thread_id": _THREAD.get(), "dialog_id": _DIALOG.get(), "run_id": _RUN.get()}


def _short(v: Any, n: int = 600) -> Any:
    if isinstance(v, str):
        return v if len(v) <= n else v[: n - 1] + "…"
    if isinstance(v, dict):
        return {k: _short(x, n) for k, x in v.items()}
    if isinstance(v, list):
        return [_short(x, n) for x in v[:30]]
    return v


def _file() -> Any:
    d = get_settings().records_root / "_trace"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{datetime.now(UTC).date().isoformat()}.jsonl"


def trace(kind: str, **fields: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {"ts": datetime.now(UTC).isoformat(), "kind": kind}
    entry.update({k: v for k, v in current_tags().items() if v})
    entry.update({k: _short(v) for k, v in fields.items()})
    with _LOCK:
        _BUF.append(entry)
        try:
            with _file().open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass
    return entry


class timed:
    """with timed() as t: ...; t.ms → elapsed milliseconds (for duration fields)."""

    def __enter__(self) -> timed:
        self.t0 = time.perf_counter()
        self.ms = 0
        return self

    def __exit__(self, *exc: object) -> None:
        self.ms = int((time.perf_counter() - self.t0) * 1000)


def recent(
    kind: str | None = None, limit: int = 100, contains: str | None = None
) -> list[dict[str, Any]]:
    with _LOCK:
        rows = list(_BUF)
    if kind:
        rows = [r for r in rows if r["kind"].startswith(kind)]
    if contains:
        rows = [r for r in rows if contains in json.dumps(r, ensure_ascii=False)]
    return rows[-limit:]


def for_ids(
    thread_id: str | None = None, dialog_id: str | None = None, run_ids: set[str] | None = None
) -> list[dict[str, Any]]:
    """All entries for a thread/dialog, read from the JSONL files (survives restarts)."""
    d = get_settings().records_root / "_trace"
    out: list[dict[str, Any]] = []
    if not d.exists():
        return out
    for f in sorted(d.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                (thread_id and e.get("thread_id") == thread_id)
                or (dialog_id and e.get("dialog_id") == dialog_id)
                or (run_ids and e.get("run_id") in run_ids)
            ):
                out.append(e)
    return out


def clear_for_tests() -> None:
    with _LOCK:
        _BUF.clear()
