"""Care managers, their caseloads and every interaction they log (§4.4).

RECORDED: a care manager runs **1:20 shared** or **1:10 dedicated**. Those ratios
live in `core/pricing.py` (`RATIO_SHARED` / `RATIO_DEDICATED`) beside the
entitlement that decides which kind a plan grants, and are enforced here.

**A care manager is a profile on an admin user, not a fourth `UserRole`** —
decided with the founder on 2026-08-22. The three-way route guard
(family / nurse / admin) survives untouched, and so does every existing
authorization test.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import CareChannel, CareDirection, CareManagerKind

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .patient import Patient
    from .user import User


class CareManager(Base):
    """One admin user, acting as a care manager, with a capacity."""

    __tablename__ = "care_managers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True, nullable=False
    )
    kind: Mapped[CareManagerKind] = mapped_column(
        SAEnum(CareManagerKind, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    # Seeded from `pricing.RATIO_SHARED` / `RATIO_DEDICATED` — recorded values.
    # Stored rather than derived so a manager can be given a reduced caseload
    # without changing what the plan promises everybody else.
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    languages: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)

    user: Mapped["User"] = relationship()
    assignments: Mapped[list["CareAssignment"]] = relationship(
        back_populates="care_manager", cascade="all, delete-orphan"
    )

    @property
    def active_assignments(self) -> list["CareAssignment"]:
        return [a for a in self.assignments if a.ended_at is None]


class CareAssignment(Base):
    """A patient in a care manager's caseload. Ended, never deleted — a handover is history."""

    __tablename__ = "care_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    care_manager_id: Mapped[int] = mapped_column(
        ForeignKey("care_managers.id"), index=True, nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    ended_reason: Mapped[Optional[str]] = mapped_column(String(200))

    patient: Mapped["Patient"] = relationship(back_populates="care_assignments")
    care_manager: Mapped["CareManager"] = relationship(back_populates="assignments")


class CareInteraction(Base):
    """Something a care manager actually did, logged against the patient."""

    __tablename__ = "care_interactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    care_manager_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("care_managers.id"), index=True
    )
    logged_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    channel: Mapped[CareChannel] = mapped_column(
        SAEnum(CareChannel, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    direction: Mapped[CareDirection] = mapped_column(
        SAEnum(CareDirection, values_callable=lambda e: [m.value for m in e]),
        default=CareDirection.OUTBOUND,
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(String(160), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    minutes: Mapped[Optional[int]] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)
    # Family-visible by default: a care manager's job is to be seen doing it.
    # Cleared for internal handover notes.
    visible_to_family: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="care_interactions")
    care_manager: Mapped[Optional["CareManager"]] = relationship()


__table_args_note__ = """One active assignment per patient is enforced in
`care_service`, not by a unique constraint: `ended_at IS NULL` partial indexes
are not portable to SQLite, and a constraint that only exists on Postgres is a
constraint nobody can rely on."""
