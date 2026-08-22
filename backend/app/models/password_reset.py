"""Single-use password reset tokens.

The raw token is never stored. It is generated once, handed to the delivery
layer, and kept only as a sha256 digest — a database reader cannot mint a
working reset link out of this table.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base, now


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Stamped both when the token is spent and when a newer request supersedes
    # it, so "usable" is a single condition rather than two flags.
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    requested_ip: Mapped[Optional[str]] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)

    def is_usable(self, at: Optional[datetime] = None) -> bool:
        return self.used_at is None and self.expires_at > (at or now())
