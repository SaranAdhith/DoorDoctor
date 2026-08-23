"""Onboarding progress (§4.15).

Only the steps that **cannot** be derived are stored here. Confirming a
relative's details is an acknowledgement and leaves no other trace, so it gets a
row. Consent, thresholds, the care circle and notification channels are all
provable from their own tables, and `onboarding_service` reads them there.

The distinction is the whole design: a checklist of ticks drifts away from the
thing it claims to describe the first time somebody removes a care circle
member. A step is complete because the thing is true, not because somebody
clicked.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base, now


class OnboardingProgress(Base):
    __tablename__ = "onboarding_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "patient_id", "step", name="uq_onboarding_step"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    step: Mapped[str] = mapped_column(String(40), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
