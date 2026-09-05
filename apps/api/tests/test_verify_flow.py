"""照護者四鍵：可能跌倒 → 我在他身邊／他沒事／他可能受傷／聯絡不上 → 進現有追問流程；
聯絡不上直接紅燈；回覆進 Path A 的 caregiver_section。"""

from __future__ import annotations

import pytest

import ingest.intake_dialog as dialog
from graphs import runner
from graphs.talk import run_turn
from main import SimFallIn, nurse_inbox, sim_fall, verify_event
from record import conversation as conv
from record import events as sensor_events
from tests.scripted_llm import ScriptedLLM


@pytest.fixture
def scripted(monkeypatch):
    llm = ScriptedLLM()
    monkeypatch.setattr(dialog, "get_llm", lambda: llm)
    dialog._extract_cached.cache_clear()
    return llm


def _turn(pid, text, event_id=None, choice=None):
    events, final = [], None
    for kind, data in run_turn(pid, text, "caregiver", event_id, choice):
        if kind == "event":
            events.append(data)
        elif kind == "error":
            raise AssertionError(data)
        else:
            final = data
    return events, final


def test_with_patient_enters_follow_up_flow(records_root, scripted):
    conv.close_session("P003", reason="test")
    ev = sim_fall("P-0000003", SimFallIn())["event"]
    sentence, by = verify_event("P003", ev["id"], "with_patient", "他坐在地上", who="cg_amei")
    assert sentence.startswith("我在他身邊") and by == "cg_amei"
    e = sensor_events.get("P003", ev["id"])
    assert e.status == "verified" and e.verification.choice == "with_patient"
    assert conv.session("P003").pending_event_id is None
    _events, final = _turn("P003", sentence, ev["id"], "with_patient")
    last_cg = [m for m in conv.messages("P003") if m.role == "caregiver"][-1]
    assert last_cg.meta["choice"] == "with_patient" and last_cg.meta["event_id"] == ev["id"]
    assert final["reply_kind"] == "question"  # existing intake follow-up continues
    assert "fall" in final["obs"]["incident_flags"]


def test_fine_goes_to_summary_without_red(records_root, scripted):
    conv.close_session("P003", reason="test")
    ev = sim_fall("P-0000003", SimFallIn())["event"]
    sentence, _ = verify_event("P003", ev["id"], "fine", who="cg_amei")
    _events, final = _turn("P003", sentence, ev["id"], "fine")
    assert not final["red"] and final["thread_id"] is None
    assert "fall" not in final["obs"]["incident_flags"]


def test_unreachable_notifies_nurse_immediately(records_root, scripted):
    conv.close_session("P002", reason="test")
    ev = sim_fall("P-0000002", SimFallIn())["event"]
    sentence, _ = verify_event("P002", ev["id"], "unreachable", who="cg_ahua")
    events, final = _turn("P002", sentence, ev["id"], "unreachable")
    assert final["red"] and final["thread_id"] and final["reply_kind"] == "closing"
    assert any(e["type"] == "red" for e in events)
    snap = runner.snapshot(final["thread_id"])
    rf = snap["values"]["red_flags"]
    assert any(h["rule_id"] == "RF12" for h in rf["hits"])
    raw = snap["values"]["raw_input"]
    assert raw["caregiver_unreachable"] is True
    assert raw["sensor_event"]["verification"]["choice"] == "unreachable"
    assert "聯絡不上" in snap["values"]["structured_observation"]["raw_text"]
    item = next(i for i in nurse_inbox()["items"] if i["thread_id"] == final["thread_id"])
    assert item["red_flag"] and any("聯絡不上" in line for line in item["red_flag_lines"])
    assert sensor_events.get("P002", ev["id"]).thread_id == final["thread_id"]


def test_maybe_injured_on_anticoagulant_is_red_and_keeps_asking(records_root, scripted):
    conv.close_session("P001", reason="test")
    ev = sim_fall("P-0000001", SimFallIn())["event"]
    sentence, _ = verify_event("P001", ev["id"], "maybe_injured", "說髖部痛", who="cg_xiaofang")
    _events, final = _turn("P001", sentence, ev["id"], "maybe_injured")
    assert final["red"] and final["reply_kind"] == "question"  # RF05: fall + anticoagulant
    snap = runner.snapshot(final["thread_id"])
    assert "髖部痛" in snap["values"]["structured_observation"]["raw_text"]
    assert snap["values"]["raw_input"]["sensor_event"]["id"] == ev["id"]


def test_bad_choice_rejected(records_root):
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        verify_event("P001", "nope", "shrug")
