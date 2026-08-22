"""Lead capture from the public site (§2.6).

`POST /leads` is the **only unauthenticated write endpoint in this codebase**.
Everything unusual about this router follows from that:

* It is rate limited twice — per source address and per email — through the
  existing `core/ratelimit` limiter. Not a second limiter: the autouse fixture in
  `tests/conftest.py` resets exactly one, and a second would silently make test
  order matter again.
* A honeypot hit gets the **same 200 and the same body** as a real submission.
* Every read is admin-only. A lead list is a list of named strangers and their
  phone numbers.
"""

from typing import Any

from fastapi import APIRouter, Query, Request, status

from ..core.dependencies import AdminUser, DbSession
from ..core.exceptions import NotFoundError
from ..core.ratelimit import LEADS_PER_EMAIL, LEADS_PER_IP, limiter
from ..models import LeadKind, LeadStatus
from ..schemas.lead import LeadAccepted, LeadCreate, LeadOut, LeadSummaryOut, LeadUpdate
from ..services import lead_service

router = APIRouter(prefix="/leads", tags=["leads"])

ACCEPTED_MESSAGE = (
    "Thank you — your enquiry has reached the DoorDoctor team. "
    "We will be in touch within one working day."
)
"""One fixed sentence for every accepted submission, every honeypot hit, and
every repeat from an address that has already enquired. It says nothing a sender
could learn from, which is the same rule `POST /auth/forgot-password` follows."""


@router.post(
    "",
    response_model=LeadAccepted,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an enquiry (public)",
)
def submit_lead(payload: LeadCreate, request: Request, db: DbSession) -> dict[str, str]:
    """Capture an enquiry from the marketing site. No authentication required."""
    ip = request.client.host if request.client else "unknown"
    ip_limit, ip_window = LEADS_PER_IP
    email_limit, email_window = LEADS_PER_EMAIL
    # IP first: it is the cheaper key to exhaust, and checking it first means a
    # flood from one host cannot consume many different addresses' budgets on
    # the way to being refused.
    limiter.check("lead:ip", ip, limit=ip_limit, per_seconds=ip_window)
    limiter.check("lead:email", payload.email, limit=email_limit, per_seconds=email_window)

    # `None` means the honeypot was filled. The response does not change.
    lead_service.create(db, payload)
    return {"message": ACCEPTED_MESSAGE}


@router.get("", response_model=list[LeadOut], summary="Every enquiry (admin)")
def list_leads(
    db: DbSession,
    current_user: AdminUser,
    lead_status: LeadStatus | None = Query(default=None, alias="status"),
    kind: LeadKind | None = Query(default=None),
) -> list[dict[str, Any]]:
    leads = lead_service.list_leads(db, status=lead_status, kind=kind)
    return [lead_service.serialize(lead) for lead in leads]


@router.get("/summary", response_model=LeadSummaryOut, summary="Enquiry counts (admin)")
def leads_summary(db: DbSession, current_user: AdminUser) -> dict[str, Any]:
    return lead_service.summary(db)


@router.patch("/{lead_id}", response_model=LeadOut, summary="Work an enquiry (admin)")
def update_lead(
    lead_id: int, payload: LeadUpdate, db: DbSession, current_user: AdminUser
) -> dict[str, Any]:
    lead = lead_service.get(db, lead_id)
    if lead is None:
        raise NotFoundError("Enquiry not found.")

    updated = lead_service.update(
        db, lead, admin=current_user, status=payload.status, admin_note=payload.admin_note
    )
    return lead_service.serialize(updated)
