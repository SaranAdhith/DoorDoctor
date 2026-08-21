"""Visit scheduling and lifecycle schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..models.enums import VisitStatus


class VisitCreate(BaseModel):
    patient_id: int
    caregiver_id: int | None = None
    scheduled_at: datetime


class VisitAssign(BaseModel):
    caregiver_id: int


class CheckinRequest(BaseModel):
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


class VisitNotesUpdate(BaseModel):
    notes: str = Field(default="", max_length=4000)


class VisitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    caregiver_id: int | None = None
    scheduled_at: datetime
    status: VisitStatus
    checkin_at: datetime | None = None
    checkout_at: datetime | None = None
    location_source: str
    notes: str | None = None


class VisitDetailOut(VisitOut):
    patient: dict[str, Any] | None = None
    caregiver: dict[str, Any] | None = None
    vitals: list[dict[str, Any]] = []
    medications: list[dict[str, Any]] = []
    medication_logs: list[dict[str, Any]] = []
