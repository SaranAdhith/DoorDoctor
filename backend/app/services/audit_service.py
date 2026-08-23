"""Writes to the append-only audit log. Nothing else may.

`record()` **never commits.** It joins the caller's transaction, so an audited
action that rolls back does not leave behind a log entry claiming it happened —
which would be a worse record than none at all.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.ops import AUDIT_RETENTION_DAYS
from ..database import now
from ..models import AuditAction, AuditEvent, User, UserRole

# Roles whose read of a patient record is worth logging. A family member reading
# their own relative's dashboard is the product working; logging every one of
# those would bury the entry that matters under thousands that do not.
AUDITED_READER_ROLES: frozenset[UserRole] = frozenset({UserRole.NURSE, UserRole.ADMIN})


def record(
    db: Session,
    *,
    action: AuditAction,
    subject_type: str,
    actor: User | None = None,
    subject_id: int | None = None,
    patient_id: int | None = None,
    detail: str | None = None,
) -> AuditEvent:
    entry = AuditEvent(
        actor_user_id=actor.id if actor else None,
        actor_role=actor.role if actor else None,
        actor_label=actor.name if actor else "system",
        action=action,
        subject_type=subject_type,
        subject_id=subject_id,
        patient_id=patient_id,
        detail=detail,
    )
    db.add(entry)
    return entry


def record_view(db: Session, *, actor: User, patient_id: int, what: str) -> AuditEvent | None:
    """Log a read of someone else's record. Returns None when not worth logging."""
    if actor.role not in AUDITED_READER_ROLES:
        return None
    return record(
        db,
        actor=actor,
        action=AuditAction.RECORD_VIEWED,
        subject_type="patient",
        subject_id=patient_id,
        patient_id=patient_id,
        detail=f"Opened {what}.",
    )


def list_events(
    db: Session,
    *,
    patient_id: int | None = None,
    actor_user_id: int | None = None,
    action: AuditAction | None = None,
    limit: int = 100,
) -> list[AuditEvent]:
    query = select(AuditEvent)
    if patient_id is not None:
        query = query.where(AuditEvent.patient_id == patient_id)
    if actor_user_id is not None:
        query = query.where(AuditEvent.actor_user_id == actor_user_id)
    if action is not None:
        query = query.where(AuditEvent.action == action)
    return list(db.scalars(query.order_by(AuditEvent.at.desc(), AuditEvent.id.desc()).limit(limit)))


def retention_cutoff() -> Any:
    """The date beyond which entries may be pruned.

    Nothing prunes today — the log is append-only and this build keeps it all.
    The cutoff exists so the retention promise on the privacy page is computed
    from the same constant the operator would edit, rather than typed twice.
    """
    return now() - timedelta(days=AUDIT_RETENTION_DAYS)


def serialize(entry: AuditEvent) -> dict[str, Any]:
    return {
        "id": entry.id,
        "at": entry.at,
        "actor_label": entry.actor_label,
        "actor_role": entry.actor_role.value if entry.actor_role else None,
        "action": entry.action.value,
        "subject_type": entry.subject_type,
        "subject_id": entry.subject_id,
        "patient_id": entry.patient_id,
        "detail": entry.detail,
    }
