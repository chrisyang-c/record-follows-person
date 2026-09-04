from __future__ import annotations

import pytest

import ingest.intake_dialog as dialog
from core.llm import LLMUnavailable
from core.trace import clear_for_tests, recent
from ingest.intake_dialog import MAX_LLM_TURNS, UNKNOWN, Turn, run_dialog
from record.store import get_store
from tests.scripted_llm import ScriptedLLM


@pytest.fixture
def scripted(monkeypatch):
    llm = ScriptedLLM()
    monkeypatch.setattr(dialog, "get_llm", lambda: llm)
    return llm


def _pb(pid="P001"):
    s = get_store()
    return s.load_profile(pid), s.load_baseline(pid)


def test_no_model_means_error_not_rule_fallback(records_root):
    p, b = _pb()
    with pytest.raises(LLMUnavailable):
        run_dialog([Turn(text="王伯今天飯只吃一半")], p, b)


def test_agent_decides_each_question_with_reason(records_root, scripted):
    clear_for_tests()
    p, b = _pb()
    r = run_dialog([Turn(text="王伯今天飯只吃一半")], p, b)
    assert "intake" in r.observation.domains and not r.done and not r.red
    assert r.next_question is not None and r.next_question.dimension != "intake"
    assert r.next_question.reason  # the model's reason is part of the decision
    q = r.next_question
    r2 = run_dialog(
        [
            Turn(text="王伯今天飯只吃一半"),
            Turn(text="晚上起來三次", question=q.text, dimension=q.dimension),
        ],
        p,
        b,
    )
    assert r2.turn_count == 1 and r2.asked == [q.text]
    assert r2.next_question is not None and r2.next_question.text != q.text
    assert r2.reports[0].question == q.text and r2.reports[0].answer == "晚上起來三次"
    assert any(e["kind"] == "intake.turn" for e in recent())


def test_budget_of_four_then_summary(records_root, scripted):
    p, b = _pb()
    turns = [Turn(text="王伯今天怪怪的")]
    r = run_dialog(turns, p, b)
    n = 0
    while r.next_question is not None:
        n += 1
        turns.append(
            Turn(text=UNKNOWN, question=r.next_question.text, dimension=r.next_question.dimension)
        )
        r = run_dialog(turns, p, b)
    assert r.done and n <= MAX_LLM_TURNS and r.turn_count == n
    assert r.summary.startswith("我聽到的是：王伯") and "對嗎" in r.summary
    assert sum(1 for q in r.observation.followups if q.answered_unknown) == n


def test_red_flag_branches_and_keeps_asking(records_root, scripted):
    p, b = _pb("P003")  # no anticoagulant: 跌倒 alone is not red
    turns = [Turn(text="李阿公在走廊跌倒")]
    r = run_dialog(turns, p, b)
    assert not r.red and r.next_question is not None
    turns.append(
        Turn(text="站不起來", question="能不能自己站起來？", dimension=None, phase="routine")
    )
    r = run_dialog(turns, p, b)
    assert r.red and r.observation.flags.cannot_get_up_after_fall  # RF10
    assert not r.done and r.next_question is not None and r.intro  # dialog continues; intro once
    turns.append(Turn(text="清醒，講話正常", question=r.next_question.text, phase="red"))
    r = run_dialog(turns, p, b)
    assert (
        r.red and r.intro is None and any("建議立即聯絡護理師" in line for line in r.red_flag_lines)
    )
    while r.next_question is not None:
        turns.append(Turn(text="沒有", question=r.next_question.text, phase="red"))
        r = run_dialog(turns, p, b)
    assert r.done and r.closing and len(r.reports) == len(turns) - 1


def test_red_on_first_sentence_gives_intro(records_root, scripted):
    p, b = _pb("P001")  # anticoagulant: 跌倒 → RF05 immediately
    r = run_dialog([Turn(text="王伯跌倒")], p, b)
    assert r.red and not r.done and r.intro and r.next_question is not None


def test_normal_answer_records_same(records_root, scripted):
    p, b = _pb()
    r = run_dialog(
        [Turn(text="吃一半"), Turn(text="沒有痛", question="有沒有哪裡痛？", dimension="pain")],
        p,
        b,
    )
    assert r.observation.domains["pain"].direction == "same"
    assert "沒有痛" in r.summary and "吃一半" in r.summary
