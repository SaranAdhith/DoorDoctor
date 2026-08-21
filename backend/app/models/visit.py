"""Scheduled nurse visits and their lifecycle state."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import VisitStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .nurse import Nurse
    from .medication import MedicationLog
    from .patient import Patient
    from .vital import Vital


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    nurse_id: Mapped[Optional[int]] = mapped_column(ForeignKey("nurses.id"), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    status: Mapped[VisitStatus] = mapped_column(
        SAEnum(VisitStatus, values_callable=lambda e: [m.value for m in e]),
        default=VisitStatus.SCHEDULED,
        nullable=False,
    )
    checkin_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    checkout_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    checkin_lat: Mapped[Optional[float]] = mapped_column(Float)
    checkin_lng: Mapped[Optional[float]] = mapped_column(Float)
    location_source: Mapped[str] = mapped_column(String(30), default="demo/unverified", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="visits")
    nurse: Mapped[Optional["Nurse"]] = relationship(back_populates="visits")
    vitals: Mapped[list["Vital"]] = relationship(back_populates="visit", cascade="all, delete-orphan")
    medication_logs: Mapped[list["MedicationLog"]] = relationship(
        back_populates="visit", cascade="all, delete-orphan"
    )

    @property
    def is_editable(self) -> bool:
        """Completed / cancelled visits are immutable health records in this MVP."""
        return self.status in (VisitStatus.SCHEDULED, VisitStatus.IN_PROGRESS)
