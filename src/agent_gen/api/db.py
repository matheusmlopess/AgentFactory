"""
SQLite database layer: users and hashed license keys.
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
