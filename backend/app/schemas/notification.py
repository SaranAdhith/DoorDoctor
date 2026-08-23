"""Notification preference and delivery-record schemas (§4.18)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationPreferenceUpdate(BaseModel):
    #: Partial: only the channels named are changed, the rest keep their setting.
    channels: dict[str, bool] | None = None
    quiet_hours_enabled: bool | None = None
    quiet_start_hour: int | None = Field(default=None, ge=0, le=23)
    quiet_end_hour: int | None = Field(default=None, ge=0, le=23)


class NotificationPreferenceOut(BaseModel):
    channels: dict[str, bool]
    quiet_hours_enabled: bool
    quiet_start_hour: int
    quiet_end_hour: int
    in_quiet_hours_now: bool
    #: Stated in the payload so the UI cannot imply otherwise.
    critical_always_delivered: bool
    critical_channel_count: int


class DeliveryLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel: str
    recipient: str
    subject: str
    status: str
    detail: str | None = None
    created_at: datetime
