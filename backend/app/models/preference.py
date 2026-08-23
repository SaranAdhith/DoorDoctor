"""How one person wants to be reached (§4.18).

One row per user. The per-channel switches live in a JSON column rather than
four boolean columns, the same shape as `Plan.entitlements`: `DeliveryChannelName`
is the source of truth for what channels exist, and adding one should be a
default lookup rather than a migration.

Quiet hours are **off by default**. That is deliberate and not laziness: a
platform that silently stops messaging a family between 21:00 and 07:00 because
of a default they never chose is a platform that decides on their behalf when
their mother's alert can wait.
"""

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.ops import CHANNEL_DEFAULT_ENABLED, QUIET_HOURS_END, QUIET_HOURS_START
from ..database import Base, now
from .enums import DeliveryChannelName


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True, nullable=False
    )
    channels_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quiet_start_hour: Mapped[int] = mapped_column(default=QUIET_HOURS_START, nullable=False)
    quiet_end_hour: Mapped[int] = mapped_column(default=QUIET_HOURS_END, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now, onupdate=now, nullable=False
    )

    @property
    def channels(self) -> dict[str, bool]:
        try:
            stored = json.loads(self.channels_json or "{}")
        except json.JSONDecodeError:  # pragma: no cover - defensive
            stored = {}
        return {name: bool(stored.get(name, CHANNEL_DEFAULT_ENABLED.get(name, False)))
                for name in (channel.value for channel in DeliveryChannelName)}

    @channels.setter
    def channels(self, value: dict[str, bool]) -> None:
        self.channels_json = json.dumps({key: bool(flag) for key, flag in value.items()})

    def is_enabled(self, channel: DeliveryChannelName) -> bool:
        return self.channels.get(channel.value, False)

    def in_quiet_hours(self, at: Optional[datetime] = None) -> bool:
        """Whether `at` falls inside this person's quiet window.

        The window wraps midnight far more often than not — 21:00 to 07:00 is
        the ordinary case — so the comparison is written for the wrapping case
        first rather than treating it as an edge.
        """
        if not self.quiet_hours_enabled:
            return False
        hour = (at or now()).hour
        start, end = self.quiet_start_hour, self.quiet_end_hour
        if start == end:
            return False
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end
