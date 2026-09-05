"""統整（2026-09-05）：隊友的個人正常帶（RF13）接進 01／護理站；Care Circle 補 purpose（WHY）。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from record_schema import CareCircleMember

from main import GrantIn, care_circle_grant, home, patient_vitals_bands, twin
from record import care_circle as cc


def test_grant_requires_purpose(records_root):
    body = GrantIn(member_id="nurse_huang", role="nurse", scopes=["docs"], granted_by="P001")
    with pytest.raises(HTTPException) as e:
        care_circle_grant("P001", body, x_who="P001")
    assert e.value.status_code == 400 and "purpose" in e.value.detail
    body.purpose = "夜班交接"
    out = care_circle_grant("P001", body, x_who="P001")
    assert out["purpose"] == "夜班交接"


def test_grant_helper_rejects_empty_purpose(records_root):
    m = CareCircleMember(
        health_id="P-0000002",
        member_id="x",
        role="doctor",
        scopes=["docs"],
        valid_from=datetime.now(UTC),
        granted_by="P002",
        purpose="",
    )
    with pytest.raises(ValueError):
        cc.grant("P002", m)


def test_seed_members_and_access_log_carry_purpose(records_root):
    assert all(m.purpose for m in cc.active_members("P003"))
    twin("P003", x_who="dr_wu")
    log = cc.access_log("P003")
    assert log[0].who == "dr_wu" and log[0].purpose == "巡診與醫囑"


def test_twin_vitals_dimension_uses_personal_band(records_root):
    out = twin("P001", x_who="P001")
    vb = out["vitals_bands"]
    assert vb["established"] and any("收縮壓" in b["text"] for b in vb["bands"])
    assert out["dimensions"]["vitals"]["baseline"].startswith("他平常：")
    for b in vb["bands"]:  # no scores leak into the wellness view either
        assert "z" not in b["text"].lower()


def test_nurse_home_card_carries_band_texts_not_scores(records_root):
    card = next(r["card"] for r in home("nurse")["residents"] if r["patient_id"] == "P001")
    assert card["vitals_band_texts"] and isinstance(card["vitals_departures"], list)
    assert all("score" not in t for t in card["vitals_departures"])


def test_vitals_bands_endpoint_needs_care_circle(records_root):
    with pytest.raises(HTTPException):
        patient_vitals_bands("P001", x_who="nobody")
    out = patient_vitals_bands("P001", x_who="nurse_lin")
    assert "bands" in out and "departures" in out
