"""Forgotten-password flow (§2.1).

Shape of the thing:

* 32 random bytes from `secrets.token_urlsafe`, stored only as a sha256 digest.
* 30-minute expiry, single use, and a new request invalidates the older links.
* The API tells no one whether an account exists — that answer is the same for
  every email, and the work done differs only in what is delivered.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..core.exceptions import BadRequestError
from ..core.security import hash_password
from ..database import now
from ..models import DeliveryChannelName, PasswordResetToken, User
from . import notification_delivery

logger = logging.getLogger("doordoctor.auth")

TOKEN_BYTES = 32
TOKEN_TTL = timedelta(minutes=30)

# One message for an unknown, expired, spent and malformed token alike. Telling
# them apart would let someone probe which tokens exist.
INVALID_TOKEN_MESSAGE = "This reset link is invalid or has expired. Please request a new one."


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def reset_url(raw_token: str) -> str:
    return f"{settings.frontend_base_url.rstrip('/')}/reset-password?token={raw_token}"


def request_reset(db: Session, *, email: str, ip: str | None = None) -> str | None:
    """Issue and deliver a reset link. Returns the raw token, or None if no account matched.

    The caller must not vary its response on that return value — it exists so
    the development-only `debug_reset_url` can be populated, and for tests.
    """
    normalised = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalised))

    if user is None or not user.is_active:
        # Same amount of nothing for an unknown address and a disabled account.
        logger.info("Password reset requested for an address with no active account")
        db.commit()
        return None

    _invalidate_outstanding(db, user.id)

    raw_token = secrets.token_urlsafe(TOKEN_BYTES)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=now() + TOKEN_TTL,
            requested_ip=ip,
        )
    )

    link = reset_url(raw_token)
    notification_delivery.deliver(
        db,
        channel=DeliveryChannelName.EMAIL,
        user=user,
        subject="Reset your DoorDoctor password",
        body=(
            f"Hello {user.name},\n\n"
            "We received a request to reset the password on your DoorDoctor account. "
            f"Open the link below within 30 minutes to choose a new one:\n\n{link}\n\n"
            "If you did not ask for this, you can ignore this message — your password "
            "has not changed.\n\n"
            "DoorDoctor"
        ),
        sensitive=[link, raw_token],
    )

    db.commit()
    # The link itself, for a developer running without a mail provider. The
    # stored delivery record has it redacted.
    logger.info("Password reset link generated: %s", link)
    return raw_token


def find_usable_token(db: Session, raw_token: str) -> PasswordResetToken | None:
    if not raw_token:
        return None
    record = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw_token))
    )
    if record is None or not record.is_usable():
        return None
    return record


def is_token_valid(db: Session, raw_token: str) -> bool:
    """Lets the reset screen say "this link has expired" before asking for a password."""
    return find_usable_token(db, raw_token) is not None


def reset_password(db: Session, *, raw_token: str, new_password: str) -> User:
    record = find_usable_token(db, raw_token)
    if record is None:
        raise BadRequestError(INVALID_TOKEN_MESSAGE)

    user = db.get(User, record.user_id)
    if user is None or not user.is_active:  # pragma: no cover - orphaned token
        raise BadRequestError(INVALID_TOKEN_MESSAGE)

    user.password_hash = hash_password(new_password)
    record.used_at = now()
    # Flushed before the bulk update so this token is already spent when the
    # statement below runs and the ORM object cannot fall out of step with the
    # row. Any *other* link that was still open dies here too: a password change
    # is exactly when someone else's outstanding link must stop working.
    db.flush()
    _invalidate_outstanding(db, user.id)

    notification_delivery.deliver(
        db,
        channel=DeliveryChannelName.EMAIL,
        user=user,
        subject="Your DoorDoctor password was changed",
        body=(
            f"Hello {user.name},\n\n"
            "The password on your DoorDoctor account was just changed. If this was you, "
            "there is nothing to do.\n\n"
            "If it was not, contact DoorDoctor immediately.\n\n"
            "DoorDoctor"
        ),
    )

    db.commit()
    logger.info("Password reset completed for user %s", user.id)
    return user


def _invalidate_outstanding(db: Session, user_id: int) -> None:
    """Stamp every still-open token for this user as used."""
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now())
    )
