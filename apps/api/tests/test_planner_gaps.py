"""Planner validation (2026-09-05 rules):
* a known dimension may be followed up once when it still has a gap (unfilled sub-field, or a
  clue in the caregiver's words not yet extracted) and the model names that gap;
* two invalid decisions in a row → ask=false (summary card), never a 503;
* LLMUnavailable stays reserved for the model itself failing."""

from __future__ import annotations

import pytest

import ingest.intake_dialog as dialog
from core.llm import NextQuestionOut
from core.trace import clear_for_tests, recent
from ingest.intake_dialog import Turn, known_gaps, run_dialog
from record.store import get_store
from tests.scripted_llm import ScriptedLLM


@pytest.fixture
def scripted(monkeypatch):
    llm = ScriptedLLM()
    monkeypatch.setattr(dialog, "get_llm", lambda: llm)
    dialog._extract_cached.cache_clear()
    return llm


def _pb(pid="P002"):
    s = get_store()
    return s.load_profile(pid), s.load_baseline(pid)


def _turns(*items):
    out = [Turn(text=items[0])]
    for text, q in items[1:]:
        out.append(Turn(text=text, question=q.text, dimension=q.dimension))
    return out


def test_known_gap_detects_unextracted_clue():
    p, b = _pb()
    obs, *_ = dialog.build_observation([Turn(text="今天早餐沒吃完，說肚子脹")], p, b)
    gaps = known_gaps(obs, ["今天早餐沒吃完，說肚子脹"])
    assert "intake" in gaps and any("肚子脹" in g for g in gaps["intake"])


def test_breakfast_bloating_stool_then_follow_up_on_bloating(records_root, scripted):
    """早餐沒吃完＋肚子脹 → 排便 → 硬 → third question may follow up「脹」(intake is known)."""
    clear_for_tests()
    p, b = _pb()
    r1 = run_dialog(_turns("今天早餐沒吃完，說肚子脹"), p, b)
    q1 = r1.next_question
    assert q1 is not None and q1.dimension != "intake"
    scripted.queue.append(
        NextQuestionOut(
            ask=True, dimension="elimination", question="今天有大便嗎？", reason="吃得少"
        )
    )
    r2 = run_dialog(_turns("今天早餐沒吃完，說肚子脹", ("有大便，但比較硬", q1)), p, b)
    q2 = r2.next_question
    assert q2 is not None
    # the model now follows up the known intake dimension, naming the gap
    scripted.queue.append(
        NextQuestionOut(
            ask=True,
            dimension="intake",
            question="肚子脹是今天才開始的嗎？有沒有越來越脹？",
            reason="原話「說肚子脹」還沒記到，補進食與飲水的缺口",
            gap="原話「說肚子脹」還沒記到",
        )
    )
    r3 = run_dialog(
        _turns("今天早餐沒吃完，說肚子脹", ("有大便，但比較硬", q1), ("硬硬的", q2)), p, b
    )
    q3 = r3.next_question
    assert q3 is not None and q3.dimension == "intake" and "脹" in q3.text
    assert q3.gap and "肚子脹" in q3.gap
    assert "note" not in scripted.seen[-1]  # accepted first time: no retry
    assert "肚子脹" in scripted.seen[-1]["known_gaps"]  # the gap was offered to the model


def test_known_dimension_without_naming_gap_is_rejected_then_retried(records_root, scripted):
    clear_for_tests()
    p, b = _pb()
    scripted.queue.append(
        NextQuestionOut(ask=True, dimension="intake", question="他吃了什麼？", reason="想知道")
    )
    r = run_dialog(_turns("今天早餐沒吃完，說肚子脹"), p, b)
    # first decision rejected (no gap named) → retry note → scripted default picks an unknown dim
    assert any("note" in c and "缺口" in c["note"] for c in scripted.seen)
    assert r.next_question is not None and r.next_question.dimension != "intake"


def test_same_known_dimension_only_once(records_root, scripted):
    clear_for_tests()
    p, b = _pb()
    q_intake = dialog.NextQuestion(key="q1", text="肚子還脹嗎？", dimension="intake", reason="缺口")
    scripted.queue.append(
        NextQuestionOut(
            ask=True,
            dimension="intake",
            question="脹多久了？",
            reason="還沒記到脹",
            gap="原話「說肚子脹」還沒記到",
        )
    )
    r = run_dialog(_turns("今天早餐沒吃完，說肚子脹", ("還是脹", q_intake)), p, b)
    assert any("note" in c and "追問過一次" in c["note"] for c in scripted.seen)
    assert r.next_question is None or r.next_question.dimension != "intake"


def test_two_invalid_decisions_give_summary_not_error(records_root, scripted):
    clear_for_tests()
    p, b = _pb()
    bad = NextQuestionOut(ask=True, dimension="intake", question="他吃了什麼？", reason="想知道")
    scripted.queue += [bad, bad.model_copy()]
    r = run_dialog(_turns("今天早餐沒吃完，說肚子脹"), p, b)
    assert r.done and r.next_question is None
    assert r.summary.startswith("我聽到的是：") and "對嗎" in r.summary
    assert any(e["kind"] == "intake.plan_gave_up" for e in recent())


def test_model_failure_is_still_an_error(records_root):
    from core.llm import LLMUnavailable

    p, b = _pb()
    with pytest.raises(LLMUnavailable):  # MockLLM's planner raises: no rule fallback
        run_dialog(_turns("今天早餐沒吃完，說肚子脹"), p, b)


def test_answer_to_follow_up_does_not_overwrite_known_quote(records_root, scripted):
    """Asked about intake (known), the caregiver answers about stool: intake keeps its own words,
    elimination gets the answer."""
    p, b = _pb()
    q = dialog.NextQuestion(key="q1", text="肚子脹多嚴重？", dimension="intake", reason="缺口")
    obs, *_ = dialog.build_observation(
        _turns("今天早餐沒吃完，說肚子脹", ("有大便，但比較硬", q)), p, b
    )
    assert "早餐沒吃完" in obs.domains["intake"].raw_quote
    assert obs.domains["elimination"].raw_quote in "有大便，但比較硬"
    assert obs.followups[-1].answer == "有大便，但比較硬"
