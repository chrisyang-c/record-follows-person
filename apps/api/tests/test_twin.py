"""01 活體數位孿生：per-dimension state / series / quote; wellness tip only here."""

from __future__ import annotations

from record_schema import DIMENSIONS

from main import twin


def test_twin_has_eight_dimensions_with_states(records_root):
    out = twin("P001", x_who="P001")
    assert set(out["dimensions"]) == set(DIMENSIONS)
    for v in out["dimensions"].values():
        assert v["state"] in ("same", "changed", "red") and v["tip"] and v["label"]
        assert isinstance(v["series"], list)
    assert out["status_line"]
    # 王伯：食量緩降 → intake 有 14 天序列與原話
    assert out["dimensions"]["intake"]["series"] and out["dimensions"]["intake"]["quote"]


def test_twin_requires_care_circle(records_root):
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        twin("P001", x_who="nobody")


def test_twin_wearable_and_avatar_state(records_root):
    out = twin("P002", x_who="P002")
    assert len(out["wearable"]) == 14
    w = out["wearable"][-1]
    assert {"steps", "resting_hr", "hrv_ms", "spo2", "sleep_hours"} <= set(w)
    assert "quality" not in " ".join(w)  # facts only, no quality score
    assert out["avatar"]["mood"] in ("same", "changed", "attention")
    assert out["avatar"]["weight_kg"] == 48.0 and out["avatar"]["sleep_hours"] == w["sleep_hours"]
