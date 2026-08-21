"""Patient, threshold and dashboard schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..models.enums import PatientStatus, VitalMetric


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    age: int
    gender: str
    address: str
    emergency_contact: str | None = None
    family_user_id: int
    status: PatientStatus
    created_at: datetime


class ThresholdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    metric: VitalMetric
    low_threshold: float | None = None
    high_threshold: float | None = None
    enabled: bool


class ThresholdUpdate(BaseModel):
    metric: VitalMetric
    low_threshold: float | None = Field(default=None, ge=0)
    high_threshold: float | None = Field(default=None, ge=0)
    enabled: bool = True


class CaregiverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    email: str
    phone: str | None = None
    credential: str
    verification_status: str
    status: str


class AdherenceOut(BaseModel):
    """`percentage` is null when nothing has been logged yet (shown as `No data`)."""

    percentage: int | None = None
    administered: int = 0
    skipped: int = 0
    refused: int = 0
    total: int = 0


class DashboardOut(BaseModel):
    patient: PatientOut
    current_vitals: dict[str, Any] | None = None
    vitals_history: list[dict[str, Any]] = []
    medication_adherence: AdherenceOut
    medications: list[dict[str, Any]] = []
    upcoming_visits: list[dict[str, Any]] = []
    recent_visits: list[dict[str, Any]] = []
    active_alerts: list[dict[str, Any]] = []
    caregiver: CaregiverOut | None = None
    overall_status: str
    thresholds: list[ThresholdOut] = []
