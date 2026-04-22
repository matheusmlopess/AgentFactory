"""
GitHub OAuth endpoints + /auth/me + /auth/logout.
Implements the contract from docs/FEATURE-AUTH.md §6.
"""
import os
import secrets
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse

from ..db import get_conn
from ..deps import get_current_user
from ..jwt_utils import COOKIE_NAME, create_token
from ..models import User

router = APIRouter(prefix="/auth", tags=["auth"])

_GITHUB_CLIENT_ID     = os.environ.get("GITHUB_CLIENT_ID", "")
_GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
_GITHUB_REDIRECT_URI  = os.environ.get(
    "GITHUB_REDIRECT_URI", "http://localhost:8000/auth/github/callback"
)
_WEBAPP_URL = os.environ.get("WEBAPP_URL", "http://localhost:5173")

# In-memory CSRF state store — fine for single process.
# Replace with Redis when running multiple API replicas.
_pending_states: dict[str, bool] = {}


@router.get("/github")
def github_login() -> RedirectResponse:
    """Redirect user to GitHub OAuth authorization page."""
    if not _GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub OAuth not configured (GITHUB_CLIENT_ID not set)",
        )
    state = secrets.token_urlsafe(32)
    _pending_states[state] = True
    url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={_GITHUB_CLIENT_ID}"
        f"&redirect_uri={_GITHUB_REDIRECT_URI}"
        f"&scope=read:user,user:email"
        f"&state={state}"
    )
    return RedirectResponse(url=url)


@router.get("/github/callback")
def github_callback(code: str, state: str, response: Response) -> RedirectResponse:
    """
    GitHub redirects here after user grants access.
    Exchanges code for access_token, upserts User, issues JWT session cookie.
    """
    # CSRF validation
    if not _pending_states.pop(state, False):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    # Exchange code for access_token
    token_resp = httpx.post(
        "https://github.com/login/oauth/access_token",
        json={
            "client_id": _GITHUB_CLIENT_ID,
            "client_secret": _GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": _GITHUB_REDIRECT_URI,
        },
        headers={"Accept": "application/json"},
        timeout=10,
    )
    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GitHub token exchange failed")

    # Fetch user profile
    user_resp = httpx.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
        timeout=10,
    )
    if user_resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GitHub user fetch failed")
    gh_user = user_resp.json()

    # Resolve primary email if not public
    email: str = gh_user.get("email") or ""
    if not email:
        emails_resp = httpx.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
            timeout=10,
        )
        if emails_resp.status_code == 200:
            for entry in emails_resp.json():
                if entry.get("primary") and entry.get("verified"):
                    email = entry["email"]
                    break

    now = datetime.now(timezone.utc).isoformat()
    github_id: int = gh_user["id"]
    handle: str = gh_user["login"]
    avatar: str = gh_user.get("avatar_url", "")

    # Upsert user in DB
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id, plan FROM users WHERE github_id = ?", (github_id,)
        ).fetchone()
        if existing:
            user_id = existing["id"]
            conn.execute(
                "UPDATE users SET github_handle=?, email=?, avatar_url=?, updated_at=? WHERE id=?",
                (handle, email, avatar, now, user_id),
            )
        else:
            user_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO users (id, github_id, github_handle, email, avatar_url, plan, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'free', ?, ?)",
                (user_id, github_id, handle, email, avatar, now, now),
            )

    # Issue JWT session cookie and redirect to webapp
    jwt_token = create_token(user_id)
    redirect = RedirectResponse(url=_WEBAPP_URL, status_code=302)
    redirect.set_cookie(
        key=COOKIE_NAME,
        value=jwt_token,
        httponly=True,
        samesite="lax",
        secure=_WEBAPP_URL.startswith("https"),
        max_age=60 * 60 * 24 * 30,  # 30 days
    )
    return redirect


@router.get("/me", response_model=User)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return the current authenticated user. 401 if no valid session."""
    return current_user


@router.post("/logout")
def logout(response: Response) -> dict:
    """Clear the session cookie."""
    response.delete_cookie(key=COOKIE_NAME, samesite="lax")
    return {}
