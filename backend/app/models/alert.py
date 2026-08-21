"""Monitoring alerts raised by the threshold engine."""

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import AlertSeverity, AlertStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .patient import Patient
    from .vital import Vital


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    vitals_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vitals.id"), index=True)
    alert_type: Mapped[str] = mapped_column(String(60), default="vital_threshold_breach", nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(
        SAEnum(AlertSeverity, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    breached_parameters_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        SAEnum(AlertStatus, values_callable=lambda e: [m.value for m in e]),
        default=AlertStatus.ACTIVE,
        nullable=False,
    )
    acknowledged_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="alerts")
    vitals: Mapped[Optional["Vital"]] = relationship(back_populates="alerts")

    @property
    def breached_parameters(self) -> list[dict[str, Any]]:
        try:
            return json.loads(self.breached_parameters_json or "[]")
        except json.JSONDecodeError:  # pragma: no cover - defensive
            return []

    @breached_parameters.setter
    def breached_parameters(self, value: list[dict[str, Any]]) -> None:
        self.breached_parameters_json = json.dumps(value)
