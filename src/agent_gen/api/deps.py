"""FastAPI dependency: resolve current user from session cookie."""
from fastapi import Cookie, HTTPException, status

from .db import get_conn
from .jwt_utils import decode_token
from .models import User


def get_current_user(session: str | None = Cookie(default=None)) -> User:
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user_id = decode_token(session)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, github_id, github_handle, email, avatar_url, plan FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return User(**dict(row))
