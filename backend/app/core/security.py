"""Password hashing and JWT helpers."""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt

from ..config import settings

# bcrypt only consumes the first 72 bytes of a password.
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt.

    The work factor comes from `settings.bcrypt_rounds`, whose default is 12 and
    whose only other caller is the test suite. A hash is self-describing — the
    cost is encoded in the string — so lowering the factor for tests does not
    invalidate anything hashed at a different one, and `verify_password` needs
    no knowledge of the setting at all.
    """
    payload = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    return bcrypt.hashpw(payload, salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time check of a plaintext password against a stored hash."""
    try:
        payload = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(payload, password_hash.encode("utf-8"))
    except (ValueError, TypeError):  # malformed hash
        return False


def create_access_token(subject: int, role: str, expires_minutes: Optional[int] = None) -> str:
    """Issue a signed JWT access token for a user id / role pair."""
    minutes = expires_minutes if expires_minutes is not None else settings.jwt_expire_minutes
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """Return the token claims, or None when the token is invalid or expired."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None


PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
PASSWORD_RULE = "At least 8 characters, including one letter and one number."


def password_problem(password: str) -> Optional[str]:
    """Return why a password is unacceptable, or None when it is fine.

    One function so the reset endpoint and any later signup cannot drift apart.
    `frontend/src/lib/password.ts` mirrors these rules for inline feedback; this
    one is the authority.
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
    # bcrypt reads 72 bytes; the cap keeps the truncation from being a surprise.
    if len(password) > PASSWORD_MAX_LENGTH:
        return f"Password must be at most {PASSWORD_MAX_LENGTH} characters."
    if not any(character.isalpha() for character in password):
        return "Password must include at least one letter."
    if not any(character.isdigit() for character in password):
        return "Password must include at least one number."
    return None
