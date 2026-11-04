"""
GitHub OAuth endpoints + /auth/me + /auth/logout.
Session contract: GitHub OAuth -> httpOnly JWT cookie (see docs/MULTI-REPO-WORKFLOW.md).
"""
import os
import secrets
import time
import uuid
from urllib.parse import urlencode
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse

from .. import db as _db
from ..db import get_conn
from ..deps import _load_user, get_current_user, get_publisher
from ..jwt_utils import COOKIE_NAME, create_token
from ..models import (
    DeviceApproveRequest,
    DeviceCodeResponse,
    DevicePollRequest,
    DevicePollResponse,
    User,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_GITHUB_CLIENT_ID     = os.environ.get("GITHUB_CLIENT_ID", "")
_GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
_GITHUB_REDIRECT_URI  = os.environ.get(
    "GITHUB_REDIRECT_URI", "http://localhost:8000/auth/github/callback"
)
_WEBAPP_URL = os.environ.get("WEBAPP_URL", "http://localhost:5173")

# In-memory CSRF state store: state -> expiry (epoch seconds). Fine for a single process;
# replace with Redis when running multiple API replicas. Entries expire and the store is
# capped, so unauthenticated /auth/github calls cannot grow it without bound.
_STATE_TTL_SECONDS = 600
_MAX_PENDING_STATES = 10_000
_pending_states: dict[str, float] = {}


def _remember_state(state: str) -> None:
    now = time.time()
    for key in [k for k, exp in _pending_states.items() if exp <= now]:
        del _pending_states[key]
    while len(_pending_states) >= _MAX_PENDING_STATES:
        del _pending_states[next(iter(_pending_states))]  # oldest first (insertion order)
    _pending_states[state] = now + _STATE_TTL_SECONDS


def _consume_state(state: str) -> bool:
    expiry = _pending_states.pop(state, None)
    return expiry is not None and expiry > time.time()


@router.get("/github")
def github_login() -> RedirectResponse:
    """Redirect user to GitHub OAuth authorization page."""
    if not _GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub OAuth not configured (GITHUB_CLIENT_ID not set)",
        )
    state = secrets.token_urlsafe(32)
    _remember_state(state)
    query = urlencode({
        "client_id": _GITHUB_CLIENT_ID,
        "redirect_uri": _GITHUB_REDIRECT_URI,
        "scope": "read:user user:email",
        "state": state,
    })
    return RedirectResponse(url=f"https://github.com/login/oauth/authorize?{query}")


@router.get("/github/callback")
def github_callback(code: str, state: str, response: Response) -> RedirectResponse:
    """
    GitHub redirects here after user grants access.
    Exchanges code for access_token, upserts User, issues JWT session cookie.
    """
    # CSRF validation
    if not _consume_state(state):
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
    if token_resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="GitHub token exchange failed")
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
def get_me(current_user: User = Depends(get_publisher)) -> User:
    """Return the current user (session cookie or `Authorization: Bearer <api token>`). 401 otherwise."""
    return current_user


# ---------------------------------------------------------------- CLI device login (#201)

_DEVICE_TTL_SECONDS = 600


def _poll_interval() -> float:
    return float(os.environ.get("DEVICE_POLL_INTERVAL", "5"))


@router.post("/cli/device", response_model=DeviceCodeResponse)
def cli_device() -> DeviceCodeResponse:
    """Start a CLI login. Show `user_code`, send the user to `verification_uri`, then poll."""
    try:
        device_code, user_code = _db.create_device_code(_DEVICE_TTL_SECONDS)
    except OverflowError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from None
    verify = f"{_WEBAPP_URL.rstrip('/')}/device"
    return DeviceCodeResponse(
        device_code=device_code, user_code=user_code, verification_uri=verify,
        verification_uri_complete=f"{verify}?{urlencode({'code': user_code})}",
        expires_in=_DEVICE_TTL_SECONDS, interval=_poll_interval(),
    )


def _poll(device_code: str) -> DevicePollResponse:
    state, token, user_id = _db.poll_device_code(device_code)
    user = _load_user(user_id) if user_id else None
    return DevicePollResponse(status=state, token=token, user=user)


@router.get("/cli/poll", response_model=DevicePollResponse)
def cli_poll_get(device_code: str = Query(..., min_length=10, max_length=128)) -> DevicePollResponse:
    """Poll a login (harness form). `authorized` carries the API token exactly once."""
    return _poll(device_code)


@router.post("/cli/poll", response_model=DevicePollResponse)
def cli_poll_post(body: DevicePollRequest) -> DevicePollResponse:
    """Poll a login (CLI form: the device code stays out of URLs and access logs)."""
    return _poll(body.device_code)


@router.post("/cli/approve")
def cli_approve(body: DeviceApproveRequest, current_user: User = Depends(get_current_user)) -> dict:
    """The webapp's /device page calls this for the signed-in user (session cookie only)."""
    if not _db.approve_device_code(body.user_code, current_user.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="code unknown, expired or already used")
    return {"approved": True}


@router.post("/cli/logout")
def cli_logout(authorization: str | None = Header(default=None)) -> dict:
    """Revoke the Bearer token the CLI is using. Idempotent."""
    if authorization and authorization.lower().startswith("bearer "):
        _db.revoke_api_token(authorization.split(" ", 1)[1].strip())
    return {}


@router.post("/logout")
def logout(response: Response) -> dict:
    """Clear the session cookie."""
    response.delete_cookie(key=COOKIE_NAME, samesite="lax")
    return {}
