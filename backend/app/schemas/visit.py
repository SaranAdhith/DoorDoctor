"""Visit scheduling and lifecycle schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..models.enums import LocationStatus, VisitStatus


class VisitCreate(BaseModel):
    patient_id: int
    nurse_id: int | None = None
    scheduled_at: datetime


class VisitAssign(BaseModel):
    nurse_id: int


class CheckinRequest(BaseModel):
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    # The browser's own estimate of how good the fix is, in metres. Optional,
    # because not every device reports it — but when it is present and worse
    # than the geofence, the check-in is classified `unavailable` rather than
    # verified against a circle the fix cannot resolve.
    accuracy_m: float | None = Field(default=None, ge=0, le=100_000)


class VisitNotesUpdate(BaseModel):
    notes: str = Field(default="", max_length=4000)


class VisitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    nurse_id: int | None = None
    scheduled_at: datetime
    status: VisitStatus
    checkin_at: datetime | None = None
    checkout_at: datetime | None = None
    location_source: str
    location_status: LocationStatus
    location_distance_m: float | None = None
    location_accuracy_m: float | None = None
    location_detail: str | None = None
    notes: str | None = None


class VisitDetailOut(VisitOut):
    patient: dict[str, Any] | None = None
    nurse: dict[str, Any] | None = None
    vitals: list[dict[str, Any]] = []
    medications: list[dict[str, Any]] = []
    medication_logs: list[dict[str, Any]] = []
