"""Follow-up tasks (§4.2, §4.7, §4.8, §4.9).

RECORDED: an abnormal lab result raises an alert **and a 24-hour follow-up
task**. Screenings, wearable breaches and escalations create tasks too, so this
is general from the start — `source_type` + `source_id` rather than a
`lab_order_id`. A lab-specific table would have been rewritten twice inside this
same phase.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import TaskKind, TaskStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .patient import Patient
    from .user import User


class FollowUpTask(Base):
    __tablename__ = "follow_up_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    kind: Mapped[TaskKind] = mapped_column(
        SAEnum(TaskKind, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, values_callable=lambda e: [m.value for m in e]),
        default=TaskStatus.OPEN,
        index=True,
        nullable=False,
    )
    # What created it. A plain string plus an id rather than seven nullable FKs:
    # the task queue never joins back, it only links out to a screen.
    source_type: Mapped[Optional[str]] = mapped_column(String(40))
    source_id: Mapped[Optional[int]] = mapped_column(Integer)
    assigned_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True)
    completed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completion_note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="tasks")
    assigned_user: Mapped[Optional["User"]] = relationship(foreign_keys=[assigned_user_id])

    @property
    def is_overdue(self) -> bool:
        return self.status == TaskStatus.OPEN and self.due_at < now()
