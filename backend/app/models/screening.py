"""Structured screenings — PHQ-2 today (§4.7).

PHQ-2 is a **published instrument**. Its two questions, its 0–3 answer scale, its
0–6 total and its cutoff of 3 come from the instrument, not from this project,
and are marked `INSTRUMENT` in `core/clinical.py` rather than `ASSUMED`.

**Both answers are stored, not only the total.** The two questions ask different
things — loss of interest and low mood — and a 3 made of (3, 0) is not the same
clinical picture as one made of (1, 2). Storing only the sum throws that away.

A positive screen means *screen further*. It creates a follow-up task for a
human and never an alert: a low mood score is not a threshold breach, and
dressing it as one would be a diagnosis this platform is not entitled to make.
"""

import json
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import ScreeningInstrument

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .patient import Patient
    from .user import User
    from .visit import Visit


class Screening(Base):
    __tablename__ = "screenings"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    instrument: Mapped[ScreeningInstrument] = mapped_column(
        SAEnum(ScreeningInstrument, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    answers_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False)
    positive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    administered_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visits.id"), index=True)
    administered_at: Mapped[datetime] = mapped_column(
        DateTime, default=now, index=True, nullable=False
    )
    note: Mapped[Optional[str]] = mapped_column(Text)

    patient: Mapped["Patient"] = relationship(back_populates="screenings")
    administered_by_user: Mapped["User"] = relationship(foreign_keys=[administered_by])
    visit: Mapped[Optional["Visit"]] = relationship()

    @property
    def answers(self) -> list[int]:
        try:
            return [int(a) for a in json.loads(self.answers_json or "[]")]
        except (json.JSONDecodeError, TypeError, ValueError):  # pragma: no cover - defensive
            return []

    @answers.setter
    def answers(self, value: list[int]) -> None:
        self.answers_json = json.dumps([int(v) for v in value])
