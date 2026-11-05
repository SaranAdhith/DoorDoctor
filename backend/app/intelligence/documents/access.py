"""Who may upload, see and remove a document.

Built on the existing `core.dependencies` functions rather than beside them, so
"who may see this patient" stays one rule. What this module adds is narrower
than that rule, never wider:

- **Family and admin** upload against a patient through `authorize_patient`.
- **A nurse uploads only from a visit**, and only while all of these hold:
  the visit is theirs, it is in progress (checked in, not yet checked out), and
  the check-in was not placed away from the home by the geofence. A missing GPS
  fix is allowed — see `core.intelligence.NURSE_UPLOAD_BLOCKED_LOCATIONS`.
- **Reading** a document: admin, any; family, their own patient's; nurse, the
  ones they uploaded plus verified ones for a patient on their visit list.
- **Raw page text** is admin-only. It is unverified machine output, and the
  whole design of Layer 1 is that unverified output reaches only the admin.
- **Deleting**: admin, any; a family uploader, their own until it is verified.
  Nurses never delete — a photograph taken during a visit is part of its record.

Every refusal for a document the caller may not see is a 404, matching
`authorize_patient`: probing ids must not reveal that a document exists.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ...core.dependencies import authorize_nurse_visit, authorize_patient
from ...core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from ...core.intelligence import NURSE_UPLOAD_BLOCKED_LOCATIONS
from ...models import Document, DocumentStatus, Nurse, Patient, User, UserRole, Visit, VisitStatus


def authorize_upload_for_patient(db: Session, user: User, patient_id: int) -> Patient:
    if user.role == UserRole.NURSE:
        raise ForbiddenError("Nurses add documents from the visit they are on.")
    return authorize_patient(db, user, patient_id)


def authorize_nurse_upload(db: Session, user: User, visit_id: int) -> tuple[Visit, Nurse]:
    """The strict nurse rule. Each failure says which condition was not met,
    because a nurse standing in a living room needs to know what to fix."""
    if user.role != UserRole.NURSE:
        raise ForbiddenError("Only the nurse on this visit can add documents to it.")
    visit, nurse = authorize_nurse_visit(db, user, visit_id)

    if visit.status != VisitStatus.IN_PROGRESS:
        raise BadRequestError("Documents can be added only while the visit is in progress.")
    status = getattr(visit.location_status, "value", visit.location_status)
    if status in NURSE_UPLOAD_BLOCKED_LOCATIONS:
        raise ForbiddenError(
            "This visit's check-in was recorded away from the patient's home, so "
            "documents can't be added to it. An admin can add the document instead."
        )
    return visit, nurse


def can_read(db: Session, user: User, document: Document) -> bool:
    try:
        authorize_patient(db, user, document.patient_id)
    except NotFoundError:
        return False
    if user.role in (UserRole.ADMIN, UserRole.FAMILY):
        return True
    if user.role == UserRole.NURSE:
        return document.uploaded_by == user.id or document.status == DocumentStatus.VERIFIED
    return False  # pragma: no cover - no other roles exist


def authorize_document(db: Session, user: User, document_id: int) -> Document:
    document = db.get(Document, document_id)
    if document is None or not can_read(db, user, document):
        raise NotFoundError("Document not found.")
    return document


def can_see_page_text(user: User) -> bool:
    return user.role == UserRole.ADMIN


def can_delete(user: User, document: Document) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.FAMILY:
        return document.uploaded_by == user.id and document.status != DocumentStatus.VERIFIED
    return False
