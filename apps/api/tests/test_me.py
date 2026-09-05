"""本人 App：/me home, year→month timeline, 問我的紀錄 (retrieve-only answers)."""

from __future__ import annotations

import pytest

from agents.personal import ARTIFACTS, PENDING, ask_record, make_ask_tools, retrieve_lines
from main import me_ask, me_home, me_timeline


def test_home_has_status_today_lifelong_and_no_confidence(records_root):
    out = me_home("P001", x_who="P001")
    assert out["status_line"] and out["today"]["dimensions"]
    lf = out["lifelong"]
    assert lf["conditions"] == 3 and lf["hospitalizations"] == 1 and lf["surgeries"] == 1
    assert lf["falls"] >= 2 and lf["years_of_records"] >= 18
    assert out["recent_events"] and all("confidence" not in r for r in out["recent_events"])


def test_timeline_year_layer_only_major_events(records_root):
    out = me_timeline("P003", x_who="P003")
    years = {y["year"]: y for y in out["years"]}
    assert 2012 in years and years[2012]["major"][0]["type"] == "condition"
    for y in out["years"]:
        assert all(
            m["type"] in ("condition", "hospitalization", "surgery", "fall", "acute")
            for m in y["major"]
        )
    assert years[2026]["months"] and sum(m["count"] for m in years[2026]["months"]) > 20


def test_retrieve_finds_history_lines(records_root):
    hits = retrieve_lines("P001", "我以前有做過心臟手術嗎")
    assert any("白內障" in h["text"] or "心房顫動" in h["text"] for h in hits)


def test_submit_answer_only_accepts_retrieved_sources(records_root):
    tools = {t.name: t for t in make_ask_tools("P002")}
    PENDING[("P002", "ask_hits")] = {}
    hits = tools["retrieve"].invoke({"query": "糖尿病"})["hits"]
    assert hits
    bad = tools["submit_answer"].invoke(
        {"sentences": [{"text": "2003 年確診糖尿病", "source_ids": ["obs_fake"]}]}
    )
    assert "error" in bad and "來源" in bad["error"]
    advice = tools["submit_answer"].invoke(
        {"sentences": [{"text": "血糖偏高，建議少吃甜", "source_ids": [hits[0]["id"]]}]}
    )
    assert "error" in advice
    ok = tools["submit_answer"].invoke(
        {"sentences": [{"text": "2003 年確診第 2 型糖尿病", "source_ids": [hits[0]["id"]]}]}
    )
    assert ok["ok"] and ok["sentences"][0]["sources"][0]["id"] == hits[0]["id"]
    assert ARTIFACTS[("P002", "submit_answer")]["found"] is True


def test_ask_says_not_found_when_record_has_nothing(records_root):
    answer, meta = ask_record("P001", "我有沒有去過火星")
    assert answer["found"] is False and answer["fallback"] == "紀錄裡沒有這件事。"
    assert meta["scripted"] is True


def test_me_ask_endpoint_cites_sources(records_root):
    out = me_ask("P001", type("B", (), {"question": "我以前住院過嗎"})(), x_who="P001")
    assert out["found"] and all(s["sources"] for s in out["sentences"])


def test_me_requires_care_circle(records_root):
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        me_home("P001", x_who="nobody")
