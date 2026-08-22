"""Doctor consult schemas (§4.6)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConsultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    patient_name: str | None = None
    scheduled_for: datetime
    duration_minutes: int
    status: str
    reason: str
    doctor_name: str
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    quota_released: bool = False
    completed_at: datetime | None = None
    summary: str | None = None
    created_at: datetime


class ConsultCreate(BaseModel):
    scheduled_for: datetime
    reason: str = Field(default="", max_length=1000)


class ConsultCancel(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ConsultComplete(BaseModel):
    summary: str | None = Field(default=None, max_length=2000)


class ConsultAllowanceOut(BaseModel):
    """What the plan allows and what is left.

    Served from the same `quota_status` the booking is refused against, so the
    number on the screen and the number in the refusal are one number.
    """

    subscribed: bool
    included: int | None = None
    used: int = 0
    remaining: int | None = None
    unlimited: bool = False
    period_start: datetime | None = None
    period_end: datetime | None = None
    duration_minutes: int
    cancellation_hours: int
