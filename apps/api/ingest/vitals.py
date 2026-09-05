"""Channel 4 — device vitals + simulated wearable fall signal (ARCHITECTURE §8).

Vitals are deterministic per (patient_id, date, shift) so seeds and the nurse's onsite prefill
agree. ``simulate_fall`` produces one sensor event (acceleration spike, orientation change,
seconds still, heart rate before/after) — POST /sim/fall/{health_id} triggers it."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

from record_schema import SensorEvent, Vitals

from core.ids import new_id

_USUAL: dict[str, dict[str, float]] = {
    "P001": {"temp_c": 36.6, "sbp": 138, "dbp": 82, "hr": 76, "rr": 18, "spo2": 96},
    "P002": {"temp_c": 36.4, "sbp": 126, "dbp": 74, "hr": 70, "rr": 16, "spo2": 97},
    "P003": {"temp_c": 36.7, "sbp": 144, "dbp": 86, "hr": 82, "rr": 18, "spo2": 95},
}


def usual(patient_id: str) -> Vitals:
    u = _USUAL.get(
        patient_id, {"temp_c": 36.6, "sbp": 130, "dbp": 80, "hr": 74, "rr": 17, "spo2": 96}
    )
    return Vitals(**{k: (int(v) if k != "temp_c" else v) for k, v in u.items()})


def measure(patient_id: str, on: date, shift: str = "day", measured_by: str = "device") -> Vitals:
    base = usual(patient_id)
    seed = int(hashlib.sha1(f"{patient_id}{on}{shift}".encode()).hexdigest(), 16)
    jitter = [(seed >> (i * 4)) % 5 - 2 for i in range(6)]
    return Vitals(
        temp_c=round((base.temp_c or 36.6) + jitter[0] * 0.1, 1),
        sbp=(base.sbp or 130) + jitter[1] * 3,
        dbp=(base.dbp or 80) + jitter[2] * 2,
        hr=(base.hr or 74) + jitter[3] * 2,
        rr=(base.rr or 17) + (jitter[4] % 2),
        spo2=(base.spo2 or 96) + (jitter[5] % 2),
        measured_by=measured_by,
        ts=datetime.combine(on, datetime.min.time(), UTC).replace(hour=8 if shift == "day" else 20),
    )


def simulate_fall(
    patient_id: str,
    health_id: str,
    at: datetime | None = None,
    *,
    still_seconds: int | None = None,
    spo2_after: int | None = None,
    location: str = "房間",
) -> SensorEvent:
    """One simulated wearable signal. Defaults describe a plausible non-hard-flag fall (still
    45 s, SpO₂ 94); pass still_seconds ≥60 or spo2_after <92 to hit the hard rule (RF11)."""
    at = at or datetime.now(UTC)
    base = usual(patient_id)
    seed = int(hashlib.sha1(f"{patient_id}{at.isoformat()}".encode()).hexdigest(), 16)
    hr_before = int(base.hr or 74) + seed % 5 - 2
    return SensorEvent(
        id=new_id("sens", at),
        health_id=health_id,
        patient_id=patient_id,
        ts=at,
        location=location,
        accel_peak_g=round(2.6 + (seed >> 4) % 10 / 10, 1),
        orientation_change_deg=float(70 + (seed >> 8) % 25),
        still_seconds=still_seconds if still_seconds is not None else 45,
        hr_before=hr_before,
        hr_after=hr_before + 28 + (seed >> 12) % 8,
        spo2_after=spo2_after if spo2_after is not None else 94,
    )
