"""Personal vital-sign bands, derived from this person's own measurements.

The gap this fills: ``red_flags/rules.py`` thresholds are population norms (SpO₂ <92,
SBP <90 or >220). They are correct as hard conditions and stay exactly as they are.
But P001's usual systolic is 138 — a reading of 118 is unremarkable against the
population and a real drop for him. ``Baseline.vitals_usual`` is one number a nurse
wrote down; this module computes the *band* from what was actually measured.

Boundaries this module respects:
  CLAUDE.md §1.4   pure code — no LLM call anywhere in this file
  CLAUDE.md §1.8   no score, probability or confidence value reaches the output text
  CLAUDE.md §11    does not write timeline, does not touch provenance
  ARCHITECTURE §11 never writes the baseline and offers no path back into it — see the
                   note at the bottom of this file for why
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from record_schema import (
    VITAL_LABELS,
    VITAL_UNITS,
    Observation,
    TimelineEntry,
    Vitals,
    VitalsBand,
    VitalsBands,
)

from baseline.stats import consecutive_outside, mad, percentile, robust_z

METRICS: tuple[str, ...] = ("temp_c", "sbp", "dbp", "hr", "rr", "spo2")

WINDOW_DAYS = 90
"""How far back a band looks. Long enough to average out a bad week, short enough that
a genuine change of state eventually moves it."""

MIN_SAMPLES: dict[str, int] = {
    "temp_c": 12,
    "sbp": 12,
    "dbp": 12,
    "hr": 12,
    "rr": 12,
    "spo2": 12,
}
"""Below this the band is not established and must not be used to judge anything.

The most common source of false alarms is not a detector that is too sensitive — it is
a "usual range" computed from four readings."""

MIN_DAYS = 5
"""Readings spread over at least this many days. Forty readings taken on one afternoon
describe that afternoon, not this person."""

DECIMALS: dict[str, int] = {"temp_c": 1}


def _round(metric: str, value: float) -> float:
    return round(value, DECIMALS.get(metric, 0))


def _fmt(metric: str, value: float) -> str:
    return f"{value:.{DECIMALS.get(metric, 0)}f}"


def band_text(metric: str, low: float, high: float) -> str:
    """The one line a nurse reads: 「收縮壓 129–139 mmHg」. A range, never a score."""
    return f"{VITAL_LABELS[metric]} {_fmt(metric, low)}–{_fmt(metric, high)}{VITAL_UNITS[metric]}"


def _samples(
    timeline: list[TimelineEntry] | list[Any],
    metric: str,
    *,
    now: datetime,
    window_days: int,
) -> list[tuple[datetime, float]]:
    """Every nurse- or device-measured value of ``metric`` inside the window.

    Caregiver-reported numbers are deliberately excluded: ``vitals_reported`` is what
    someone said, ``vitals`` is what was measured. A band built from hearsay is not a band.
    """
    since = now - timedelta(days=window_days)
    out: list[tuple[datetime, float]] = []
    for entry in timeline:
        if getattr(entry, "kind", None) != "observation":
            continue
        obs: Observation = entry  # type: ignore[assignment]
        vitals: Vitals | None = obs.vitals
        if vitals is None:
            continue
        value = getattr(vitals, metric, None)
        if value is None:
            continue
        ts = vitals.ts or getattr(obs, "ts", None)
        if ts is None:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        if ts < since or ts > now:
            continue
        out.append((ts, float(value)))
    out.sort(key=lambda p: p[0])
    return out


def compute_band(
    metric: str,
    samples: list[tuple[datetime, float]],
) -> VitalsBand:
    """One metric's band. Always returns a band — ``established`` says whether to trust it."""
    values = [v for _, v in samples]
    days = len({ts.date() for ts, _ in samples})
    n = len(values)

    if n == 0:
        return VitalsBand(
            metric=metric,  # type: ignore[arg-type]
            label=VITAL_LABELS[metric],
            unit=VITAL_UNITS[metric],
            center=0.0,
            spread=0.0,
            low=0.0,
            high=0.0,
            n=0,
            days=0,
            established=False,
            reason="沒有量測值",
        )

    from statistics import median

    center = median(values)
    spread = mad(values, center)
    low = percentile(values, 0.10)
    high = percentile(values, 0.90)

    reason = ""
    if n < MIN_SAMPLES.get(metric, 12):
        reason = f"量測值只有 {n} 筆，不足以說是他平常的樣子"
    elif days < MIN_DAYS:
        reason = f"量測只涵蓋 {days} 天，不足以說是他平常的樣子"
    elif spread <= 0:
        reason = "所有量測值完全相同，疑似裝置異常"

    return VitalsBand(
        metric=metric,  # type: ignore[arg-type]
        label=VITAL_LABELS[metric],
        unit=VITAL_UNITS[metric],
        center=_round(metric, center),
        spread=round(spread, 3),
        low=_round(metric, low),
        high=_round(metric, high),
        n=n,
        days=days,
        established=not reason,
        reason=reason,
        text=band_text(metric, low, high) if not reason else "",
    )


