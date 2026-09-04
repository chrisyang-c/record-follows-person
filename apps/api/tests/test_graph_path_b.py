"""Path B: one shift flow and one round flow."""

from __future__ import annotations

from datetime import UTC, datetime

from graphs import runner
from record.store import get_store

NURSE = "nurse_lin"


def test_shift_flow_confirm_writes_observation():
    before = len(get_store().load_timeline("P003", kinds={"observation"}))
    snap = runner.start(
        "shift",
        "P003",
        {
            "path": "routine",
            "raw_input": {
                "text": "吃一半，右膝痛，晚上起來兩次",
                "language": "zh-TW",
                "shift": "day",
            },
        },
    )
    assert snap["interrupt"]["type"] == "nurse_10s_confirm"
    ms = snap["interrupt"]["minimal_sbar"]
    assert (
        ms["status"] == "draft" and ms["author"] == "ai" and ms["s"] and ms["a_change_vs_baseline"]
    )
    # 退回一次
    snap = runner.resume(
        snap["thread_id"], {"action": "return", "nurse_id": NURSE, "caregiver_addendum": "喝水三杯"}
    )
    assert snap["interrupt"]["type"] == "nurse_10s_confirm"
    # 改一句後確認
    snap = runner.resume(
        snap["thread_id"], {"action": "edit", "nurse_id": NURSE, "edited_a": "進食減半、疼痛新出現"}
    )
    assert snap["status"] == "done"
    entries = get_store().load_timeline("P003", kinds={"observation"})
    assert len(entries) == before + 1
    last = next(e for e in entries if e.id == snap["values"]["written_id"])
    assert last.status == "approved" and last.confirmed_by == NURSE
    assert (
        last.minimal_sbar.author == "nurse"
        and last.minimal_sbar.a_change_vs_baseline == "進食減半、疼痛新出現"
    )
    assert "intake" in last.observation.domains and "pain" in last.observation.domains
    assert snap["values"]["curated"]["written_id"] == last.id


def test_shift_red_flag_hands_off_to_path_a():
    snap = runner.start(
        "shift",
        "P003",
        {
            "path": "routine",
            "raw_input": {"text": "發燒 39 度，一直睡叫不太醒，心跳 120", "language": "zh-TW"},
        },
    )
    assert snap["status"] == "done"
    assert snap["values"]["handoff_to_path_a"] is True
    assert snap["values"]["red_flags"]["notify_now"] is True


def test_round_flow_three_pages_orders_notes_baseline():
    store = get_store()
    snap = runner.start("round", "ALL", {"round_date": datetime.now(UTC).date().isoformat()})
    assert snap["interrupt"]["type"] == "head_nurse_edit_list"
    roster = snap["interrupt"]["roster"]
    pages = snap["interrupt"]["round_pages"]
    assert {r["patient_id"] for r in roster} == {"P001", "P002", "P003"}
    assert len(pages) == 3 and all(p["status"] == "draft" for p in pages)
    p1 = next(p for p in pages if p["patient_id"] == "P001")
    assert (
        p1["who"].startswith("王伯") and p1["changes"] and p1["questions"] and p1["order_followup"]
    )
    assert all(q.endswith("？") for q in p1["questions"])
    assert 1 <= len(p1["chart"]) <= 2 and p1["page_limit_ok"]
    assert "familiarization_writer" in p1["agent_note"] and "scripted" in p1["agent_note"]
    assert all(c["is_abnormal"] for c in p1["changes"])  # ② only changed dimensions
    p3 = next(p for p in pages if p["patient_id"] == "P003")
    assert p3["changes"] == [] and "皆與基線一致" in (p3["cross_dimension_signal"] or "")
    from core.trace import recent

    runs = [e for e in recent(kind="deep_agent.run") if e.get("thread_id") == snap["thread_id"]]
    assert {r["task"] for r in runs} >= {"trend", "round_page"} and all(r["scripted"] for r in runs)
    assert roster[0]["patient_id"] in ("P001", "P003")  # abnormal first

    snap = runner.resume(
        snap["thread_id"],
        {"head_nurse": "head_nurse_chen", "patient_ids": ["P001", "P002", "P003"]},
    )
    assert snap["interrupt"]["type"] == "doctor_round"
    assert len(snap["values"]["published"]) == 3
    assert all(d.status == "approved" for d in store.load_documents("P001", "round_page"))

    orders = [
        {
            "patient_id": "P001",
            "doctor": "dr_wu",
            "text": "飲食：每餐記錄進食量，喝水每天 6 杯；新藥 Mirtazapine 7.5 mg，睡前。",
        },
        {
            "patient_id": "P003",
            "doctor": "dr_wu",
            "text": "疼痛：右膝評估後止痛藥調整；活動：每天陪走廊走一趟。",
        },
    ]
    snap = runner.resume(snap["thread_id"], {"orders": orders, "nurse_id": NURSE})
    assert snap["interrupt"]["type"] == "nurse_confirm_baseline"
    props = snap["interrupt"]["proposals"]
    assert props and all(p["status"] == "draft" for p in props)
    notes = snap["values"]["caregiver_notes"]
    p001_notes = next(n for n in notes if n["patient_id"] == "P001")
    assert p001_notes["lang"] == "zh-TW" and 1 <= len(p001_notes["items"]) <= 3
    assert any("喝水目標" in it or "新藥" in it or "夜間醒來" in it for it in p001_notes["items"])

    baseline_before = store.load_baseline("P001").current("intake")
    snap = runner.resume(snap["thread_id"], {"action": "approve", "nurse_id": NURSE})
    assert snap["status"] == "done"
    assert snap["values"]["baseline_written"]
    cur = store.load_baseline("P001").current("intake")
    assert (
        cur is not None
        and cur.confirmed_by == NURSE
        and cur.description != baseline_before.description
    )
    assert store.load_timeline("P001", kinds={"order"})[-1].confirmed_by == NURSE
    assert store.load_documents("P001", "caregiver_notes")[-1].status == "approved"
