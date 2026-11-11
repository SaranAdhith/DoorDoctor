"""Turning an upload into a stored file and a `Document` row.

Synchronous and cheap on purpose: validate, store, record, return `202`. Reading
the pages — which with OCR can take minutes — is the worker's job, so an upload
from a phone on a weak connection is never holding a request open for Chandra.

Authorization has already happened by the time anything here runs (`access.py`);
this module trusts its arguments and checks only the bytes.
"""

from __future__ import annotations

import re
from pathlib import PurePath

from sqlalchemy.orm import Session

from ...core.intelligence import DOCUMENT_DEFAULT_TITLE, DOCUMENT_TITLE_MAX
from ...models import (
    Attachment,
    AttachmentKind,
    AuditAction,
    Document,
    DocumentStatus,
    DocumentType,
    Patient,
    User,
    Visit,
)
from ...services import audit_service, storage
from . import notify, pdf_text

_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")


def clean_title(title: str | None, filename: str | None) -> str:
    """A display title from what the uploader typed, else the file's own name.

    The filename is a string somebody else chose: only its last path component
    is used, control characters are dropped, and it is never used as a path —
    storage paths come from the bytes' hash.
    """
    candidate = (title or "").strip()
    if not candidate and filename:
        candidate = PurePath(filename.replace("\\", "/")).name
    candidate = _CONTROL.sub(" ", candidate).strip()
    return (candidate or DOCUMENT_DEFAULT_TITLE)[:DOCUMENT_TITLE_MAX]


def upload(
    db: Session,
    *,
    patient: Patient,
    data: bytes,
    uploader: User,
    title: str | None = None,
    filename: str | None = None,
    doc_type: DocumentType = DocumentType.UNKNOWN,
    visit: Visit | None = None,
) -> Document:
    """Validate, store and queue. Raises `BadRequestError` on bad input."""
    page_count: int | None = None
    if storage.is_pdf(data):
        # Before anything is written: an encrypted or 300-page PDF is refused
        # here, while the uploader is still looking at the screen.
        page_count = pdf_text.inspect(data).page_count

    stored = storage.store_document(data)
    attachment = Attachment(
        kind=AttachmentKind.DOCUMENT_PDF if stored.is_pdf else AttachmentKind.DOCUMENT_IMAGE,
        path=stored.path,
        sha256=stored.sha256,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        width=stored.width,
        height=stored.height,
        patient_id=patient.id,
        uploaded_by=uploader.id,
    )
    db.add(attachment)
    db.flush()

    document = Document(
        patient_id=patient.id,
        visit_id=visit.id if visit else None,
        attachment_id=attachment.id,
        uploaded_by=uploader.id,
        uploader_role=uploader.role,
        title=clean_title(title, filename),
        doc_type=doc_type,
        status=DocumentStatus.UPLOADED,
        page_count=page_count if stored.is_pdf else 1,
    )
    db.add(document)
    db.flush()

    audit_service.record(
        db,
        actor=uploader,
        action=AuditAction.DOCUMENT_UPLOADED,
        subject_type="document",
        subject_id=document.id,
        patient_id=patient.id,
        detail=(
            f"Uploaded a {'PDF' if stored.is_pdf else 'photo'} document"
            + (f" during visit #{visit.id}" if visit else "")
            + "."
        ),
    )
    notify.document_event(db, document, notify.Event.UPLOADED, actor=uploader)
    db.commit()
    db.refresh(document)
    return document
