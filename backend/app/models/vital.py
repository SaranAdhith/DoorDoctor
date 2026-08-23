"""Vital sign readings recorded during a visit."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .alert import Alert
    from .patient import Patient
    from .visit import Visit


class Vital(Base):
    __tablename__ = "vitals"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visits.id"), index=True)
    systolic_bp: Mapped[float] = mapped_column(Float, nullable=False)
    diastolic_bp: Mapped[float] = mapped_column(Float, nullable=False)
    heart_rate: Mapped[float] = mapped_column(Float, nullable=False)
    blood_glucose: Mapped[float] = mapped_column(Float, nullable=False)
    spo2: Mapped[float] = mapped_column(Float, nullable=False)
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_breached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # --- Phase 10, offline-tolerant capture (§4.16) ----------------------
    # A token minted by the nurse's device before the reading is queued. A visit
    # in a basement flat is recorded offline and replayed when signal returns,
    # and a replay must correct the record rather than double it. Unique per
    # visit, so a genuinely different reading in the same visit is still allowed.
    client_token: Mapped[Optional[str]] = mapped_column(String(64), index=True)

    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="vitals")
    visit: Mapped[Optional["Visit"]] = relationship(back_populates="vitals")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="vitals")
