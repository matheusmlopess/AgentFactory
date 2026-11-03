"""JWT session helpers. HS256-signed, httpOnly cookie transport.

The signing secret comes from ``JWT_SECRET`` and is read on every call, so tests and
long-running processes see the current value. Outside development (``AGENTFACTORY_ENV``
is ``dev``/``development``/``test``) the API refuses to run without a real secret.
"""
import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

_ALGORITHM = "HS256"
_EXPIRE_DAYS = 30
_MIN_SECRET_LEN = 32
_DEV_ENVS = frozenset({"dev", "development", "test"})
# Placeholders shipped in examples or old defaults: never valid outside development.
_PLACEHOLDERS = frozenset({
    "dev-secret-change-in-production",
    "change_me_generate_a_real_secret",
})
COOKIE_NAME = "session"


class InsecureConfigError(RuntimeError):
    """Raised when the API would run with a guessable signing secret."""


def is_dev_env() -> bool:
    return os.environ.get("AGENTFACTORY_ENV", "").strip().lower() in _DEV_ENVS


def _secret() -> str:
    secret = os.environ.get("JWT_SECRET", "")
    if is_dev_env():
        return secret or "dev-secret-change-in-production"
    if len(secret) < _MIN_SECRET_LEN or secret in _PLACEHOLDERS:
        raise InsecureConfigError(
            f"JWT_SECRET must be set to a random value of at least {_MIN_SECRET_LEN} characters "
            '(python3 -c "import secrets; print(secrets.token_hex(32))"). '
            "For local development only, set AGENTFACTORY_ENV=dev."
        )
    return secret


def check_config() -> None:
    """Fail fast at startup instead of on the first login."""
    _secret()


def create_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=_EXPIRE_DAYS)
    return jwt.encode({"sub": user_id, "exp": expire}, _secret(), algorithm=_ALGORITHM)


def decode_token(token: str) -> str | None:
    """Return user_id if token valid, else None."""
    try:
        payload = jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
