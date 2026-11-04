"""
SQLite database layer: users, hashed license keys, API tokens and the agent registry.
DATABASE_URL=sqlite:///./data/agentfactory.db  (default)
Swap for postgresql:// via env var when scaling.
"""
import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path

_DB_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/agentfactory.db")


def _db_path() -> str:
    if _DB_URL.startswith("sqlite:///"):
        path = _DB_URL[len("sqlite:///"):]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        return path
    raise ValueError(f"Unsupported DATABASE_URL scheme: {_DB_URL!r}. Only sqlite:// is supported currently.")


@contextmanager
def get_conn():
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


DDL = """
CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    github_id       INTEGER UNIQUE NOT NULL,
    github_handle   TEXT NOT NULL,
    email           TEXT NOT NULL,
    avatar_url      TEXT NOT NULL DEFAULT '',
    plan            TEXT NOT NULL DEFAULT 'free',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- License keys are stored only as sha256 hashes; the plaintext is shown once at issue time.
CREATE TABLE IF NOT EXISTS license_keys (
    key_hash        TEXT PRIMARY KEY,
    plan            TEXT NOT NULL,
    user_id         TEXT REFERENCES users(id),
    created_at      TEXT NOT NULL,
    revoked_at      TEXT
);

-- API tokens for the CLI/harness (Bearer). Only the sha256 hash is stored.
CREATE TABLE IF NOT EXISTS api_tokens (
    token_hash      TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id),
    label           TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    expires_at      TEXT,
    last_used_at    TEXT,
    revoked_at      TEXT
);

-- Registry: one row per unit (owned by its first publisher) and one per immutable version.
CREATE TABLE IF NOT EXISTS registry_units (
    name            TEXT PRIMARY KEY,
    owner_id        TEXT NOT NULL REFERENCES users(id),
    description     TEXT NOT NULL DEFAULT '',
    tags            TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
-- Device-code login for the CLI/harness (RFC 8628 style). The device code is stored hashed.
CREATE TABLE IF NOT EXISTS device_codes (
    device_hash     TEXT PRIMARY KEY,
    user_code       TEXT UNIQUE NOT NULL,
    created_at      TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    approved_by     TEXT REFERENCES users(id),
    consumed_at     TEXT
);
CREATE TABLE IF NOT EXISTS registry_versions (
    name            TEXT NOT NULL REFERENCES registry_units(name),
    version         TEXT NOT NULL,
    sha256          TEXT NOT NULL,
    size_bytes      INTEGER NOT NULL,
    published_by    TEXT NOT NULL REFERENCES users(id),
    published_at    TEXT NOT NULL,
    PRIMARY KEY (name, version)
);
"""

PLAN_RANK = {"free": 0, "pro": 1, "team": 2, "enterprise": 3}


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def issue_license_key(plan: str, user_id: str | None = None) -> str:
    """Create a random key for *plan*, store its hash, and return the plaintext once."""
    if plan not in PLAN_RANK:
        raise ValueError(f"Unknown plan {plan!r}; expected one of {', '.join(PLAN_RANK)}")
    key = f"afk_{secrets.token_urlsafe(32)}"
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO license_keys (key_hash, plan, user_id, created_at) VALUES (?, ?, ?, ?)",
            (hash_key(key), plan, user_id, now),
        )
    return key


def revoke_license_key(key: str) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE license_keys SET revoked_at = ? WHERE key_hash = ? AND revoked_at IS NULL",
            (now, hash_key(key)),
        )
        return cur.rowcount > 0


