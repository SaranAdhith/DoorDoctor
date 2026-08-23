"""Scheduled nurse visits and their lifecycle state."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import LocationStatus, VisitStatus

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
    # --- Phase 10, verified location (§4.11) ------------------------------
    # `location_source` is the *provenance* of the fix — where the coordinates
    # came from. `location_status` is what the platform is willing to claim
    # about it. They are different facts and the old "demo/unverified" was
    # conflating them into an apology.
    location_source: Mapped[str] = mapped_column(String(30), default="none", nullable=False)
    location_status: Mapped[LocationStatus] = mapped_column(
        SAEnum(LocationStatus, values_callable=lambda e: [m.value for m in e]),
        default=LocationStatus.UNAVAILABLE,
        nullable=False,
    )
    # Stored so `verified` is arithmetic a reader can re-run, not a badge. Both
    # stay None when there was nothing to measure.
    location_distance_m: Mapped[Optional[float]] = mapped_column(Float)
    location_accuracy_m: Mapped[Optional[float]] = mapped_column(Float)
    location_detail: Mapped[Optional[str]] = mapped_column(String(255))
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
