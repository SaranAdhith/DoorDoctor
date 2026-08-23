"""Alert and notification schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..models.enums import AlertSeverity, AlertStatus, NotificationType


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    vitals_id: int | None = None
    alert_type: str
    severity: AlertSeverity
    title: str
    message: str
    breached_parameters: list[dict[str, Any]] = []
    status: AlertStatus
    acknowledged_by: int | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    resolution_note: str | None = None
    sla_minutes: int | None = None
    sla_due_at: datetime | None = None
    sla_breached_at: datetime | None = None
    created_at: datetime


class AlertResolve(BaseModel):
    """What the admin did about an alert (§8, journey 3).

    Optional, so the existing one-click resolve still works. Capped like every
    other free-text field a user can write into.
    """

    note: str | None = Field(default=None, max_length=1000)


class AlertDetailOut(AlertOut):
    patient_name: str | None = None
    nurse_name: str | None = None
    vitals: dict[str, Any] | None = None
    thresholds: list[dict[str, Any]] = []


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    patient_id: int | None = None
    alert_id: int | None = None
    type: NotificationType
    title: str
    message: str
    read: bool
    created_at: datetime
