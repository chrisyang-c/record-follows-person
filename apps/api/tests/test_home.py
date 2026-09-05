"""GET /home/{role}: one call per role home page (KNOWN_ISSUES #19)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from main import home


def test_home_caregiver_cards(records_root):
    out = home("caregiver")
    assert out["role"] == "caregiver" and len(out["residents"]) == 3
    for r in out["residents"]:
        assert {"patient_id", "code_name", "room", "timeline_count"} <= set(r)
        assert {"recorded_today", "notes_count", "session_phase"} == set(r["card"])


def test_home_nurse_cards_carry_trends(records_root):
    out = home("nurse")
    cards = [r["card"] for r in out["residents"]]
    assert all({"abnormal", "series"} == set(c) for c in cards)
    assert any(c["abnormal"] for c in cards)  # the seed has a resident with a story curve
    for c in cards:
        assert len(c["series"]) <= 2
        assert all(s["dimension"] in {a["dimension"] for a in c["abnormal"]} for s in c["series"])


def test_home_doctor_cards(records_root):
    out = home("doctor")
    assert all("round_page" in r["card"] for r in out["residents"])


def test_home_unknown_role(records_root):
    with pytest.raises(HTTPException):
        home("admin")
