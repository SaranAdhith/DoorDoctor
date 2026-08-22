"""Connected devices and the readings they push in (§4.8).

RECORDED: SpO2 below 90% or a heart rate outside range triggers "the documented
three actions". The range and the three actions themselves are `ASSUMED` and
live in `core/clinical.py`.

**A device stores a sha256 of its key, never the key.** Same discipline as Phase
3's password-reset tokens, for the same reason: a leaked `devices` table must not
be a list of working credentials. The plaintext key is returned exactly once, at
registration, and cannot be recovered afterwards — only rotated.

`POST /ingest/device-readings` is the second least-trusted caller in this
codebase after the public lead form. Every cap it is subject to is in
`core/clinical.py`, and no device-supplied string ever reaches a log.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import DeviceKind, DeviceStatus, VitalMetric

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .patient import Patient


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    kind: Mapped[DeviceKind] = mapped_column(
        SAEnum(DeviceKind, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    serial: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    # sha256 of the API key. Indexed because every ingest call looks a device up
    # by exactly this, and a table scan per reading is a denial-of-service the
    # device fleet performs on itself.
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[DeviceStatus] = mapped_column(
        SAEnum(DeviceStatus, values_callable=lambda e: [m.value for m in e]),
        default=DeviceStatus.ACTIVE,
        nullable=False,
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="devices")
    readings: Mapped[list["DeviceReading"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )


class DeviceReading(Base):
    """One measurement from a device.

    Deliberately **not** a `Vital` row. A `Vital` is a full observation a nurse
    recorded and signed for during a visit; this is one unattended number from a
    consumer sensor. Merging them would put unverified data into the clinical
    record and into the threshold engine, and would make the family's chart
    unable to say which was which.
    """

    __tablename__ = "device_readings"
    __table_args__ = (
        # A device retrying a batch must not double-record. The same device
        # reporting the same metric at the same instant is the same reading.
        UniqueConstraint("device_id", "metric", "recorded_at", name="uq_device_reading"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True, nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    metric: Mapped[VitalMetric] = mapped_column(
        SAEnum(VitalMetric, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
    # True when this reading crossed a recorded wearable trigger and set the
    # three actions running. Stored so the timeline can point at the cause.
    triggered: Mapped[bool] = mapped_column(default=False, nullable=False)

    device: Mapped["Device"] = relationship(back_populates="readings")
