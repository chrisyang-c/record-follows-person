"""KNOWN_ISSUES #18: an open intake session expires after SESSION_EXPIRY_H hours or on a new
Taiwan-local day; open_session then closes it (closed_reason=expired) and starts a fresh one."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from record import conversation as conv


def _fresh(pid: str) -> conv.SessionState:
    conv.close_session(pid, reason="test")
    return conv.open_session(pid)


def test_session_within_window_is_kept(records_root):
    s = _fresh("P001")
    assert conv.open_session("P001").session_id == s.session_id
    assert conv.is_expired(s) is None


def test_session_older_than_expiry_hours_is_replaced(records_root):
    s = _fresh("P001")
    s.started = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
    conv.save_session("P001", s)
    n = conv.open_session("P001")
    assert n.session_id != s.session_id and n.phase == "intake"
    old = [m for m in conv.messages("P001") if m.session_id == s.session_id and m.role == "system"]
    assert old and "自動結束" in old[-1].text and old[-1].meta["expired"].startswith("超過")


def test_session_started_on_previous_taiwan_day_is_replaced(records_root):
    s = _fresh("P001")
    # 23:30 Taipei yesterday (= 15:30 UTC yesterday); still < 4h ago only if now is early
    now = datetime.now(UTC)
    yesterday_late = (now.astimezone(conv.TAIPEI) - timedelta(days=1)).replace(
        hour=23, minute=30, second=0, microsecond=0
    )
    s.started = yesterday_late.astimezone(UTC).isoformat()
    conv.save_session("P001", s)
    why = conv.is_expired(s, now)
    assert why in ("跨日", f"超過 {conv.get_settings().SESSION_EXPIRY_H} 小時")
    assert conv.open_session("P001").session_id != s.session_id


def test_close_session_records_reason(records_root):
    _fresh("P001")
    conv.close_session("P001", reason="confirmed")
    assert conv.session("P001").closed_reason == "confirmed"
