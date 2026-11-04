"""FastAPI dependencies: resolve the current user from the session cookie or a Bearer API token."""
from fastapi import Cookie, Header, HTTPException, status

from .db import api_token_user, get_conn
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


def _load_user(user_id: str) -> User | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, github_id, github_handle, email, avatar_url, plan FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return User(**dict(row)) if row else None


def get_publisher(
    authorization: str | None = Header(default=None),
    session: str | None = Cookie(default=None),
) -> User:
    """CLI/harness send `Authorization: Bearer <api token>`; the webapp sends the session cookie."""
    user_id = None
    if authorization and authorization.lower().startswith("bearer "):
        user_id = api_token_user(authorization.split(" ", 1)[1].strip())
    elif session:
        user_id = decode_token(session)
    user = _load_user(user_id) if user_id else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in first: `agentfactory-gen login` (CLI) or GitHub sign-in (webapp).",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
