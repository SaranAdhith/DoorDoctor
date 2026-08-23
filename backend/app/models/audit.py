"""The append-only audit log.

RECORDED: this log is append-only. It is enforced **in the mapper**, not by
convention — a `before_update` and a `before_delete` listener raise, so a future
service that tries to tidy an entry fails loudly instead of quietly rewriting
history. `tests/test_privacy.py` proves both.

It is also the one table an erasure does not empty. Deleting the log would
remove the evidence that the erasure happened, which is the opposite of what a
family asking for an erasure is owed.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text, event
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from ..database import Base, now
from .enums import AuditAction, UserRole


class AppendOnlyError(RuntimeError):
    """Raised when something tries to change or remove an audit entry."""


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)

    # Nullable because the actor may be gone: an erasure can remove the account
    # that requested it, and the entry must survive that. `actor_label` is the
    # denormalised name, frozen at write time for the same reason.
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True)
    actor_role: Mapped[Optional[UserRole]] = mapped_column(
        SAEnum(UserRole, values_callable=lambda e: [m.value for m in e])
    )
    actor_label: Mapped[str] = mapped_column(String(120), default="system", nullable=False)

    action: Mapped[AuditAction] = mapped_column(
        SAEnum(AuditAction, values_callable=lambda e: [m.value for m in e]), index=True, nullable=False
    )
    subject_type: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_id: Mapped[Optional[int]] = mapped_column()
    # Kept as a plain id rather than a foreign key: the patient row may be gone
    # by the time somebody reads the entry describing its erasure.
    patient_id: Mapped[Optional[int]] = mapped_column(index=True)

    # One sentence, written for an admin to read. Never a reading, never a
    # credential, never a token — the log is reviewed by people who are not
    # necessarily entitled to the record it describes.
    detail: Mapped[Optional[str]] = mapped_column(Text)


@event.listens_for(AuditEvent, "before_update", propagate=True)
def _no_update(_mapper: Mapper, _connection, _target: AuditEvent) -> None:  # pragma: no cover - raises
    raise AppendOnlyError("Audit entries cannot be modified.")


@event.listens_for(AuditEvent, "before_delete", propagate=True)
def _no_delete(_mapper: Mapper, _connection, _target: AuditEvent) -> None:  # pragma: no cover - raises
    raise AppendOnlyError("Audit entries cannot be deleted.")
