"""Vitals input validation and output schemas.

The numeric bounds are practical input-validation ranges for the software.
They are not clinical guidance.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VitalCreate(BaseModel):
    systolic_bp: float = Field(..., ge=50, le=250, description="mmHg")
    diastolic_bp: float = Field(..., ge=30, le=150, description="mmHg")
    heart_rate: float = Field(..., ge=20, le=250, description="bpm")
    blood_glucose: float = Field(..., ge=20, le=600, description="mg/dL")
    spo2: float = Field(..., ge=50, le=100, description="%")
    temperature: float = Field(..., ge=80, le=115, description="degrees Fahrenheit")
    weight: float = Field(..., ge=20, le=250, description="kg")
    #: Minted by the client before the reading is queued. Replaying the same
    #: token corrects the reading it created rather than recording a second one.
    client_token: str | None = Field(default=None, max_length=64)


class VitalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    visit_id: int | None = None
    systolic_bp: float
    diastolic_bp: float
    heart_rate: float
    blood_glucose: float
    spo2: float
    temperature: float
    weight: float
    threshold_breached: bool
    recorded_at: datetime


class VitalRecordResponse(BaseModel):
    vitals: VitalOut
    threshold_breached: bool
    breached_parameters: list[dict[str, Any]] = []
    alerts_created: list[dict[str, Any]] = []
    #: True when this submission carried a `client_token` that had already been
    #: recorded — the queued-offline case. The reading is returned unchanged and
    #: no second alert is raised.
    replayed: bool = False
