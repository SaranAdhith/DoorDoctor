"""Hospital coordination requests and their SLA clock (§4.3).

Nothing about hospital coordination was recorded beyond that it exists, so every
value here comes from `core/clinical.py` marked `ASSUMED`.

**No hospital partnerships are modelled.** DoorDoctor is pre-launch and a partner
list would be invented traction. A booking records the hospital the family or the
admin *named*; the coordination itself is a human doing it, and the row is how
the family can see that it is being done.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import HospitalBookingStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .escalation import EscalationEvent
    from .patient import Patient
    from .user import User


class HospitalBooking(Base):
    __tablename__ = "hospital_bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    hospital_name: Mapped[str] = mapped_column(String(160), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    ambulance_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    preferred_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[HospitalBookingStatus] = mapped_column(
        SAEnum(HospitalBookingStatus, values_callable=lambda e: [m.value for m in e]),
        default=HospitalBookingStatus.REQUESTED,
        index=True,
        nullable=False,
    )
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime, default=now, index=True, nullable=False
    )
    # An ambulance request runs on the critical clock, a routine referral does
    # not. Both are stored rather than recomputed — see `EscalationEvent`.
    sla_due_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    sla_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    breached_sla: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    confirmation_detail: Mapped[Optional[str]] = mapped_column(Text)
    handled_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    escalation_event_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("escalation_events.id"), index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)

    patient: Mapped["Patient"] = relationship(back_populates="hospital_bookings")
    requested_by_user: Mapped["User"] = relationship(foreign_keys=[requested_by])
    escalation_event: Mapped[Optional["EscalationEvent"]] = relationship()
