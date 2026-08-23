"""A nurse's working day (§4.16).

A shift check-in is the start-of-day equivalent of a visit check-in: the nurse
arrives at their zone hub, and the platform records when and — classified by the
same geofence arithmetic — where.

It is a separate table from `Visit` on purpose. A shift is not a visit: it has
no patient, it is not clinical, and folding it into `visits` would put rows with
a null patient into every query that assumes one.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import LocationStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .nurse import Nurse


class ShiftCheckIn(Base):
    __tablename__ = "shift_checkins"

    id: Mapped[int] = mapped_column(primary_key=True)
    nurse_id: Mapped[int] = mapped_column(ForeignKey("nurses.id"), index=True, nullable=False)
    zone: Mapped[Optional[str]] = mapped_column(String(60), index=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    lat: Mapped[Optional[float]] = mapped_column(Float)
    lng: Mapped[Optional[float]] = mapped_column(Float)
    location_source: Mapped[str] = mapped_column(String(30), default="none", nullable=False)
    location_status: Mapped[LocationStatus] = mapped_column(
        SAEnum(LocationStatus, values_callable=lambda e: [m.value for m in e]),
        default=LocationStatus.UNAVAILABLE,
        nullable=False,
    )
    location_distance_m: Mapped[Optional[float]] = mapped_column(Float)
    location_accuracy_m: Mapped[Optional[float]] = mapped_column(Float)
    location_detail: Mapped[Optional[str]] = mapped_column(String(255))

    note: Mapped[Optional[str]] = mapped_column(String(255))

    nurse: Mapped["Nurse"] = relationship()

    @property
    def is_open(self) -> bool:
        return self.ended_at is None