def license_plan(key: str) -> str | None:
    """Plan of an active key, or None for unknown/revoked keys."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT plan FROM license_keys WHERE key_hash = ? AND revoked_at IS NULL",
            (hash_key(key),),
        ).fetchone()
    return row["plan"] if row else None


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(DDL)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def issue_api_token(user_id: str, label: str = "", ttl_days: int | None = 90) -> str:
    """Create a Bearer token for *user_id*; only its hash is stored. Returns the plaintext once."""
    token = f"aft_{secrets.token_urlsafe(32)}"
    expires = None
    if ttl_days:
        from datetime import timedelta
        expires = (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat()
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
            raise ValueError(f"unknown user id {user_id!r}")
        conn.execute(
            "INSERT INTO api_tokens (token_hash, user_id, label, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            (hash_key(token), user_id, label, _now(), expires),
        )
    return token


def api_token_user(token: str) -> str | None:
    """users.id for an active, unexpired token (and record its use), else None."""
    now = _now()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT user_id, expires_at FROM api_tokens WHERE token_hash = ? AND revoked_at IS NULL",
            (hash_key(token),),
        ).fetchone()
        if row is None or (row["expires_at"] and row["expires_at"] <= now):
            return None
        conn.execute("UPDATE api_tokens SET last_used_at = ? WHERE token_hash = ?", (now, hash_key(token)))
        return row["user_id"]


def revoke_api_token(token: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE api_tokens SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
            (_now(), hash_key(token)),
        )
        return cur.rowcount > 0


# ---------------------------------------------------------------- device login

_USER_CODE_ALPHABET = "BCDFGHJKLMNPQRSTVWXZ"  # no vowels (no accidental words), no 0/O/1/I confusion
MAX_PENDING_DEVICE_CODES = 1000


def _user_code() -> str:
    raw = "".join(secrets.choice(_USER_CODE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def normalize_user_code(code: str) -> str:
    raw = "".join(ch for ch in code.upper() if ch.isalnum())
    return f"{raw[:4]}-{raw[4:]}" if len(raw) == 8 else code.strip().upper()


def create_device_code(ttl_seconds: int = 600) -> tuple[str, str]:
    """Start a login: returns (device_code, user_code). Expired codes are purged; pending codes are capped."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    device_code = secrets.token_urlsafe(32)
    with get_conn() as conn:
        conn.execute("DELETE FROM device_codes WHERE expires_at <= ?", (now.isoformat(),))
        pending = conn.execute("SELECT COUNT(*) FROM device_codes WHERE consumed_at IS NULL").fetchone()[0]
        if pending >= MAX_PENDING_DEVICE_CODES:
            raise OverflowError("too many pending logins; try again in a few minutes")
        for _ in range(5):
            user_code = _user_code()
            try:
                conn.execute(
                    "INSERT INTO device_codes (device_hash, user_code, created_at, expires_at) VALUES (?, ?, ?, ?)",
                    (hash_key(device_code), user_code, now.isoformat(),
                     (now + timedelta(seconds=ttl_seconds)).isoformat()),
                )
                return device_code, user_code
            except sqlite3.IntegrityError:
                continue
    raise RuntimeError("could not allocate a user code")


def approve_device_code(user_code: str, user_id: str) -> bool:
    """Signed-in user confirms the code shown by the CLI. False when unknown, expired or already used."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE device_codes SET approved_by = ? WHERE user_code = ? AND approved_by IS NULL "
            "AND consumed_at IS NULL AND expires_at > ?",
            (user_id, normalize_user_code(user_code), _now()),
        )
        return cur.rowcount > 0


def poll_device_code(device_code: str, label: str = "device login") -> tuple[str, str | None, str | None]:
    """Returns (status, token, user_id). status: pending | authorized | expired.

    The token is issued exactly once: the first poll after approval consumes the code.
    """
    now = _now()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT approved_by, expires_at, consumed_at FROM device_codes WHERE device_hash = ?",
            (hash_key(device_code),),
        ).fetchone()
        if row is None or row["consumed_at"] or row["expires_at"] <= now:
            return "expired", None, None
        if not row["approved_by"]:
            return "pending", None, None
        cur = conn.execute(
            "UPDATE device_codes SET consumed_at = ? WHERE device_hash = ? AND consumed_at IS NULL",
            (now, hash_key(device_code)),
        )
        if cur.rowcount == 0:
            return "expired", None, None
        user_id = row["approved_by"]
    return "authorized", issue_api_token(user_id, label), user_id
