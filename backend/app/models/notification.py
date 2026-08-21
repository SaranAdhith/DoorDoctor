"""In-app notification records (no external delivery in this MVP)."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base, now
from .enums import NotificationType


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    patient_id: Mapped[Optional[int]] = mapped_column(ForeignKey("patients.id"))
    alert_id: Mapped[Optional[int]] = mapped_column(ForeignKey("alerts.id"))
    type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, values_callable=lambda e: [m.value for m in e]),
        default=NotificationType.ALERT,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)
