"""Authentication use cases."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.exceptions import UnauthorizedError
from ..core.security import create_access_token, verify_password
from ..models import User


def authenticate(db: Session, email: str, password: str) -> User:
    """Verify credentials and return the user, or raise 401.

    The same message is returned for an unknown email and a wrong password so the
    API does not confirm which accounts exist.
    """
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Invalid email or password.")
    if not user.is_active:
        raise UnauthorizedError("This account is inactive.")
    return user


def issue_token(user: User) -> str:
    return create_access_token(subject=user.id, role=user.role.value)