def from_timeline(
    patient_id: str,
    timeline: list[TimelineEntry] | list[Any],
    *,
    now: datetime | None = None,
    window_days: int = WINDOW_DAYS,
) -> VitalsBands:
    """All bands for one resident. Reads the timeline; writes nothing."""
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return VitalsBands(
        patient_id=patient_id,
        computed_at=now,
        window_days=window_days,
        bands={
            m: compute_band(m, _samples(timeline, m, now=now, window_days=window_days))
            for m in METRICS
        },
    )


# ---------------------------------------------------------------------------
# Deviation — used by red_flags/rules.py RF13
# ---------------------------------------------------------------------------

OUTSIDE_MARGIN_Z = 2.5
"""How far past the band counts as a departure rather than a normal wobble."""

MIN_CONSECUTIVE = 2
"""A single reading outside the band does not fire. Two in a row does."""


def departure(
    band: VitalsBand,
    value: float,
    *,
    recent: list[float] | None = None,
) -> str | None:
    """Is ``value`` a departure from this person's own usual range?

    Returns the sentence a nurse should read, or ``None``. The sentence states the
    measured value and the person's range — no z-score, no percentage, no severity
    (CLAUDE.md §1.8). Requires the band to be established and, when recent readings are
    supplied, more than one reading in a row outside the band.
    """
    if not band.established:
        return None
    if band.low <= value <= band.high:
        return None

    z = robust_z(value, band.center, band.spread)
    if abs(z) < OUTSIDE_MARGIN_Z:
        return None

    if recent is not None:
        streak = consecutive_outside([*recent, value], band.low, band.high)
        if streak < MIN_CONSECUTIVE:
            return None

    direction = "高於" if value > band.high else "低於"
    return (
        f"{band.label} {_fmt(band.metric, value)}{band.unit}，"
        f"{direction}他平常的 {_fmt(band.metric, band.low)}–"
        f"{_fmt(band.metric, band.high)}{band.unit}"
    )


# ---------------------------------------------------------------------------
# Why there is no propose_vitals_usual() here
# ---------------------------------------------------------------------------
#
# It is tempting to turn a band back into a proposed `vitals_usual` and let the nurse
# confirm it. ARCHITECTURE §11 rules that out, and it is right:
#
#   「baseline 多久滾動一次？只在醫囑或護理師確認時更新，不自動漂移，
#     否則『平常』會被慢慢惡化帶走。」
#
# For someone who is slowly deteriorating, every such proposal looks reasonable on the
# day it appears. Confirm a few of them and "usual" has followed the disease down —
# and then nothing is ever outside the band again. `baseline_update_proposal` in
# graphs/path_b.py deliberately proposes only from doctor's orders.
#
# So the band and `vitals_usual` stay separate: the band only ever answers "how does
# this reading compare with what has actually been measured", and never writes back.
