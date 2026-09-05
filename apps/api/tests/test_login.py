"""登入以病人為核心：本人用自己的密碼；其他人要病人的密碼才進 Care Circle。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from main import LoginIn, login
from record import care_circle as cc


def test_patient_logs_in_with_own_code(records_root):
    out = login(LoginIn(who="P001", code="1940"))
    assert out["role"] == "patient" and out["patient_id"] == "P001"


def test_wrong_code_is_401(records_root):
    with pytest.raises(HTTPException) as e:
        login(LoginIn(who="P001", code="0000"))
    assert e.value.status_code == 401


def test_other_role_needs_patient_code_and_gets_scoped_access(records_root):
    cc.revoke("P002", "dr_wu", by="P002")
    assert cc.scopes_for("P002", "dr_wu") == []
    with pytest.raises(HTTPException):
        login(LoginIn(who="dr_wu", patient_id="P002", code="wrong"))
    out = login(LoginIn(who="dr_wu", patient_id="P002", code="1936"))
    assert out["role"] == "doctor"
    assert cc.scopes_for("P002", "dr_wu") == cc.DEFAULT_SCOPES["doctor"]
    assert any(e.what == "login:granted" for e in cc.access_log("P002"))


def test_other_role_must_pick_a_patient(records_root):
    with pytest.raises(HTTPException) as e:
        login(LoginIn(who="nurse_lin", code="1940"))
    assert e.value.status_code == 400
