"""User accounts (family members, nurses, admins)."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import UserRole

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .assistant import AssistantMessage
    from .nurse import Nurse
    from .patient import Patient


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now, nullable=False)

    patients: Mapped[list["Patient"]] = relationship(back_populates="family_user")
    nurse_profile: Mapped[Optional["Nurse"]] = relationship(back_populates="user", uselist=False)
    # Cascades: an assistant exchange is meaningless once its only reader is gone.
    assistant_messages: Mapped[list["AssistantMessage"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
