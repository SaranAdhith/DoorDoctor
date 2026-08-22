"""Record of every message the platform handed to a delivery channel.

This build has no email/SMS provider, so the channels simulate. The *record* is
real: it is what an admin reviews when a family member says "I never got the
alert", and it is the table Phase 10's channel routing and preferences extend.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base, now
from .enums import DeliveryChannelName, DeliveryStatus


class DeliveryLog(Base):
    __tablename__ = "delivery_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True)
    channel: Mapped[DeliveryChannelName] = mapped_column(
        SAEnum(DeliveryChannelName, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    # Secrets are redacted before they reach this column — see
    # `services/notification_delivery.deliver`.
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DeliveryStatus] = mapped_column(
        SAEnum(DeliveryStatus, values_callable=lambda e: [m.value for m in e]),
        default=DeliveryStatus.SIMULATED,
        nullable=False,
    )
    detail: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)
