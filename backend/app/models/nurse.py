"""Nurse profiles linked to nurse user accounts."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import NurseStatus, VerificationStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .user import User
    from .visit import Visit


class Nurse(Base):
    __tablename__ = "nurses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True, nullable=False)
    credential: Mapped[str] = mapped_column(String(50), nullable=False)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, values_callable=lambda e: [m.value for m in e]),
        default=VerificationStatus.PENDING,
        nullable=False,
    )
    status: Mapped[NurseStatus] = mapped_column(
        SAEnum(NurseStatus, values_callable=lambda e: [m.value for m in e]),
        default=NurseStatus.ACTIVE,
        nullable=False,
    )
    zone: Mapped[Optional[str]] = mapped_column(String(60), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)

    user: Mapped["User"] = relationship(back_populates="nurse_profile")
    visits: Mapped[list["Visit"]] = relationship(back_populates="nurse")
