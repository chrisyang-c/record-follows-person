"""Personal authentication never restores revoked consent."""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app
from record import care_circle as cc


def test_patient_logs_in_with_own_password(records_root):
    client = TestClient(app)
    response = client.post("/login", json={"who": "P001", "password": "demo-P001-2026!"})
    assert response.status_code == 200
    out = response.json()
    assert out["role"] == "patient" and out["patient_id"] == "P001"
    assert "HttpOnly" in response.headers.get_list("set-cookie")[0]
    client.close()


def test_wrong_password_is_401(records_root):
    client = TestClient(app)
    assert client.post("/login", json={"who": "P001", "password": "0000"}).status_code == 401
    client.close()


def test_login_does_not_restore_revoked_grant(records_root):
    original = next(m for m in cc.active_members("P002") if m.member_id == "dr_wu")
    cc.revoke("P002", "dr_wu", by="P002")
    assert cc.scopes_for("P002", "dr_wu") == []
    client = TestClient(app)
    response = client.post(
        "/login", json={"who": "dr_wu", "patient_id": "P002", "password": "demo-dr_wu-2026!"}
    )
    assert response.status_code == 403
    assert cc.scopes_for("P002", "dr_wu") == []
    client.close()
    cc.grant("P002", original)  # restore this shared domain fixture, not via authentication


def test_staff_can_login_without_patient_context(records_root):
    client = TestClient(app)
    response = client.post("/login", json={"who": "nurse_lin", "password": "demo-nurse_lin-2026!"})
    assert response.status_code == 200
    assert response.json()["patient_id"] is None
    assert client.get("/residents").status_code == 200
    client.close()
