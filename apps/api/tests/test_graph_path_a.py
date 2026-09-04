"""Path A end-to-end: one 退回 (return) and one 超時升級 (timeout escalation), then to END."""

from __future__ import annotations

from graphs import runner, worker
from record.store import get_store

NURSE = "nurse_lin"
ONSITE = {
    "vitals": {"temp_c": 37.9, "sbp": 146, "dbp": 84, "hr": 96, "rr": 20, "spo2": 95},
    "consciousness": "可喚醒，對答清楚",
    "wound": None,
    "notes": "現場評估完成",
}


def _start(
    text="王伯這三天飯只吃一半，晚上起來三次，今天身體有點燙",
    lang="zh-TW",
):
    return runner.start(
        "path_a",
        "P001",
        {
            "path": "incident",
            "raw_input": {
                "text": text,
                "language": lang,
                "caregiver_id": "cg_xiaofang",
                "seems_different": True,
            },
        },
    )


def test_path_a_full_run_with_return_and_timeout_escalation():
    snap = _start()
    assert snap["status"] == "interrupted"
    assert snap["interrupt"]["type"] == "nurse_review"
    sbar = snap["interrupt"]["sbar"]
    assert sbar["status"] == "draft" and sbar["author"] == "ai"
    assert sbar["nurse_assessment"] is None and sbar["nurse_recommendation"] is None
    assert all(q.endswith("？") for q in sbar["ai_questions_for_nurse"])
    assert snap["values"]["deadline"] is not None

    # 1) 退回 → intake_agent re-runs with the caregiver's addendum, back to nurse_review
    snap = runner.resume(
        snap["thread_id"],
        {
            "action": "return",
            "nurse_id": NURSE,
            "return_reason": "請補充喝水量",
            "caregiver_addendum": "水只喝兩杯",
        },
    )
    assert snap["interrupt"]["type"] == "nurse_review"
    assert "兩杯" in snap["values"]["structured_observation"]["raw_text"]
    assert any(r["action"] == "return" for r in snap["values"]["review_log"])

    # 2) 超時 → worker injects escalate → escalate node → back to nurse_review with level 1
    assert snap["values"]["deadline"] is not None
    escalated = worker.scan_once()
    assert snap["thread_id"] in escalated
    snap = runner.snapshot(snap["thread_id"])
    assert snap["interrupt"]["type"] == "nurse_review"
    assert snap["values"]["escalation_level"] == 1
    assert any(n["to"] == "second_nurse" for n in snap["values"]["notifications"])

    # 3) nurse accepts with onsite assessment + writes A and R herself
    snap = runner.resume(
        snap["thread_id"],
        {
            "action": "accept",
            "nurse_id": NURSE,
            "onsite_assessment": ONSITE,
            "nurse_assessment": "進食連續三天減半，夜眠中斷，體溫 37.9，需醫師評估。",
            "nurse_recommendation": "聯絡特約醫院安排當日看診。",
        },
    )
    assert snap["interrupt"]["type"] == "nurse_route_choice"
    sbar = snap["values"]["sbar"]
    assert (
        sbar["status"] == "approved" and sbar["author"] == "nurse" and sbar["confirmed_by"] == NURSE
    )

    # 4) route choice → handoff → incident file → timeline_write → family draft
    snap = runner.resume(
        snap["thread_id"], {"route": "contact_contract_hospital", "nurse_id": NURSE}
    )
    assert snap["interrupt"]["type"] == "nurse_approve_notification"
    assert snap["values"]["documents"]["incident_file"]
    assert snap["values"]["documents"]["handoff_page_id"]
    draft = snap["interrupt"]["draft"]
    assert draft["status"] == "draft" and draft["to"] == "family"

    # 5) approve family notification → send_line (display only) → follow-up → END
    snap = runner.resume(snap["thread_id"], {"action": "approve", "nurse_id": NURSE})
    assert snap["status"] == "done"
    assert snap["values"]["family_notification"]["status"] == "displayed_only"
    assert snap["values"]["follow_up"]["set_by"] == NURSE

    store = get_store()
    incidents = store.load_timeline("P001", kinds={"incident"})
    assert any(i.id == snap["values"]["documents"]["incident_entry"] for i in incidents)
    doc = store.get_document("P001", snap["values"]["documents"]["incident_file"])
    assert doc is not None and doc.doc_type == "incident_file"
    assert doc.nurse_section.isbar.nurse_assessment.startswith("進食")
    assert doc.follow_up is not None and any(n.to == "family" for n in doc.notifications)
    ledger = store.read_provenance("P001")
    assert any(line.ref == doc.id for line in ledger)


def test_path_a_red_flag_skips_draft_and_goes_to_onsite():
    snap = _start("王伯在浴室跌倒，頭撞到洗手台，現在講話怪怪的")
    assert snap["interrupt"]["type"] == "nurse_onsite_assessment"
    assert snap["values"].get("sbar") is None  # no AI draft on the red path
    assert snap["values"]["red_flags"]["notify_now"] is True
    assert any(
        n["to"] == "nurse" and "紅燈" in n["content"] for n in snap["values"]["notifications"]
    )
    snap = runner.resume(
        snap["thread_id"],
        {
            "nurse_id": NURSE,
            "onsite_assessment": {**ONSITE, "wound": "右額血腫 2 cm"},
            "nurse_assessment": "跌倒撞頭，服用抗凝血劑。",
            "nurse_recommendation": "後送急診。",
        },
    )
    assert snap["interrupt"]["type"] == "nurse_route_choice"
    assert snap["values"]["sbar"]["author"] == "nurse"


def test_resume_validation_rejects_missing_nurse_a_r():
    snap = _start()
    import pytest

    with pytest.raises(ValueError):
        runner.resume(
            snap["thread_id"], {"action": "accept", "nurse_id": NURSE, "onsite_assessment": ONSITE}
        )
