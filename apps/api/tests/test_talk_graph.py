"""talk graph: one caregiver message → activity events → reply; red branch; confirmation by text."""

from __future__ import annotations

import pytest

from graphs import talk
from ingest import intake_dialog as dialog
from record import conversation as conv
from tests.scripted_llm import ScriptedLLM


@pytest.fixture
def scripted(monkeypatch):
    llm = ScriptedLLM()
    monkeypatch.setattr(dialog, "get_llm", lambda: llm)
    return llm


def _turn(pid: str, text: str):
    events, final = [], None
    for kind, data in talk.run_turn(pid, text):
        if kind == "event":
            events.append(data)
        elif kind == "error":
            raise AssertionError(data)
        else:
            final = data
    assert final is not None
    return events, final


def test_turn_emits_node_events_and_persists_conversation(records_root, scripted):
    conv.close_session("P002")
    events, final = _turn("P002", "陳奶奶今天吃一半")
    names = [e["name"] for e in events if e["type"] == "node_end"]
    assert names[:5] == [
        "load_person_record", "record_caregiver_message", "intake_agent",
        "baseline_comparator", "red_flag_rules",
    ]
    assert any(e["type"] == "llm_call" and e["name"] == "next_question" for e in events)
    assert all("plain" in e and "summary" in e for e in events)
    assert final["reply_kind"] == "question" and final["reply_meta"]["reason"]
    msgs = conv.messages("P002")
    assert [m.role for m in msgs[-2:]] == ["caregiver", "agent"]
    assert msgs[-1].meta["activity"]  # activity stored with the agent message


def test_confirm_by_text_sends_shift_and_closes(records_root, scripted):
    conv.close_session("P002")
    _turn("P002", "陳奶奶今天吃一半")
    final = None
    for _ in range(6):
        _, final = _turn("P002", "不知道")
        if final["reply_kind"] == "summary":
            break
    assert final and final["phase"] == "confirm"
    _, final = _turn("P002", "對")
    assert final["reply_kind"] == "closing" and final["sent"] and final["phase"] == "closed"
    assert any(m.role == "system" and "已送給護理師" in m.text for m in conv.messages("P002"))
    assert conv.session("P002").phase == "closed"


def test_red_flag_starts_path_a_and_keeps_talking(records_root, scripted):
    conv.close_session("P001")
    events, final = _turn("P001", "王伯跌倒了")  # anticoagulant → RF05
    assert final["red"] and final["thread_id"].startswith("P001:path_a")
    assert any(e["type"] == "red" for e in events)
    assert "已通知護理師，請留在他身邊。" in final["system_lines"]
    assert final["reply_kind"] == "question"  # dialog continues with key facts
    _, final2 = _turn("P001", "清醒")
    assert final2["thread_id"] == final["thread_id"] and not final2["system_lines"]
    from graphs import runner

    snap = runner.snapshot(final["thread_id"])
    assert snap["values"]["caregiver_reports"]
