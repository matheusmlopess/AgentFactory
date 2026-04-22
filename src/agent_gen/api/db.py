"""
SQLite database layer. Single users table.
DATABASE_URL=sqlite:///./data/agentfactory.db  (default)
Swap for postgresql:// via env var when scaling.
"""
import os
import sqlite3
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
"""


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(DDL)
