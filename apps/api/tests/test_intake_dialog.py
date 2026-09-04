from __future__ import annotations

from ingest.intake_dialog import MAX_TURNS, UNKNOWN, Turn, run_dialog
from record.store import get_store


def _pb():
    s = get_store()
    return s.load_profile("P001"), s.load_baseline("P001")


def test_dialog_asks_one_missing_dimension_at_a_time_with_quick_replies(records_root):
    p, b = _pb()
    r = run_dialog([Turn(text="王伯今天飯只吃一半")], p, b)
    assert "intake" in r.observation.domains and not r.done and not r.red
    assert r.next_question is not None and r.next_question.key == "sleep"
    assert UNKNOWN in r.next_question.quick_replies and 2 <= len(r.next_question.quick_replies) <= 4
    # mentioned dimensions are never asked again
    r2 = run_dialog(
        [
            Turn(text="王伯今天飯只吃一半"),
            Turn(text="晚上起來三次", dimension="sleep", quick=False),
        ],
        p,
        b,
    )
    assert r2.observation.domains["sleep"].value == 3.0
    assert r2.next_question is not None and r2.next_question.key not in ("intake", "sleep")
    assert r2.turn_count == 1 and r2.asked_dimensions == ["sleep"]


def test_dialog_stops_after_max_turns_and_summarizes(records_root):
    p, b = _pb()
    turns = [Turn(text="王伯今天怪怪的")]
    r = run_dialog(turns, p, b)
    keys = []
    while r.next_question is not None:
        keys.append(r.next_question.key)
        turns.append(Turn(text=UNKNOWN, dimension=r.next_question.key, quick=True))
        r = run_dialog(turns, p, b)
    assert r.done and r.turn_count <= MAX_TURNS and len(set(keys)) == len(keys)
    assert r.summary.startswith("我聽到的是：王伯") and "對嗎" in r.summary
    assert sum(1 for q in r.observation.followups if q.answered_unknown) == r.turn_count


def test_dialog_red_flag_stops_immediately(records_root):
    p, b = _pb()
    r = run_dialog(
        [Turn(text="王伯跌倒"), Turn(text="撞到頭", dimension="event:fall", quick=True)], p, b
    )
    assert r.red and r.done and r.next_question is None
    assert "fall" in r.observation.incident_flags and r.observation.flags.fall_head_strike
    assert any("建議立即聯絡護理師" in line for line in r.red_flag_lines)


def test_normal_quick_reply_records_same(records_root):
    p, b = _pb()
    r = run_dialog([Turn(text="吃一半"), Turn(text="沒有痛", dimension="pain", quick=True)], p, b)
    assert r.observation.domains["pain"].direction == "same"
    assert "沒有痛" in r.summary and "吃一半" in r.summary
