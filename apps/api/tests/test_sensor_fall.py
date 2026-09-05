"""Channel 4: POST /sim/fall → 可能跌倒 event; hard rules RF11/RF12 only; raw values nurse-only."""

from __future__ import annotations

from record_schema import SensorEvent, StructuredObservation

from ingest.vitals import simulate_fall
from main import SimFallIn, nurse_inbox, patient_summary, sim_fall
from record import conversation as conv
from record import events as sensor_events
from red_flags.rules import SENSOR_SPO2_MIN, SENSOR_STILL_S, RedFlagInput, evaluate


def _obs() -> StructuredObservation:
    return StructuredObservation(raw_text="", language="zh-TW")


def _ev(**kw) -> SensorEvent:
    return simulate_fall("P002", "P-0000002", **kw)


def test_rf11_hits_on_still_seconds_boundary_and_spo2():
    assert not evaluate(RedFlagInput(observation=_obs(), sensor=_ev())).notify_now  # 45 s, 94%
    hit = evaluate(RedFlagInput(observation=_obs(), sensor=_ev(still_seconds=SENSOR_STILL_S)))
    assert hit.notify_now and hit.hits[0].rule_id == "RF11" and "靜止" in hit.hits[0].facts[0]
    miss = evaluate(RedFlagInput(observation=_obs(), sensor=_ev(still_seconds=SENSOR_STILL_S - 1)))
    assert not miss.notify_now
    spo2 = evaluate(RedFlagInput(observation=_obs(), sensor=_ev(spo2_after=SENSOR_SPO2_MIN - 1)))
    assert spo2.notify_now and "SpO₂" in spo2.hits[0].facts[0]
    assert not evaluate(
        RedFlagInput(observation=_obs(), sensor=_ev(spo2_after=SENSOR_SPO2_MIN))
    ).notify_now


def test_rf12_unreachable_needs_a_sensor_event():
    assert not evaluate(RedFlagInput(observation=_obs(), caregiver_unreachable=True)).notify_now
    hit = evaluate(RedFlagInput(observation=_obs(), sensor=_ev(), caregiver_unreachable=True))
    assert hit.notify_now and hit.hits[0].rule_id == "RF12"


def test_sim_fall_creates_possible_fall_and_asks_caregiver(records_root):
    conv.close_session("P002", reason="test")
    out = sim_fall("P-0000002", SimFallIn())
    ev = out["event"]
    assert ev["kind"] == "possible_fall" and ev["status"] == "pending"
    assert out["notified_nurse"] is False and ev["thread_id"] is None
    assert conv.session("P002").pending_event_id == ev["id"]
    last = conv.messages("P002")[-1]
    assert last.role == "system" and last.meta.get("needs_verification") and "可能" in last.text
    # nurse sees the raw values; caregiver / doctor views carry none
    inbox = nurse_inbox()
    mine = next(e for e in inbox["events"] if e["id"] == ev["id"])
    assert mine["still_seconds"] == 45 and mine["hr_after"] > mine["hr_before"]
    cg = patient_summary("P002", x_who="cg_ahua")["sensor_events"][-1]
    assert cg["id"] == ev["id"] and "still_seconds" not in cg and "hr_after" not in cg
    assert "confidence" not in cg and "%" not in str(cg)
    doc = patient_summary("P002", x_who="dr_wu")["sensor_events"][-1]
    assert "accel_peak_g" not in doc
    nurse = patient_summary("P002", x_who="nurse_lin")["sensor_events"][-1]
    assert "accel_peak_g" in nurse


def test_sim_fall_hard_condition_notifies_nurse_via_path_a(records_root):
    conv.close_session("P003", reason="test")
    out = sim_fall("P-0000003", SimFallIn(still_seconds=90))
    ev = out["event"]
    assert out["notified_nurse"] is True and ev["hard_flag"] and ev["thread_id"]
    assert any("靜止 90 秒" in f for f in ev["hard_facts"])
    inbox = nurse_inbox()
    item = next(i for i in inbox["items"] if i["thread_id"] == ev["thread_id"])
    assert item["red_flag"] and item["interrupt_type"] == "nurse_onsite_assessment"
    assert any("感測器" in line for line in item["red_flag_lines"])
    s = conv.session("P003")
    assert s.phase == "red" and s.thread_id == ev["thread_id"]
    assert sensor_events.get("P003", ev["id"]).thread_id == ev["thread_id"]
