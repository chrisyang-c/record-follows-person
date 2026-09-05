"""Care Circle: authorization is a lookup on the person's record, not a cookie (VISION §15–18)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from main import _authorize, care_circle_revoke, patient_access_log, patient_summary
from record import care_circle as cc


def test_seed_grants_each_role_a_scope_subset(records_root):
    assert set(cc.scopes_for("P001", "nurse_lin")) == {"who", "timeline", "docs", "talk"}
    assert cc.scopes_for("P001", "dr_wu") == ["docs", "who", "timeline"]  # no talk
    assert "talk" in cc.scopes_for("P001", "cg_xiaofang")
    assert cc.scopes_for("P001", "P001") and cc.role_of("P001", "P001") == "patient"
    assert cc.role_of("P001", "fam_P001") == "family"
    assert cc.scopes_for("P001", "stranger") == [] and cc.scopes_for("P001", None) == []


def test_unknown_member_is_403_not_404(records_root):
    with pytest.raises(HTTPException) as e:
        patient_summary("P001", x_who="stranger")
    assert e.value.status_code == 403 and "未獲授權" in e.value.detail


def test_summary_carries_allowed_tabs_and_logs_access(records_root):
    out = patient_summary("P002", tab="docs", x_who="dr_wu")
    assert out["allowed_tabs"] == ["docs", "who", "timeline"] and out["who"] == "dr_wu"
    log = patient_access_log("P002", x_who="P002")["items"]
    assert log and log[0]["who"] == "dr_wu" and log[0]["what"] == "summary:docs"
    assert log[0]["health_id"] == "P-0000002"


def test_revoke_removes_access_and_is_logged(records_root):
    assert "docs" in cc.scopes_for("P003", "nurse_huang")
    assert care_circle_revoke("P003", "nurse_huang", x_who="P003")["revoked"] is True
    assert cc.scopes_for("P003", "nurse_huang") == []
    with pytest.raises(HTTPException):
        _authorize("P003", "nurse_huang")
    assert any(e.what == "revoke:nurse_huang" for e in cc.access_log("P003"))


def test_only_patient_or_family_can_revoke(records_root):
    with pytest.raises(HTTPException) as e:
        care_circle_revoke("P003", "dr_wu", x_who="nurse_lin")
    assert e.value.status_code == 403


def test_health_id_format(records_root):
    from record.store import get_store

    for pid in ("P001", "P002", "P003"):
        assert get_store().load_profile(pid).health_id == f"P-000000{pid[-1]}"
