"""Doctor video consults (§4.6).

RECORDED: Premium includes 2 consults per month (`core/pricing.py`). Everything
else — duration, how late one may be cancelled, who the doctor is — is `ASSUMED`
and lives in `core/clinical.py`.

This is the **first genuinely enforced quota** in the codebase. `subscription_id`
is stored on the row so a cancellation can hand the allowance back to the same
meter it was taken from, even if the family has changed plan since.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import ConsultStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .patient import Patient
    from .subscription import Subscription
    from .user import User


class Consult(Base):
    __tablename__ = "consults"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    subscription_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subscriptions.id"), index=True
    )
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ConsultStatus] = mapped_column(
        SAEnum(ConsultStatus, values_callable=lambda e: [m.value for m in e]),
        default=ConsultStatus.SCHEDULED,
        index=True,
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # No doctor roster is modelled. This records the name the consult was booked
    # under; inventing a staffed calendar would be inventing staff.
    doctor_name: Mapped[str] = mapped_column(String(120), nullable=False)
    # True when cancelling gave the allowance back — see `consult_service`.
    quota_released: Mapped[bool] = mapped_column(default=False, nullable=False)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="consults")
    subscription: Mapped[Optional["Subscription"]] = relationship()
    requested_by_user: Mapped["User"] = relationship(foreign_keys=[requested_by])
