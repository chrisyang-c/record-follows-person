"""Load a resident's bands from the record store.

Kept out of ``baseline/__init__.py`` on purpose: ``red_flags/rules.py`` imports
``baseline.vitals_band`` and must not pull the store in transitively. The pure maths
and the I/O stay in separate modules.

Bands read 90 days of timeline, so they are cached per (patient, day). A band that
changes within the same day would only move by a fraction of one reading anyway, and
recomputing it on every red-flag evaluation would read the whole timeline each time.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from record_schema import VitalsBands

from baseline.vitals_band import WINDOW_DAYS, from_timeline

_CACHE: dict[tuple[str, date, int], VitalsBands] = {}


def bands_for(
    patient_id: str,
    *,
    now: datetime | None = None,
    window_days: int = WINDOW_DAYS,
) -> VitalsBands | None:
    """This resident's measured vital ranges, or ``None`` if the record is unreadable.

    Never raises: a missing record must not stop red-flag evaluation. Callers treat
    ``None`` as "no bands" and every existing rule behaves exactly as before.
    """
    now = now or datetime.now(UTC)
    key = (patient_id, now.date(), window_days)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    try:
        from record.store import get_store

        timeline = get_store().load_timeline(
            patient_id,
            since=now - timedelta(days=window_days),
            kinds={"observation"},
        )
    except Exception:  # noqa: BLE001 — bands are an enhancement, never a hard dependency
        return None

    bands = from_timeline(patient_id, timeline, now=now, window_days=window_days)
    _CACHE[key] = bands
    return bands


def invalidate(patient_id: str | None = None) -> None:
    """Drop cached bands. Called after seeding or when a nurse writes new vitals."""
    if patient_id is None:
        _CACHE.clear()
        return
    for key in [k for k in _CACHE if k[0] == patient_id]:
        _CACHE.pop(key, None)
