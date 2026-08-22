"""The Senior Safety Score (§4.5).

RECORDED: the score is deterministic, runs 0–100, and a drop of 10 or more
points inside 30 days raises an alert. Every weight and band is `ASSUMED` and
lives in `core/clinical.py`.

**Every component is stored, not just the total.** A score a family cannot have
explained to them is worse than no score, because it looks authoritative. The
row below therefore keeps the individual weighted components and the share of
the scale that actually had data behind it, so the number on the screen can
always be taken apart in front of the person it describes.
"""

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import SafetyBand

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .patient import Patient


class SafetyScore(Base):
    """One calculation. History is kept, because the *change* is the alert."""

    __tablename__ = "safety_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    band: Mapped[SafetyBand] = mapped_column(
        SAEnum(SafetyBand, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    # How much of the 100-point scale had data behind it. A component with no
    # data is dropped and the rest are rescaled; storing the coverage is what
    # makes that rescaling visible instead of flattering.
    covered_weight: Mapped[int] = mapped_column(Integer, nullable=False)
    components_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    # The score this one is compared against for the recorded 30-day drop rule.
    previous_score: Mapped[Optional[int]] = mapped_column(Integer)
    delta: Mapped[Optional[int]] = mapped_column(Integer)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="safety_scores")

    @property
    def components(self) -> list[dict[str, Any]]:
        try:
            return json.loads(self.components_json or "[]")
        except json.JSONDecodeError:  # pragma: no cover - defensive
            return []

    @components.setter
    def components(self, value: list[dict[str, Any]]) -> None:
        self.components_json = json.dumps(value)
