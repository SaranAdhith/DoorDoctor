"""Telling the people who can see a document that it moved (Phase 12).

Every stage change writes an **in-app** notification — the same `notifications`
table the bell reads, with type `document` so the Documents menu item can show
its own unread count. Nothing here is sent by SMS, WhatsApp or email: a
document's progress is not urgent, and the outbound path (`dispatch`) stays
reserved for alerts.

Who hears about what follows `access.py` exactly — nobody is told about a
document they couldn't open:

| Event                    | Family (patient's own) | Nurse who uploaded | Nurses with an open visit | Admins |
|--------------------------|------------------------|--------------------|---------------------------|--------|
| uploaded by someone else | ✓                      |                    |                           |        |
| read, ready for review   | ✓                      | ✓                  |                           | ✓      |
| could not be read        | ✓                      | ✓                  |                           | ✓      |
| verified                 | ✓                      | ✓                  | ✓ (it's now visible to them) |     |
| rejected                 | ✓                      | ✓                  |                           |        |
| removed                  | ✓                      | ✓                  |                           |        |

The person who caused the change is never notified of their own action. The
message names the document and the patient's first name and says nothing about
what the document contains.
"""

from __future__ import annotations

from enum import Enum

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...models import (
    Document,
    Notification,
    NotificationType,
    Nurse,
    Patient,
    User,
    UserRole,
    Visit,
    VisitStatus,
)


class Event(str, Enum):
    UPLOADED = "uploaded"
    READ = "read"
    FAILED = "failed"
    VERIFIED = "verified"
    REJECTED = "rejected"
    REMOVED = "removed"


def _admins(db: Session) -> set[int]:
    return set(db.scalars(select(User.id).where(User.role == UserRole.ADMIN, User.is_active.is_(True))))


def _nurses_with_open_visits(db: Session, patient_id: int) -> set[int]:
    return set(
        db.scalars(
            select(Nurse.user_id)
            .join(Visit, Visit.nurse_id == Nurse.id)
            .where(
                Visit.patient_id == patient_id,
                Visit.status.in_([VisitStatus.SCHEDULED, VisitStatus.IN_PROGRESS]),
            )
        )
    )


def _uploader_if_nurse(document: Document) -> set[int]:
    if document.uploaded_by and document.uploader_role == UserRole.NURSE:
        return {document.uploaded_by}
    return set()


def recipients(db: Session, document: Document, event: Event, patient: Patient) -> set[int]:
    family = {patient.family_user_id}
    nurse_uploader = _uploader_if_nurse(document)
    if event == Event.UPLOADED:
        return family
    if event in (Event.READ, Event.FAILED):
        return family | nurse_uploader | _admins(db)
    if event == Event.VERIFIED:
        return family | nurse_uploader | _nurses_with_open_visits(db, document.patient_id)
    return family | nurse_uploader  # rejected, removed


def _message(event: Event, document: Document, first_name: str, facts_kept: int) -> tuple[str, str]:
    name = f"“{document.title}” for {first_name}"
    if event == Event.UPLOADED:
        return "New document added", f"{name} was added and is being read."
    if event == Event.READ:
        return "Document ready for review", f"{name} has been read and is waiting for the care team to check it."
    if event == Event.FAILED:
        return "Document could not be read", f"{name} could not be read. It can be uploaded again or entered by hand."
    if event == Event.VERIFIED:
        detail = f" {facts_kept} detail{'s' if facts_kept != 1 else ''} added to the record." if facts_kept else ""
        return "Document checked by the care team", f"{name} has been checked.{detail}"
    if event == Event.REJECTED:
        return "Document not added", f"{name} was checked and not added to the record."
    return "Document removed", f"{name} was removed."


def document_event(
    db: Session,
    document: Document,
    event: Event,
    *,
    actor: User | None = None,
    facts_kept: int = 0,
) -> list[Notification]:
    """Write one notification per recipient. Joins the caller's transaction;
    the caller commits."""
    patient = db.get(Patient, document.patient_id)
    if patient is None:  # pragma: no cover - defensive
        return []
    first_name = (patient.name or "your relative").split()[0]
    title, message = _message(event, document, first_name, facts_kept)

    users = recipients(db, document, event, patient)
    if actor is not None:
        users.discard(actor.id)
    created = []
    for user_id in sorted(users):
        notification = Notification(
            user_id=user_id,
            patient_id=document.patient_id,
            type=NotificationType.DOCUMENT,
            title=title,
            message=message,
        )
        db.add(notification)
        created.append(notification)
    return created


def mark_seen(db: Session, user: User) -> int:
    """The user opened their Documents page: their document notifications are read."""
    rows = db.scalars(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.type == NotificationType.DOCUMENT,
            Notification.read.is_(False),
        )
    ).all()
    for row in rows:
        row.read = True
    db.commit()
    return len(rows)


def unseen_count(db: Session, user: User) -> int:
    return db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id,
            Notification.type == NotificationType.DOCUMENT,
            Notification.read.is_(False),
        )
    ) or 0
