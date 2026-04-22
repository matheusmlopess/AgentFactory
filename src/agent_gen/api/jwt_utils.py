"""JWT session helpers. HS256-signed, httpOnly cookie transport."""
import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
_ALGORITHM = "HS256"
_EXPIRE_DAYS = 30
COOKIE_NAME = "session"


def create_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=_EXPIRE_DAYS)
    return jwt.encode({"sub": user_id, "exp": expire}, _SECRET, algorithm=_ALGORITHM)


def decode_token(token: str) -> str | None:
    """Return user_id if token valid, else None."""
    try:
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
