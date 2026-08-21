"""Medication schedules and per-visit administration logs."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import MedicationLogStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .patient import Patient
    from .visit import Visit


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    dosage: Mapped[str] = mapped_column(String(60), nullable=False)
    frequency: Mapped[str] = mapped_column(String(60), nullable=False)
    scheduled_time: Mapped[str] = mapped_column(String(5), nullable=False)  # HH:MM
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="medications")
    logs: Mapped[list["MedicationLog"]] = relationship(
        back_populates="medication", cascade="all, delete-orphan"
    )


class MedicationLog(Base):
    __tablename__ = "medication_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    medication_id: Mapped[int] = mapped_column(ForeignKey("medications.id"), index=True, nullable=False)
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visits.id"), index=True)
    status: Mapped[MedicationLogStatus] = mapped_column(
        SAEnum(MedicationLogStatus, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(String(255))
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)
    recorded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    medication: Mapped["Medication"] = relationship(back_populates="logs")
    visit: Mapped[Optional["Visit"]] = relationship(back_populates="medication_logs")
