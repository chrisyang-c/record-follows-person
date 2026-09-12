"""Local account credentials, opaque sessions, login throttles, and security audit.

The private SQLite file belongs to the configured RecordStore. Credentials never contain
roles: the identity registry is checked on every authentication and session lookup.
Callers must still enforce patient membership, resource scopes, purpose, and CSRF before
authorizing an operation. Audit entries use an append interface, not an immutable ledger.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import secrets
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from record.store import get_store

PASSWORD_ITERATIONS = 600_000
SESSION_SECONDS = 8 * 60 * 60
LOGIN_WINDOW_SECONDS = 15 * 60
ACCOUNT_ATTEMPT_LIMIT = 5
PEER_ATTEMPT_LIMIT = 30
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 1024
_ROLES = {"patient", "family", "caregiver", "nurse", "doctor"}
_DUMMY_SALT = hashlib.sha256(b"rfp-unknown-credential-salt").digest()[:16]
_DUMMY_HASH = hashlib.sha256(b"rfp-unknown-credential-hash").digest()
_SCHEMA = """
CREATE TABLE IF NOT EXISTS credentials (
    who TEXT PRIMARY KEY,
    salt BLOB NOT NULL,
    password_hash BLOB NOT NULL,
    iterations INTEGER NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    who TEXT NOT NULL,
    purpose TEXT NOT NULL,
    patient_id TEXT,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    revoked_at REAL
);
CREATE INDEX IF NOT EXISTS sessions_who ON sessions(who);
CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_hash TEXT NOT NULL,
    peer_hash TEXT NOT NULL,
    ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS attempts_account ON login_attempts(account_hash, ts);
CREATE INDEX IF NOT EXISTS attempts_peer ON login_attempts(peer_hash, ts);
CREATE TABLE IF NOT EXISTS security_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    patient_id TEXT,
    who TEXT,
    action TEXT NOT NULL,
    outcome TEXT NOT NULL,
    purpose TEXT,
    resource TEXT,
    peer TEXT,
    details TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_patient ON security_audit(patient_id, id);
"""


class AuthenticationRateLimited(PermissionError):
    def __init__(self, retry_after: int):
        super().__init__("Too many sign-in attempts. Try again later.")
        self.retry_after = max(1, retry_after)


def _now() -> float:
    return time.time()


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, UTC).isoformat()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _identity(who: str) -> dict[str, Any] | None:
    # Imported lazily so seed/management code can use these helpers without an import cycle.
    from record import care_circle

    identity = care_circle.identities().get(who)
    if (
        not isinstance(identity, dict)
        or identity.get("role") not in _ROLES
        or not isinstance(identity.get("name"), str)
        or not identity["name"].strip()
        or identity.get("disabled")
        or identity.get("active") is False
    ):
        return None
    return {**identity, "who": who}


@contextmanager
def _database() -> Iterator[sqlite3.Connection]:
    root = get_store().root
    root.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(root / "_security.sqlite3", timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        connection.executescript(_SCHEMA)
        with connection:
            yield connection
    finally:
        connection.close()


def _redacted(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if any(
                    sensitive in str(key).lower()
                    for sensitive in ("password", "token", "secret", "cookie", "authorization")
                )
                else _redacted(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redacted(item) for item in value]
    return value


def _audit(
    connection: sqlite3.Connection,
    patient_id: str | None,
    who: str | None,
    action: str,
    *,
    outcome: str,
    purpose: str | None = None,
    resource: str | None = None,
    peer: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    connection.execute(
        "INSERT INTO security_audit "
        "(ts, patient_id, who, action, outcome, purpose, resource, peer, details) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            _now(),
            patient_id,
            who,
            action,
            outcome,
            purpose,
            resource,
            peer,
            json.dumps(_redacted(details or {}), ensure_ascii=False),
        ),
    )


def audit(
    patient_id: str | None,
    who: str | None,
    action: str,
    *,
    outcome: str,
    purpose: str | None = None,
    resource: str | None = None,
    peer: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Append an event. Never put credentials or clinical payloads in free-text fields."""
    with _database() as connection:
        _audit(
            connection,
            patient_id,
            who,
            action,
            outcome=outcome,
            purpose=purpose,
            resource=resource,
            peer=peer,
            details=details,
        )


def audit_entries(patient_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Return only this patient's newest events; callers enforce access to audit data."""
    with _database() as connection:
        rows = connection.execute(
            "SELECT * FROM security_audit WHERE patient_id = ? ORDER BY id DESC LIMIT ?",
            (patient_id, max(0, min(limit, 1000))),
        ).fetchall()
    return [
        {**dict(row), "ts": _iso(row["ts"]), "details": json.loads(row["details"])} for row in rows
    ]


def set_password(who: str, password: str) -> None:
    """Provision/reset an existing account and revoke its sessions in the same transaction."""
    if not _identity(who):
        raise ValueError("Account must be an existing, enabled identity")
    if (
        not isinstance(password, str)
        or not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH
    ):
        raise ValueError(
            f"Password must contain {MIN_PASSWORD_LENGTH}–{MAX_PASSWORD_LENGTH} characters"
        )
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    now = _now()
    with _database() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT INTO credentials (who, salt, password_hash, iterations, updated_at) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(who) DO UPDATE SET "
            "salt = excluded.salt, password_hash = excluded.password_hash, "
            "iterations = excluded.iterations, updated_at = excluded.updated_at",
            (who, salt, derived, PASSWORD_ITERATIONS, now),
        )
        connection.execute(
            "UPDATE sessions SET revoked_at = ? WHERE who = ? AND revoked_at IS NULL", (now, who)
        )
        _audit(connection, None, who, "credential.set", outcome="success")


