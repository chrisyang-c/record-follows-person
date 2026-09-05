"""Personal vital-sign bands — pure code, no LLM (CLAUDE.md §1.4).

``Baseline.vitals_usual`` is what a nurse wrote down. This package computes what was
actually measured, as a band, and never writes it back: updating the baseline stays
behind ◇nurse_confirm_baseline (§1.6).
"""

from baseline.stats import consecutive_outside, mad, percentile, robust_z
from baseline.vitals_band import (
    METRICS,
    MIN_DAYS,
    MIN_SAMPLES,
    WINDOW_DAYS,
    band_text,
    compute_band,
    departure,
    from_timeline,
    propose_vitals_usual,
)

__all__ = [
    "consecutive_outside", "mad", "percentile", "robust_z",
    "METRICS", "MIN_DAYS", "MIN_SAMPLES", "WINDOW_DAYS",
    "band_text", "compute_band", "departure", "from_timeline", "propose_vitals_usual",
]
