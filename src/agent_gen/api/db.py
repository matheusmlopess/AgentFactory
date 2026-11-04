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