def _reserve_attempt(who: str, peer: str, now: float) -> int:
    # Reserve before hashing: concurrent guesses cannot all pass the same remaining slot.
    retry_after = 0
    with _database() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "DELETE FROM login_attempts WHERE ts <= ?", (now - LOGIN_WINDOW_SECONDS,)
        )
        for column, value, limit in (
            ("account_hash", _digest(who), ACCOUNT_ATTEMPT_LIMIT),
            ("peer_hash", _digest(peer), PEER_ATTEMPT_LIMIT),
        ):
            row = connection.execute(
                "SELECT COUNT(*) AS attempts, MIN(ts) AS oldest "
                f"FROM login_attempts WHERE {column} = ?",
                (value,),
            ).fetchone()
            if row["attempts"] >= limit:
                retry_after = max(
                    retry_after, math.ceil(row["oldest"] + LOGIN_WINDOW_SECONDS - now)
                )
        if retry_after:
            _audit(connection, None, who, "login", outcome="rate_limited", peer=peer)
        else:
            cursor = connection.execute(
                "INSERT INTO login_attempts (account_hash, peer_hash, ts) VALUES (?, ?, ?)",
                (_digest(who), _digest(peer), now),
            )
            attempt_id = cursor.lastrowid
    if retry_after:
        raise AuthenticationRateLimited(retry_after)
    assert attempt_id is not None
    return attempt_id


def authenticate(who: str, password: str, peer: str) -> dict[str, Any] | None:
    """Return a current identity or one generic failure; both known/unknown users are throttled.

    The peer must be the server's trusted connection address, not an arbitrary forwarded header.
    Successful attempts release their reservation; failures expire after fifteen minutes.
    """
    attempt_id = _reserve_attempt(who, peer, _now())
    with _database() as connection:
        credential = connection.execute(
            "SELECT * FROM credentials WHERE who = ?", (who,)
        ).fetchone()
    valid_length = isinstance(password, str) and len(password) <= MAX_PASSWORD_LENGTH
    candidate = password if valid_length else "invalid-password-length"
    salt = credential["salt"] if credential else _DUMMY_SALT
    iterations = credential["iterations"] if credential else PASSWORD_ITERATIONS
    expected = credential["password_hash"] if credential else _DUMMY_HASH
    derived = hashlib.pbkdf2_hmac("sha256", candidate.encode("utf-8"), salt, iterations)
    matches = hmac.compare_digest(derived, expected)
    identity = _identity(who)
    success = bool(credential and valid_length and matches and identity)
    with _database() as connection:
        if success:
            connection.execute("DELETE FROM login_attempts WHERE id = ?", (attempt_id,))
        _audit(
            connection, None, who, "login", outcome="success" if success else "denied", peer=peer
        )
    return identity if success else None


def _csrf(token: str) -> str:
    # The public CSRF value cannot reconstruct the secret cookie; neither raw value is stored.
    return hmac.new(token.encode("utf-8"), b"rfp:csrf:v1", hashlib.sha256).hexdigest()


def _session(row: sqlite3.Row, identity: dict[str, Any], token: str) -> dict[str, Any]:
    return {
        "who": row["who"],
        "role": identity["role"],
        "name": identity["name"],
        "purpose": row["purpose"],
        "patient_id": row["patient_id"],
        "created_at": _iso(row["created_at"]),
        "expires_at": _iso(row["expires_at"]),
        "csrf_token": _csrf(token),
    }


def create_session(who: str, purpose: str, patient_id: str | None = None) -> dict[str, Any]:
    """Mint after successful authentication and purpose checks by the trusted caller.

    The raw token is returned only here. Authorization must validate patient context against
    current consent for every request; this context is not itself an access grant.
    """
    identity = _identity(who)
    if not identity:
        raise ValueError("Account must be an existing, enabled identity")
    if not isinstance(purpose, str) or not purpose.strip() or len(purpose) > 256:
        raise ValueError("A nonempty purpose of at most 256 characters is required")
    token = secrets.token_urlsafe(32)
    now = _now()
    with _database() as connection:
        connection.execute("BEGIN IMMEDIATE")
        if not connection.execute("SELECT 1 FROM credentials WHERE who = ?", (who,)).fetchone():
            raise ValueError("Account credentials have not been provisioned")
        connection.execute(
            "INSERT INTO sessions (token_hash, who, purpose, patient_id, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (_digest(token), who, purpose.strip(), patient_id, now, now + SESSION_SECONDS),
        )
        row = connection.execute(
            "SELECT * FROM sessions WHERE token_hash = ?", (_digest(token),)
        ).fetchone()
        _audit(
            connection,
            patient_id,
            who,
            "session.created",
            outcome="success",
            purpose=purpose.strip(),
        )
    return {**_session(row, identity, token), "token": token}


def get_session(token: str | None) -> dict[str, Any] | None:
    if not isinstance(token, str) or not token or len(token) > 512:
        return None
    with _database() as connection:
        row = connection.execute(
            "SELECT * FROM sessions WHERE token_hash = ? AND revoked_at IS NULL AND expires_at > ?",
            (_digest(token), _now()),
        ).fetchone()
    if row is None:
        return None
    identity = _identity(row["who"])
    return _session(row, identity, token) if identity else None


def revoke_session(token: str | None) -> None:
    if not isinstance(token, str) or not token or len(token) > 512:
        return
    with _database() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT * FROM sessions WHERE token_hash = ? AND revoked_at IS NULL", (_digest(token),)
        ).fetchone()
        if row:
            connection.execute(
                "UPDATE sessions SET revoked_at = ? WHERE token_hash = ?", (_now(), _digest(token))
            )
            _audit(
                connection,
                row["patient_id"],
                row["who"],
                "session.revoked",
                outcome="success",
                purpose=row["purpose"],
            )
