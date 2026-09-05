"""Care Circle — patient-owned access to one person's record (VISION §15–18).

records/{patient_id}/care_circle.json   — members (append; revoke sets revoked_at)
records/{patient_id}/access_log.jsonl   — who looked at what, when (「誰看過我的紀錄」)
records/_identities.json                 — demo identities (member_id → role, display name)

Authorization is a lookup here, never a cookie: the web only stores「我是誰」(``me``) and every
record read passes it as ``X-Who``. A tab outside the member's scopes renders「未獲授權」.
"""

from __future__ import annotations

import hashlib as _hashlib
import json
from datetime import UTC, datetime
from datetime import timedelta as _timedelta
from typing import Any

from record_schema import AccessLogEntry, CareCircleMember, CareRole, Scope

from record.store import get_store

ALL_SCOPES: tuple[Scope, ...] = ("who", "timeline", "docs", "talk")
DEFAULT_PURPOSE: dict[CareRole, str] = {
    "patient": "本人查看自己的紀錄",
    "family": "家屬照護與陪同",
    "caregiver": "每日照顧與記錄",
    "nurse": "護理評估與確認",
    "doctor": "巡診與醫囑",
}
DEFAULT_SCOPES: dict[CareRole, list[Scope]] = {
    "patient": ["who", "timeline", "docs", "talk"],
    "family": ["who", "timeline", "docs", "talk"],
    "caregiver": ["talk", "who", "timeline", "docs"],
    "nurse": ["docs", "timeline", "who", "talk"],
    "doctor": ["docs", "who", "timeline"],
}


def _file(patient_id: str):
    return get_store().dir(patient_id) / "care_circle.json"


def _log_file(patient_id: str):
    return get_store().dir(patient_id) / "access_log.jsonl"


def _identities_file():
    return get_store().root / "_identities.json"


# --- identities (demo registry written by seed) -------------------------------------------


def identities() -> dict[str, dict[str, Any]]:
    f = _identities_file()
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def save_identities(items: dict[str, dict[str, Any]]) -> None:
    f = _identities_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


def whoami(who: str | None) -> dict[str, Any] | None:
    if not who:
        return None
    it = identities().get(who)
    return {"who": who, **it} if it else None


# --- members ---------------------------------------------------------------------------------


def members(patient_id: str) -> list[CareCircleMember]:
    f = _file(patient_id)
    if not f.exists():
        return []
    return [CareCircleMember.model_validate(x) for x in json.loads(f.read_text(encoding="utf-8"))]


def _save(patient_id: str, items: list[CareCircleMember]) -> None:
    f = _file(patient_id)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        json.dumps([m.model_dump(mode="json") for m in items], ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


def grant(patient_id: str, member: CareCircleMember) -> CareCircleMember:
    """授權必須說明目的（VISION §16 的 WHY）。"""
    if not member.purpose.strip():
        raise ValueError("授權必須說明目的（purpose）")
    items = [m for m in members(patient_id) if not (m.member_id == member.member_id and m.active())]
    items.append(member)
    _save(patient_id, items)
    return member


def revoke(patient_id: str, member_id: str, by: str) -> bool:
    items = members(patient_id)
    hit = False
    now = datetime.now(UTC)
    for m in items:
        if m.member_id == member_id and m.active(now):
            m.revoked_at = now
            m.valid_to = now
            hit = True
    if hit:
        _save(patient_id, items)
        log_access(patient_id, by, "patient", f"revoke:{member_id}")
    return hit


def active_members(patient_id: str, now: datetime | None = None) -> list[CareCircleMember]:
    now = now or datetime.now(UTC)
    return [m for m in members(patient_id) if m.active(now)]


def scopes_for(patient_id: str, who: str | None) -> list[Scope]:
    """Scopes ``who`` currently holds on this record (empty = 未獲授權)."""
    if not who:
        return []
    out: list[Scope] = []
    for m in active_members(patient_id):
        if m.member_id == who:
            for s in m.scopes:
                if s not in out:
                    out.append(s)
    return out


def purpose_of(patient_id: str, who: str | None) -> str:
    for m in active_members(patient_id):
        if m.member_id == who:
            return m.purpose
    return ""


def role_of(patient_id: str, who: str | None) -> CareRole | None:
    for m in active_members(patient_id):
        if m.member_id == who:
            return m.role
    it = whoami(who)
    return it["role"] if it else None


# --- access log ------------------------------------------------------------------------------


def log_access(patient_id: str, who: str | None, role: CareRole | None, what: str) -> None:
    if not who:
        return
    store = get_store()
    if not store.exists(patient_id):
        return
    entry = AccessLogEntry(
        health_id=store.load_profile(patient_id).health_id,
        who=who,
        role=role,
        what=what,
        purpose=purpose_of(patient_id, who) or (DEFAULT_PURPOSE.get(role, "") if role else ""),
        ts=datetime.now(UTC),
    )
    with _log_file(patient_id).open("a", encoding="utf-8") as f:
        f.write(entry.model_dump_json() + "\n")


def access_log(patient_id: str, limit: int = 50) -> list[AccessLogEntry]:
    f = _log_file(patient_id)
    if not f.exists():
        return []
    rows = [
        AccessLogEntry.model_validate_json(x)
        for x in f.read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    return rows[-limit:][::-1]


# --- 登入：以病人為核心，其他人要有病人密碼 ------------------------------------------------


def _code_file(patient_id: str):
    return get_store().dir(patient_id) / "access.json"


def set_access_code(patient_id: str, code: str) -> None:
    """Store only the hash（demo：seed 用出生年）。"""
    f = _code_file(patient_id)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        json.dumps({"sha256": _hashlib.sha256(code.encode()).hexdigest()}), encoding="utf-8"
    )


def check_access_code(patient_id: str, code: str | None) -> bool:
    f = _code_file(patient_id)
    if not f.exists() or not code:
        return False
    return (
        json.loads(f.read_text(encoding="utf-8"))["sha256"]
        == _hashlib.sha256(code.strip().encode()).hexdigest()
    )


def login(who: str, patient_id: str | None, code: str | None, days: int = 1) -> dict[str, Any]:
    """本人：自己的密碼。其他身份：輸入病人密碼 → 若不在 Care Circle 就以該角色預設範圍加入
    （有效 ``days`` 天，granted_by＝病人）；已在圈內則只記一筆 access log。
    回 {who, role, name, patient_id}。"""
    it = whoami(who)
    if not it:
        raise KeyError("unknown identity")
    role: CareRole = it["role"]
    pid = who if role == "patient" else (it.get("patient_id") or patient_id)
    if not pid or not get_store().exists(pid):
        raise ValueError("要先選一位住民")
    if not check_access_code(pid, code):
        raise PermissionError("密碼不對")
    if not scopes_for(pid, who):
        now = datetime.now(UTC)
        grant(
            pid,
            CareCircleMember(
                health_id=get_store().load_profile(pid).health_id,
                member_id=who,
                name=it.get("name", who),
                role=role,
                scopes=DEFAULT_SCOPES[role],
                valid_from=now,
                valid_to=None if role == "patient" else now + _timedelta(days=days),
                granted_by=pid,
                purpose=DEFAULT_PURPOSE[role],
            ),
        )
        log_access(pid, who, role, "login:granted")
    else:
        log_access(pid, who, role, "login")
    return {"who": who, "role": role, "name": it.get("name", who), "patient_id": pid}
