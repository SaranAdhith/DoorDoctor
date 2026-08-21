"""Patients under care and their monitoring thresholds."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import PatientStatus, VitalMetric

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .alert import Alert
    from .medication import Medication
    from .user import User
    from .visit import Visit
    from .vital import Vital


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    age: Mapped[int] = mapped_column(nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    emergency_contact: Mapped[Optional[str]] = mapped_column(String(120))
    family_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    status: Mapped[PatientStatus] = mapped_column(
        SAEnum(PatientStatus, values_callable=lambda e: [m.value for m in e]),
        default=PatientStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now, nullable=False)

    family_user: Mapped["User"] = relationship(back_populates="patients")
    visits: Mapped[list["Visit"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    vitals: Mapped[list["Vital"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    medications: Mapped[list["Medication"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    thresholds: Mapped[list["PatientThreshold"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )


class PatientThreshold(Base):
    __tablename__ = "patient_thresholds"
    __table_args__ = (UniqueConstraint("patient_id", "metric", name="uq_patient_metric"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    metric: Mapped[VitalMetric] = mapped_column(
        SAEnum(VitalMetric, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    low_threshold: Mapped[Optional[float]] = mapped_column(Float)
    high_threshold: Mapped[Optional[float]] = mapped_column(Float)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="thresholds")
