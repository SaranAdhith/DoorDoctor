"""An admin's decisions on a document (Stage 2).

The rule this module holds: **software proposes, a person decides, and only a
decision becomes part of the record.** Concretely:

- each fact is confirmed, edited, rejected or added by an admin, and the
  reviewer and time are stored on it;
- an edit keeps what software first proposed (`original_json`), so a correction
  ("DRS" → "ORS") is visible, not silently overwritten;
- a document is `verified` only once **no fact is still `proposed`** — the
  button can't be pressed past an undecided fact;
- a verified or rejected document is closed: its facts can't change. Re-opening
  means re-uploading, which leaves a trail.

Every verification and rejection is audited.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from ...core.exceptions import BadRequestError, ConflictError
from ...database import now
from ...models import (
    AuditAction,
    Document,
    DocumentStatus,
    DocumentType,
    ExtractedFact,
    FactKind,
    FactSource,
    FactStatus,
    User,
)
from ...services import audit_service
from . import extraction, notify

#: A document can be reviewed once its pages have been read, whether or not
#: every page could be (a `needs_manual` page is exactly where facts get added).
REVIEWABLE: frozenset[DocumentStatus] = frozenset({DocumentStatus.EXTRACTED, DocumentStatus.NEEDS_MANUAL})
DECIDED: frozenset[FactStatus] = frozenset(
    {FactStatus.CONFIRMED, FactStatus.EDITED, FactStatus.REJECTED, FactStatus.ADDED}
)
#: What reaches nurses, families and summaries.
IN_RECORD: frozenset[FactStatus] = frozenset({FactStatus.CONFIRMED, FactStatus.EDITED, FactStatus.ADDED})

EDITABLE_FIELDS = ("kind", "label", "value_text", "value_num", "unit", "ref_low", "ref_high", "observed_on", "page_no")


def _require_open(document: Document) -> None:
    if document.status not in REVIEWABLE:
        if document.status in (DocumentStatus.VERIFIED, DocumentStatus.REJECTED):
            raise ConflictError("This document has already been decided and can't be changed.")
        raise ConflictError("This document hasn't been read yet. Try again once its pages are ready.")


def _snapshot(fact: ExtractedFact) -> str:
    return json.dumps(
        {
            "kind": fact.kind.value,
            "label": fact.label,
            "value_text": fact.value_text,
            "value_num": fact.value_num,
            "unit": fact.unit,
            "ref_low": fact.ref_low,
            "ref_high": fact.ref_high,
            "observed_on": fact.observed_on.isoformat() if fact.observed_on else None,
        }
    )


def _apply(fact: ExtractedFact, changes: dict[str, Any]) -> None:
    for name in EDITABLE_FIELDS:
        if name not in changes:
            continue
        value = changes[name]
        if name == "kind" and value is not None:
            value = FactKind(value)
        if name in ("value_text", "unit") and value is None:
            value = ""
        if name == "observed_on" and isinstance(value, str):
            value = date.fromisoformat(value)
        setattr(fact, name, value)
    if not fact.label.strip():
        raise BadRequestError("A fact needs a label.")
    if fact.ref_low is not None and fact.ref_high is not None and fact.ref_low > fact.ref_high:
        raise BadRequestError("The lower bound of the range is above the upper bound.")


def decide(
    db: Session,
    document: Document,
    fact: ExtractedFact,
    *,
    action: str,
    actor: User,
    changes: dict[str, Any] | None = None,
) -> ExtractedFact:
    """`confirm`, `reject` or `edit` one fact."""
    _require_open(document)
    if fact.document_id != document.id:
        raise BadRequestError("That fact belongs to a different document.")

    if action == "confirm":
        fact.status = FactStatus.CONFIRMED
    elif action == "reject":
        fact.status = FactStatus.REJECTED
    elif action == "edit":
        if fact.original_json is None and fact.source != FactSource.MANUAL:
            fact.original_json = _snapshot(fact)
        _apply(fact, changes or {})
        # A manual fact edited is still the admin's own entry.
        fact.status = FactStatus.ADDED if fact.source == FactSource.MANUAL else FactStatus.EDITED
    elif action == "reopen":
        fact.status = FactStatus.PROPOSED
    else:
        raise BadRequestError("Action must be confirm, edit, reject or reopen.")

    if fact.status == FactStatus.PROPOSED:
        fact.reviewed_by, fact.reviewed_at = None, None
    else:
        fact.reviewed_by, fact.reviewed_at = actor.id, now()
    db.commit()
    db.refresh(fact)
    return fact


def add(db: Session, document: Document, *, actor: User, fields: dict[str, Any]) -> ExtractedFact:
    """An admin's own fact — for a page nothing could read, or one software missed."""
    _require_open(document)
    fact = ExtractedFact(
        patient_id=document.patient_id,
        kind=FactKind.OTHER,
        label="",
        source=FactSource.MANUAL,
        status=FactStatus.ADDED,
        reviewed_by=actor.id,
        reviewed_at=now(),
    )
    _apply(fact, fields)
    document.facts.append(fact)
    db.commit()
    db.refresh(fact)
    return fact


def pending(document: Document) -> list[ExtractedFact]:
    return [fact for fact in document.facts if fact.status == FactStatus.PROPOSED]


def verify(
    db: Session,
    document: Document,
    *,
    actor: User,
    doc_type: DocumentType | None = None,
    document_date: date | None = None,
) -> Document:
    _require_open(document)
    undecided = pending(document)
    if undecided:
        raise ConflictError(
            f"{len(undecided)} fact{'s are' if len(undecided) != 1 else ' is'} still waiting for a "
            "decision. Confirm, edit or reject each one first."
        )
    if doc_type is not None:
        document.doc_type = doc_type
    if document_date is not None:
        document.document_date = document_date
    document.status = DocumentStatus.VERIFIED
    document.verified_by = actor.id
    document.verified_at = now()

    kept = sum(1 for fact in document.facts if fact.status in IN_RECORD)
    audit_service.record(
        db,
        actor=actor,
        action=AuditAction.DOCUMENT_VERIFIED,
        subject_type="document",
        subject_id=document.id,
        patient_id=document.patient_id,
        detail=f"Verified a document; {kept} fact{'s' if kept != 1 else ''} added to the record.",
    )
    notify.document_event(db, document, notify.Event.VERIFIED, actor=actor, facts_kept=kept)
    db.commit()
    db.refresh(document)
    return document


def reject(db: Session, document: Document, *, actor: User, reason: str) -> Document:
    """The whole document stays out of the record: wrong patient, unreadable,
    not a medical document. The reason goes to the audit log, which is where an
    admin's judgement about a record belongs."""
    _require_open(document)
    reason = reason.strip()
    if not reason:
        raise BadRequestError("Say why the document is being rejected.")
    document.status = DocumentStatus.REJECTED
    audit_service.record(
        db,
        actor=actor,
        action=AuditAction.DOCUMENT_REJECTED,
        subject_type="document",
        subject_id=document.id,
        patient_id=document.patient_id,
        detail=f"Rejected a document: {reason}",
    )
    notify.document_event(db, document, notify.Event.REJECTED, actor=actor)
    db.commit()
    db.refresh(document)
    return document


def re_extract(db: Session, document: Document) -> int:
    """Propose facts again from the stored text — after a Groq key is added, say.
    Decided facts are kept (see `extraction.extract_document`)."""
    _require_open(document)
    proposed = extraction.extract_document(db, document)
    db.commit()
    return proposed
