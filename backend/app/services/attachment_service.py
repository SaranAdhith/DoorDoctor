"""Uploaded files: recording them, serving them, and removing them safely.

`storage.py` owns the bytes. This owns the rows, and the one decision that
cannot live in either alone: **a file is deleted only when the last row
referencing it is gone.** Storage is content-addressed, so two dose photos that
happen to be the same image are one file on disk — deleting the file with the
first row would blank the second.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Attachment, AttachmentKind, Patient, User
from . import storage


def store(
    db: Session,
    *,
    data: bytes,
    kind: AttachmentKind,
    patient: Patient,
    uploaded_by: User | None = None,
) -> Attachment:
    """Validate, strip, write and record. Raises `BadRequestError` on bad input."""
    stored = storage.store_image(data)
    attachment = Attachment(
        kind=kind,
        path=stored.path,
        sha256=stored.sha256,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        width=stored.width,
        height=stored.height,
        patient_id=patient.id,
        uploaded_by=uploaded_by.id if uploaded_by else None,
    )
    db.add(attachment)
    db.flush()
    return attachment


def read(attachment: Attachment) -> bytes:
    return storage.read(attachment.path)


def delete(db: Session, attachment: Attachment) -> None:
    """Remove the row, and the file only if nothing else points at it."""
    path = attachment.path
    db.delete(attachment)
    db.flush()
    remaining = db.scalar(select(func.count(Attachment.id)).where(Attachment.path == path)) or 0
    if remaining == 0:
        storage.delete(path)


def delete_for_patient(db: Session, patient_id: int) -> int:
    """Every attachment belonging to one patient. Used by erasure."""
    attachments = list(db.scalars(select(Attachment).where(Attachment.patient_id == patient_id)))
    for attachment in attachments:
        delete(db, attachment)
    return len(attachments)


def serialize(attachment: Attachment) -> dict[str, Any]:
    """Metadata only. The bytes come from the authenticated fetch route."""
    return {
        "id": attachment.id,
        "kind": attachment.kind.value,
        "content_type": attachment.content_type,
        "size_bytes": attachment.size_bytes,
        "width": attachment.width,
        "height": attachment.height,
        "created_at": attachment.created_at,
        "url": f"/attachments/{attachment.id}",
    }
