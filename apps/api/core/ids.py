from __future__ import annotations

import secrets
from datetime import UTC, datetime


def new_id(prefix: str, ts: datetime | None = None) -> str:
    ts = ts or datetime.now(UTC)
    return f"{prefix}_{ts.strftime('%Y%m%dT%H%M%S')}_{secrets.token_hex(3)}"


def now() -> datetime:
    return datetime.now(UTC)
