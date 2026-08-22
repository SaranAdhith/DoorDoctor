"""Public enquiries (§2.6).

Small on purpose. The interesting decisions in lead capture are *not* business
logic — they are the defences around the only unauthenticated write in the
codebase, and they live where they belong: the rate limit in the router (it
needs the request's IP), the length caps in the schema, and the honeypot here,
because whether a submission is real is a fact about the submission.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import now
from ..models import Lead, LeadKind, LeadStatus, User
from ..schemas.lead import LeadCreate

logger = logging.getLogger("doordoctor.leads")


def create(db: Session, payload: LeadCreate) -> Optional[Lead]:
    """Store an enquiry, or return `None` when the honeypot was filled.

    `None` is not an error and the caller must not turn it into one. A bot that
    receives a 400 learns that its script was detected and tries something else;
    a bot that receives the same cheerful 200 as everyone else learns nothing and
    has spent a request. So the return type carries the distinction and the
    response body does not.
    """
    if payload.company_website:
        # Never log the value — it is attacker-controlled text.
        logger.info("Discarded a lead submission that filled the honeypot field.")
        return None

    lead = Lead(
        name=payload.name,
        email=payload.email,  # already lowercased by the schema validator
        phone=payload.phone,
        city=payload.city,
        kind=payload.kind,
        message=payload.message,
        source_page=payload.source_page,
        status=LeadStatus.NEW,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    # The address is a stranger's contact detail; the id is enough to find the row.
    logger.info("Lead %s captured from %s.", lead.id, lead.source_page or "unknown page")
    return lead


def list_leads(
    db: Session, *, status: Optional[LeadStatus] = None, kind: Optional[LeadKind] = None
) -> list[Lead]:
    """Newest first — an enquiry is worth most on the day it arrives."""
    query = select(Lead).order_by(Lead.created_at.desc(), Lead.id.desc())
    if status is not None:
        query = query.where(Lead.status == status)
    if kind is not None:
        query = query.where(Lead.kind == kind)
    return list(db.scalars(query))


def get(db: Session, lead_id: int) -> Optional[Lead]:
    return db.get(Lead, lead_id)


def update(
    db: Session,
    lead: Lead,
    *,
    admin: User,
    status: Optional[LeadStatus] = None,
    admin_note: Optional[str] = None,
) -> Lead:
    """Move a lead along the queue and/or note what happened.

    `handled_by` and `handled_at` are stamped whenever the status moves off
    `new`, so "who spoke to this person and when" is answerable without an audit
    log. Moving a lead *back* to `new` clears them rather than leaving a stale
    name attached to an unworked enquiry.
    """
    if status is not None and status != lead.status:
        lead.status = status
        if status == LeadStatus.NEW:
            lead.handled_by_user_id = None
            lead.handled_at = None
        else:
            lead.handled_by_user_id = admin.id
            lead.handled_at = now()

    if admin_note is not None:
        cleaned = admin_note.strip()
        lead.admin_note = cleaned or None

    db.commit()
    db.refresh(lead)
    return lead


def summary(db: Session) -> dict[str, Any]:
    """Counts for the admin queue header.

    Grouped in the database rather than by loading every lead and counting in
    Python — this is the one place that would still be correct but slow once the
    marketing site works.
    """
    by_status = {
        status.value: 0 for status in LeadStatus
    } | {
        row.value: count
        for row, count in db.execute(select(Lead.status, func.count(Lead.id)).group_by(Lead.status))
    }
    by_kind = {
        row.value: count
        for row, count in db.execute(select(Lead.kind, func.count(Lead.id)).group_by(Lead.kind))
    }

    return {
        "total": sum(by_status.values()),
        "new": by_status[LeadStatus.NEW.value],
        "contacted": by_status[LeadStatus.CONTACTED.value],
        "qualified": by_status[LeadStatus.QUALIFIED.value],
        "closed": by_status[LeadStatus.CLOSED.value],
        "by_kind": by_kind,
    }


def serialize(lead: Lead) -> dict[str, Any]:
    return {
        "id": lead.id,
        "name": lead.name,
        "email": lead.email,
        "phone": lead.phone,
        "city": lead.city,
        "kind": lead.kind.value,
        "message": lead.message,
        "source_page": lead.source_page,
        "status": lead.status.value,
        "admin_note": lead.admin_note,
        "handled_by": lead.handled_by.name if lead.handled_by else None,
        "handled_at": lead.handled_at,
        "created_at": lead.created_at,
    }
