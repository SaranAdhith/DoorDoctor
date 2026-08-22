"""Escalation events and the parallel-notification timeline (§4.9).

RECORDED: the escalation ladder is **108 → nurse → admin**. Phase 7 pinned that
order in the assistant's emergency intent; `core/clinical.ESCALATION_LADDER`
states it once so the assistant, the on-screen emergency block and this timeline
cannot drift apart. SLA durations are `ASSUMED`.

**The timeline is data, not prose.** "We notified everyone" is a promise; one
`EscalationStep` per recipient per channel with its own timestamp is a record.
Steps that went out at the same time share a `sequence`, so the UI can draw a
fan-out rather than implying a queue that was worked one at a time.
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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import (
    AlertSeverity,
    EscalationStatus,
    EscalationStepStatus,
    EscalationTrigger,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .patient import Patient
    from .user import User


class EscalationEvent(Base):
    __tablename__ = "escalation_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    trigger: Mapped[EscalationTrigger] = mapped_column(
        SAEnum(EscalationTrigger, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    trigger_id: Mapped[Optional[int]] = mapped_column(Integer)
    alert_id: Mapped[Optional[int]] = mapped_column(ForeignKey("alerts.id"), index=True)
    severity: Mapped[AlertSeverity] = mapped_column(
        SAEnum(AlertSeverity, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    status: Mapped[EscalationStatus] = mapped_column(
        SAEnum(EscalationStatus, values_callable=lambda e: [m.value for m in e]),
        default=EscalationStatus.OPEN,
        index=True,
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)
    # Stored, not computed at render time. A booking that breached last week must
    # still say so after the SLA constants are edited.
    sla_due_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    sla_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    breached_sla: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    resolved_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text)

    patient: Mapped["Patient"] = relationship(back_populates="escalations")
    steps: Mapped[list["EscalationStep"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="EscalationStep.sequence, EscalationStep.id",
    )

    @property
    def is_open(self) -> bool:
        return self.status != EscalationStatus.RESOLVED


class EscalationStep(Base):
    """One contact attempt: who, on what channel, when, and what came of it."""

    __tablename__ = "escalation_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("escalation_events.id"), index=True, nullable=False
    )
    # Steps taken at the same moment share a sequence. That is what makes the
    # timeline render as parallel contact rather than as a serial queue.
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    actor: Mapped[str] = mapped_column(String(60), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    target: Mapped[str] = mapped_column(String(160), nullable=False)
    recipient_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    status: Mapped[EscalationStepStatus] = mapped_column(
        SAEnum(EscalationStepStatus, values_callable=lambda e: [m.value for m in e]),
        default=EscalationStepStatus.PENDING,
        nullable=False,
    )
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    delivery_log_id: Mapped[Optional[int]] = mapped_column(ForeignKey("delivery_log.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)

    event: Mapped["EscalationEvent"] = relationship(back_populates="steps")
