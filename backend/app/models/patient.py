"""Patients under care and their monitoring thresholds."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import PatientStatus, VitalMetric

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .alert import Alert
    from .care import CareAssignment, CareInteraction
    from .device import Device
    from .escalation import EscalationEvent
    from .hospital import HospitalBooking
    from .lab import LabOrder
    from .medication import Medication
    from .report import Report
    from .safety import SafetyScore
    from .screening import Screening
    from .task import FollowUpTask
    from .telemedicine import Consult
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
    # --- Phase 10, operations (§4.11, §4.17) -----------------------------
    # Phase 5 kept the zone as a lookup table in `seed/demo_data.py` and left a
    # note to lift it into a column when something needed to *query* by it. The
    # admin zone view is that something.
    zone: Mapped[Optional[str]] = mapped_column(String(60), index=True)
    # The centre of the geofence. Without these a check-in can only ever be
    # classified `unavailable`, which is the honest answer and is exactly what
    # `visit_service` returns for a patient whose home was never located.
    home_lat: Mapped[Optional[float]] = mapped_column(Float)
    home_lng: Mapped[Optional[float]] = mapped_column(Float)
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
    reports: Mapped[list["Report"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )

    # --- Phase 9, clinical (§4.2-4.9) ------------------------------------
    # All cascade delete-orphan: a deleted patient must not leave a lab result,
    # a device reading or an open escalation behind. SQLite does not enforce
    # foreign keys unless asked, so the ORM cascade is what actually holds here.
    safety_scores: Mapped[list["SafetyScore"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    lab_orders: Mapped[list["LabOrder"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["FollowUpTask"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    consults: Mapped[list["Consult"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    care_assignments: Mapped[list["CareAssignment"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    care_interactions: Mapped[list["CareInteraction"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    screenings: Mapped[list["Screening"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    devices: Mapped[list["Device"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    escalations: Mapped[list["EscalationEvent"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    hospital_bookings: Mapped[list["HospitalBooking"]] = relationship(
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
