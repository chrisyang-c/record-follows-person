"""Timeout worker: scans interrupted threads whose deadline passed and injects
Command(resume={"action": "escalate"}) so Path A goes ◇nurse_review → escalate → ◇nurse_review.

Runs inside the API lifespan (APScheduler) and standalone via `make worker`."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler

from core.settings import get_settings
from graphs import registry, runner

log = logging.getLogger(__name__)


def scan_once(now: datetime | None = None) -> list[str]:
    now = now or datetime.now(UTC)
    escalated: list[str] = []
    for row in registry.overdue(now):
        tid = row["thread_id"]
        try:
            runner.resume(tid, {"action": "escalate", "nurse_id": "system_timeout"})
            escalated.append(tid)
            log.warning("escalated %s (deadline %s)", tid, row.get("deadline"))
        except Exception as e:  # noqa: BLE001
            log.error("escalation failed for %s: %s", tid, e)
    return escalated


def start_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(
        scan_once, "interval", seconds=get_settings().WORKER_SCAN_INTERVAL_S, id="timeout-scan"
    )
    sched.start()
    return sched


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    s = start_scheduler()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        s.shutdown()
