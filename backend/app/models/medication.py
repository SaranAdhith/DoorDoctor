"""Medication schedules, dose logs, organiser fills and the change history.

Phase 10 (§4.12) adds three things to what a family can see about medicines:
the photograph the nurse took when the dose was given, the pill organiser
somebody filled last Sunday, and **why the dose is different from last month**.

`MedicationChange` is append-only history. A stopped medication is a row, not a
missing row — "why is she on half the dose now" is a question a current-state
table cannot answer, and it is one of the most common questions a family
actually asks.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import MedicationChangeKind, MedicationLogStatus, PillOrganiserStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .attachment import Attachment
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
    changes: Mapped[list["MedicationChange"]] = relationship(
        back_populates="medication", cascade="all, delete-orphan", order_by="MedicationChange.id"
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

    # The photograph the nurse took as they gave the dose. Optional forever:
    # a phone with no camera permission must not stop a dose being recorded.
    photo_attachment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("attachments.id"))

    medication: Mapped["Medication"] = relationship(back_populates="logs")
    visit: Mapped[Optional["Visit"]] = relationship(back_populates="medication_logs")
    photo: Mapped[Optional["Attachment"]] = relationship()


class MedicationChange(Base):
    """One edit to a medication, kept forever.

    Written by `medication_service` and by nothing else, so the history cannot
    develop gaps that look like periods when nothing changed.
    """

    __tablename__ = "medication_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    medication_id: Mapped[int] = mapped_column(
        ForeignKey("medications.id"), index=True, nullable=False
    )
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    kind: Mapped[MedicationChangeKind] = mapped_column(
        SAEnum(MedicationChangeKind, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    # Both sides of the change, as they were shown. Strings rather than
    # structured fields because "5 mg" and "half a tablet in the morning" are
    # both real prescriptions and the history has to hold either.
    previous_value: Mapped[Optional[str]] = mapped_column(String(120))
    new_value: Mapped[Optional[str]] = mapped_column(String(120))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    changed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    changed_by_name: Mapped[str] = mapped_column(String(120), default="DoorDoctor", nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)

    medication: Mapped["Medication"] = relationship(back_populates="changes")


class PillOrganiserFill(Base):
    """A weekly organiser, filled.

    The ₹199 add-on finally has a buyer. Priced *per month*, so the charge lands
    on the first fill of a billing month and every later fill that month is
    free — the family bought the service, not the plastic.
    """

    __tablename__ = "pill_organiser_fills"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visits.id"), index=True)
    filled_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    filled_by_name: Mapped[str] = mapped_column(String(120), default="DoorDoctor", nullable=False)
    status: Mapped[PillOrganiserStatus] = mapped_column(
        SAEnum(PillOrganiserStatus, values_callable=lambda e: [m.value for m in e]),
        default=PillOrganiserStatus.FILLED,
        nullable=False,
    )
    compartments_filled: Mapped[int] = mapped_column(default=0, nullable=False)
    compartments_total: Mapped[int] = mapped_column(default=0, nullable=False)
    covers_until: Mapped[Optional[date]] = mapped_column(Date)
    note: Mapped[Optional[str]] = mapped_column(String(255))
    # Set when this fill was the one that carried the month's charge. Null means
    # it rode on a charge already made, which is a different thing from free.
    invoice_line_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoice_lines.id"))
    filled_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)
