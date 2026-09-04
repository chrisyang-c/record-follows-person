"""Channel 4 — device vitals. HARDCODED for the demo (ARCHITECTURE §8).

Deterministic per (patient_id, date, shift) so seeds and the nurse's onsite prefill agree."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

from record_schema import Vitals

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
