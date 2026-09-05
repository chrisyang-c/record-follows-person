"""Robust statistics — PURE FUNCTIONS. No LLM, no I/O, no schema imports.

Why median/MAD instead of mean/sd: vital signs have outliers (one bad cuff reading, one
sensor slipping) and are not normally distributed. Mean and sd get dragged by a single
bad measurement; median and MAD do not. A "usual range" built on mean±2sd is wrong for
exactly the people this project is for.

Deliberately no numpy/scipy: these five functions should be readable at a glance, and
``apps/api`` should not grow a scientific stack for arithmetic this small.
"""

from __future__ import annotations

from statistics import median

MAD_TO_SIGMA = 1.4826
"""Scale factor that makes MAD comparable to a standard deviation under normality."""

EPS = 1e-9


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile. ``q`` is 0..1."""
    if not values:
        raise ValueError("empty sequence has no percentile")
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = q * (len(xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def mad(values: list[float], center: float | None = None) -> float:
    """Median absolute deviation — this person's own variability.

    Someone whose heart rate swings 55–95 every day and someone who sits at 58–62 both
    have a "normal" 74 and an abnormal 74 respectively. MAD is what tells them apart.
    """
    if not values:
        return 0.0
    c = median(values) if center is None else center
    return median([abs(v - c) for v in values])


def robust_z(value: float, center: float, spread: float) -> float:
    """How far outside this person's own variability. ``spread`` is MAD, not sd.

    Kept internal: CLAUDE.md §1.8 forbids scores in any caregiver/nurse/doctor surface.
    Use it to decide, never to display.
    """
    return (value - center) / (MAD_TO_SIGMA * spread + EPS)


def consecutive_outside(values: list[float], low: float, high: float) -> int:
    """How many of the most recent readings in a row fall outside the band.

    A single reading outside the band is common (measured right after walking). Several
    in a row is a signal. This is the cheapest lever there is against false alarms.
    """
    n = 0
    for v in reversed(values):
        if low <= v <= high:
            break
        n += 1
    return n
