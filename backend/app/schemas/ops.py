"""Operations schemas (§4.16, §4.17)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models.enums import LocationStatus


class HubCheckInRequest(BaseModel):
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0, le=100_000)
    note: str | None = Field(default=None, max_length=255)


class ShiftCheckInOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nurse_id: int
    zone: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    location_status: LocationStatus
    location_distance_m: float | None = None
    location_accuracy_m: float | None = None
    location_detail: str | None = None
    note: str | None = None
    is_open: bool
