"""Listing, serialising, deleting, reprocessing — and the privacy hooks.

`export_for_patient` and `erase_for_patient` are what `privacy_service`'s
registry calls, so the erasure promise covers uploaded documents and the text
read from them without `privacy_service` knowing how either is stored.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from ...core.exceptions import BadRequestError
from ...models import (
    AuditAction,
    Document,
    DocumentPage,
    DocumentStatus,
    ExtractedFact,
    FactStatus,
    User,
    UserRole,
)
from ...services import attachment_service, audit_service
from . import access, notify

#: What a family member reads in place of a status code. The nurse and admin
#: screens show the code itself alongside.
STATUS_LABELS: dict[DocumentStatus, str] = {
    DocumentStatus.UPLOADED: "Received",
    DocumentStatus.EXTRACTING: "Being read",
    DocumentStatus.EXTRACTED: "Waiting for the care team to check",
    DocumentStatus.NEEDS_MANUAL: "Waiting for the care team to check",
    DocumentStatus.VERIFIED: "Checked by the care team",
    DocumentStatus.REJECTED: "Not added to the record",
    DocumentStatus.FAILED: "Could not be read",
}


def _loaded():
    return select(Document).options(
        selectinload(Document.attachment),
        selectinload(Document.uploader),
        selectinload(Document.pages),
        selectinload(Document.facts),
    )


def list_for_patient(db: Session, user: User, patient_id: int) -> list[Document]:
    """Documents the caller may see, newest first. Authorization of the patient
    itself happens in the router; this applies the per-document rule."""
    documents = db.scalars(
        _loaded().where(Document.patient_id == patient_id).order_by(Document.created_at.desc(), Document.id.desc())
    ).all()
    return [d for d in documents if access.can_read(db, user, d)]


def list_for_admin(db: Session, *, status: DocumentStatus | None = None, limit: int = 100) -> list[Document]:
    query = _loaded().order_by(Document.created_at, Document.id).limit(limit)
    if status is not None:
        query = query.where(Document.status == status)
    return list(db.scalars(query))


#: What the admin review queue shows: read, and waiting for a person.
QUEUE: tuple[DocumentStatus, ...] = (DocumentStatus.EXTRACTED, DocumentStatus.NEEDS_MANUAL)


def review_queue(db: Session, *, limit: int = 100) -> list[Document]:
    """Oldest first: the family who uploaded first has waited longest."""
    query = _loaded().where(Document.status.in_(QUEUE)).order_by(Document.created_at, Document.id).limit(limit)
    return list(db.scalars(query))


def reprocess(db: Session, document: Document) -> Document:
    """Put a document back in the queue — after the OCR server comes back, say."""
    if document.status in (DocumentStatus.VERIFIED, DocumentStatus.EXTRACTING):
        raise BadRequestError(
            "A verified document can't be re-read."
            if document.status == DocumentStatus.VERIFIED
            else "This document is being read right now."
        )
    document.status = DocumentStatus.UPLOADED
    document.attempts = 0
    document.error = None
    db.commit()
    db.refresh(document)
    return document


def remove(db: Session, document: Document, *, actor: User) -> None:
    attachment = document.attachment
    patient_id = document.patient_id
    document_id = document.id
    notify.document_event(db, document, notify.Event.REMOVED, actor=actor)
    db.delete(document)  # pages go with it (delete-orphan)
    db.flush()
    if attachment is not None:
        attachment_service.delete(db, attachment)
    audit_service.record(
        db,
        actor=actor,
        action=AuditAction.DOCUMENT_DELETED,
        subject_type="document",
        subject_id=document_id,
        patient_id=patient_id,
        detail="Removed an uploaded document.",
    )
    db.commit()


def serialize(document: Document, user: User) -> dict[str, Any]:
    attachment = document.attachment
    body: dict[str, Any] = {
        "id": document.id,
        "patient_id": document.patient_id,
        "visit_id": document.visit_id,
        "title": document.title,
        "doc_type": document.doc_type.value,
        "document_date": document.document_date,
        "status": document.status.value,
        "status_label": STATUS_LABELS[document.status],
        "page_count": document.page_count,
        "uploader_role": document.uploader_role.value,
        "uploaded_by_name": document.uploader.name if document.uploader else None,
        "uploaded_by_me": document.uploaded_by == user.id,
        "created_at": document.created_at,
        "extracted_at": document.extracted_at,
        "verified_at": document.verified_at,
        "file": {
            "url": f"/attachments/{attachment.id}",
            "content_type": attachment.content_type,
            "size_bytes": attachment.size_bytes,
        }
        if attachment is not None
        else None,
        "can_delete": access.can_delete(user, document),
    }
    in_record = [f for f in document.facts if f.status in _IN_RECORD]
    body["facts_in_record"] = len(in_record) if document.status == DocumentStatus.VERIFIED else 0
    if user.role == UserRole.ADMIN:
        body["facts_total"] = len(document.facts)
        body["facts_pending"] = sum(1 for f in document.facts if f.status == FactStatus.PROPOSED)
        body["error"] = document.error
        body["attempts"] = document.attempts
        body["pages_needing_manual_entry"] = [
            page.page_no for page in document.pages if page.method.value == "none"
        ]
    return body


_IN_RECORD = frozenset({FactStatus.CONFIRMED, FactStatus.EDITED, FactStatus.ADDED})


def serialize_fact(fact: ExtractedFact, *, with_review: bool) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": fact.id,
        "page_no": fact.page_no,
        "kind": fact.kind.value,
        "label": fact.label,
        "value_text": fact.value_text,
        "value_num": fact.value_num,
        "unit": fact.unit,
        "ref_low": fact.ref_low,
        "ref_high": fact.ref_high,
        "out_of_range": fact.out_of_range,
        "observed_on": fact.observed_on,
        "status": fact.status.value,
    }
    if with_review:
        body.update(
            source=fact.source.value,
            source_quote=fact.source_quote,
            original=json.loads(fact.original_json) if fact.original_json else None,
            reviewed_at=fact.reviewed_at,
        )
    return body


def visible_facts(document: Document, user: User) -> list[ExtractedFact]:
    """Admins see every fact, decided or not. Everyone else sees only facts a
    person put in the record, and only once the document is verified."""
    if user.role == UserRole.ADMIN:
        return list(document.facts)
    if document.status != DocumentStatus.VERIFIED:
        return []
    return [f for f in document.facts if f.status in _IN_RECORD]


def serialize_with_pages(document: Document, user: User) -> dict[str, Any]:
    body = serialize(document, user)
    body["facts"] = [
        serialize_fact(f, with_review=user.role == UserRole.ADMIN) for f in visible_facts(document, user)
    ]
    if access.can_see_page_text(user):
        body["pages"] = [
            {
                "page_no": page.page_no,
                "method": page.method.value,
                "engine": page.engine,
                "char_count": page.char_count,
                "elapsed_ms": page.elapsed_ms,
                "text": page.text,
            }
            for page in document.pages
        ]
    return body


# --- privacy registry hooks ---------------------------------------------------


def export_for_patient(db: Session, patient_id: int) -> list[dict[str, Any]]:
    documents = db.scalars(
        select(Document).where(Document.patient_id == patient_id).order_by(Document.created_at)
    ).all()
    return [
        {
            "title": d.title,
            "doc_type": d.doc_type.value,
            "status": d.status.value,
            "page_count": d.page_count,
            "uploaded_at": d.created_at.isoformat() if d.created_at else None,
            # Only what a person put in the record; proposals are not the patient's data.
            "facts": [
                {
                    "label": f.label,
                    "value": f.value_text,
                    "unit": f.unit,
                    "reference": [f.ref_low, f.ref_high],
                    "observed_on": f.observed_on.isoformat() if f.observed_on else None,
                }
                for f in d.facts
                if f.status in _IN_RECORD
            ],
        }
        for d in documents
    ]


def erase_for_patient(db: Session, patient_id: int) -> int:
    """Rows only. The files go with the `attachments` dataset, which the
    registry runs after this one — every document's file is an Attachment of
    the same patient, so nothing is left on disk."""
    ids = list(db.scalars(select(Document.id).where(Document.patient_id == patient_id)))
    if not ids:
        return 0
    db.execute(delete(ExtractedFact).where(ExtractedFact.document_id.in_(ids)))
    db.execute(delete(DocumentPage).where(DocumentPage.document_id.in_(ids)))
    db.execute(delete(Document).where(Document.id.in_(ids)))
    return len(ids)
