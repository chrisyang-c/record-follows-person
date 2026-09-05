"""Personal vital bands: what gets established, what does not, what it says.

The interesting cases are the refusals. A band that establishes itself on four readings
is worse than no band at all, because everything downstream then trusts it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from record_schema import Observation, Provenance, StructuredObservation, Vitals

from baseline.stats import consecutive_outside, mad, percentile
from baseline.vitals_band import compute_band, departure, from_timeline

NOW = datetime(2026, 9, 5, 21, 0, tzinfo=UTC)


def _obs(day_offset: int, **vitals) -> Observation:
    ts = NOW - timedelta(days=day_offset)
    return Observation(
        id=f"obs-{day_offset}",
        patient_id="P001",
        ts=ts,
        shift="day",
        status="approved",
        confirmed_by="nurse",
        provenance=Provenance(source="nurse_assessed", author="nurse", ts=ts),
        observation=StructuredObservation(raw_text="x", language="zh-TW"),
        vitals=Vitals(**vitals, ts=ts, measured_by="device"),
    )


def _series(values: list[int], metric: str = "sbp") -> list[Observation]:
    return [_obs(i, **{metric: v}) for i, v in enumerate(values)]


# --- stats ------------------------------------------------------------------------


def test_percentile_interpolates():
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5


def test_mad_is_not_dragged_by_one_bad_reading():
    """平均數與標準差會被一次量測失誤拉走，中位數與 MAD 不會。"""
    clean = [58.0, 59.0, 60.0, 61.0, 62.0]
    with_outlier = [*clean, 180.0]
    assert mad(clean) == mad(with_outlier) or abs(mad(clean) - mad(with_outlier)) <= 1.0


def test_consecutive_outside_counts_from_the_end():
    assert consecutive_outside([100.0, 90.0, 80.0, 79.0], 85.0, 120.0) == 2
    assert consecutive_outside([80.0, 90.0, 100.0], 85.0, 120.0) == 0


# --- establishment ----------------------------------------------------------------


def test_band_not_established_on_too_few_readings():
    band = compute_band("sbp", [(NOW - timedelta(days=i), 138.0 + i) for i in range(4)])
    assert not band.established
    assert "只有 4 筆" in band.reason
    assert band.text == "", "沒建立的帶不該給出可以被引用的文字"


def test_band_not_established_when_all_readings_are_the_same_day():
    """四十筆全在同一個下午量的，描述的是那個下午，不是這個人。"""
    same_day = [(NOW - timedelta(minutes=5 * i), 138.0 + (i % 3)) for i in range(20)]
    band = compute_band("sbp", same_day)
    assert not band.established
    assert "天" in band.reason


def test_band_not_established_when_every_value_is_identical():
    """完全沒有變異＝裝置卡住，不是穩定。"""
    ident = [(NOW - timedelta(days=i), 138.0) for i in range(20)]
    band = compute_band("sbp", ident)
    assert not band.established
    assert "裝置" in band.reason


def test_band_establishes_on_a_real_series():
    band = compute_band("sbp", [(NOW - timedelta(days=i), 130.0 + (i % 9)) for i in range(30)])
    assert band.established and band.reason == ""
    assert band.low < band.center < band.high
    assert "收縮壓" in band.text and "mmHg" in band.text


def test_from_timeline_reads_measured_values_only():
    """caregiver 說的數字不進帶——`vitals_reported` 是人講的，`vitals` 是量的。"""
    timeline = _series([130 + (i % 9) for i in range(30)])
    reported_only = Observation(
        id="obs-x", patient_id="P001", ts=NOW, shift="day", status="approved",
        confirmed_by="nurse",
        provenance=Provenance(source="caregiver_said", author="caregiver", ts=NOW),
        observation=StructuredObservation(
            raw_text="x", language="zh-TW", vitals_reported=Vitals(sbp=999)
        ),
    )
    bands = from_timeline("P001", [*timeline, reported_only], now=NOW)
    assert bands.get("sbp") is not None
    assert bands.bands["sbp"].high < 200


# --- departure --------------------------------------------------------------------


def test_departure_fires_below_his_own_range():
    band = compute_band("sbp", [(NOW - timedelta(days=i), 134.0 + (i % 9)) for i in range(30)])
    line = departure(band, 112.0, recent=[116.0])
    assert line and "低於他平常的" in line


def test_departure_silent_inside_the_range():
    band = compute_band("sbp", [(NOW - timedelta(days=i), 134.0 + (i % 9)) for i in range(30)])
    assert departure(band, 138.0) is None


def test_departure_silent_on_unestablished_band():
    band = compute_band("sbp", [(NOW - timedelta(days=i), 138.0 + i) for i in range(4)])
    assert departure(band, 60.0) is None


def test_departure_text_has_no_score():
    band = compute_band("hr", [(NOW - timedelta(days=i), 74.0 + (i % 7)) for i in range(30)])
    line = departure(band, 120.0, recent=[118.0])
    assert line
    for banned in ("z=", "%", "分數", "機率", "信心"):
        assert banned not in line.replace("／分", "")


# --- the module must not offer a way to write the baseline back -------------------


def test_module_offers_no_baseline_proposal():
    """ARCHITECTURE §11：baseline 不自動漂移，否則「平常」會被慢慢惡化帶走。

    A band answers "how does this reading compare with what was measured". It must not
    grow a path back into `vitals_usual` — for someone deteriorating, every such
    proposal looks reasonable on the day it appears, and after a few confirmations
    nothing is ever outside the band again.
    """
    import baseline
    from baseline import vitals_band

    assert not hasattr(vitals_band, "propose_vitals_usual")
    assert not [n for n in dir(baseline) if "propose" in n or "usual" in n]
