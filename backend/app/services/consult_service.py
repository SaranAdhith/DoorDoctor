"""Doctor video consults (§4.6) — and the first enforced quota in the codebase.

RECORDED: Premium includes **2 consults per month** (`core/pricing.py`).
`ASSUMED` (all in `core/clinical.py`): duration, the cancellation window, how far
ahead one may be booked, and the doctor's name.

Why telemedicine is enforced when visits are not
------------------------------------------------
Phase 4 built `consume_quota` and deliberately did not wire it in at the point of
use, because §3 was never supplied. Phase 9 is where that stops being free to
ignore — but the two meters are **not** in the same position, and the split
follows the evidence rather than a preference:

* **Visits stay unenforced.** §2.4 records ~1,400 visits over 90 days for 28
  patients — 16.7 per patient per month — against an assumed top tier of 12.
  Enforcing that limit would refuse the visits the demo is specified to contain.
  The recorded volume contradicts the assumed entitlement, so the entitlement is
  what has to be reconciled first.
* **Telemedicine is enforced.** Its allowance is the one number in `pricing.py`
  that is *recorded* (2 per month on Premium), and nothing recorded contradicts
  it. A "2 per month" limit that never says no is not a limit.

That is the whole argument, and it lives here rather than only in STATE.md
because here is where the next person will be standing when they wonder.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..core import clinical, pricing
from ..core.exceptions import BadRequestError, ConflictError, NotFoundError
from ..database import now
from ..models import (
    Consult,
    ConsultStatus,
    Patient,
    Subscription,
    User,
)
from . import subscription_service

logger = logging.getLogger("doordoctor.consults")

# Resolved from the entitlement key, never typed. See `lab_service.LAB_QUOTA`.
CONSULT_QUOTA = next(
    q.name for q in pricing.QUOTAS if q.entitlement_key == pricing.TELEMEDICINE_PER_MONTH
)


def _subscription_for(db: Session, patient: Patient) -> Subscription | None:
    return db.scalar(
        select(Subscription)
        .options(selectinload(Subscription.plan))
        .where(Subscription.family_user_id == patient.family_user_id)
        .order_by(Subscription.id.desc())
        .limit(1)
    )


def allowance(db: Session, patient: Patient, as_of: datetime | None = None) -> dict[str, Any]:
    """What this patient's plan allows this month, and what is left.

    Read straight out of `quota_status` so the number on the booking screen and
    the number the booking is refused against are the same number.
    """
    subscription = _subscription_for(db, patient)
    if subscription is None:
        return {"included": 0, "used": 0, "remaining": 0, "unlimited": False, "subscribed": False}

    status = next(
        q
        for q in subscription_service.quota_status(db, subscription, as_of=as_of)
        if q["quota"] == CONSULT_QUOTA
    )
    return {
        "included": status["limit"],
        "used": status["used"],
        "remaining": status["remaining"],
        "unlimited": status["unlimited"],
        "subscribed": True,
        "period_start": status["period_start"],
        "period_end": status["period_end"],
    }


def book(
    db: Session,
    *,
    patient: Patient,
    user: User,
    scheduled_for: datetime,
    reason: str = "",
    as_of: datetime | None = None,
) -> Consult:
    """Book a consult against the plan's allowance.

    Refusal is a **409, not a 403** — `consume_quota`'s choice, and the right
    one: the family is entitled to book consults, they have simply used this
    month's. Those two need different words on screen, and an HTTP status is how
    the client tells them apart without parsing a sentence.
    """
    moment = as_of or now()
    _validate_slot(scheduled_for, moment)

    subscription = _subscription_for(db, patient)
    if subscription is None:
        raise ConflictError(
            "This patient has no active plan, so a doctor consult cannot be booked."
        )
    if not subscription.is_live:
        raise ConflictError("This plan is no longer active, so a consult cannot be booked.")

    # Raises ConflictError (409) when the allowance is spent. Essential's
    # allowance is 0, so booking on Essential is refused by the entitlement —
    # not by a check on the tier's name, which nothing in this codebase does.
    subscription_service.consume_quota(db, subscription, CONSULT_QUOTA, as_of=moment)

    consult = Consult(
        patient_id=patient.id,
        subscription_id=subscription.id,
        requested_by=user.id,
        scheduled_for=scheduled_for,
        duration_minutes=clinical.CONSULT_DURATION_MINUTES,
        status=ConsultStatus.SCHEDULED,
        reason=(reason or "").strip(),
        doctor_name=clinical.CONSULT_PLACEHOLDER_DOCTOR,
        created_at=moment,
    )
    db.add(consult)
    db.flush()
    logger.info("Consult %s booked for patient %s", consult.id, patient.id)
    return consult


def _validate_slot(scheduled_for: datetime, moment: datetime) -> None:
    """Both bounds are `ASSUMED` and both live in `core/clinical.py`."""
    earliest = moment + timedelta(minutes=clinical.CONSULT_MIN_LEAD_MINUTES)
    latest = moment + timedelta(days=clinical.CONSULT_MAX_LEAD_DAYS)
    if scheduled_for < earliest:
        raise BadRequestError(
            f"Please choose a time at least {clinical.CONSULT_MIN_LEAD_MINUTES} minutes from now."
        )
    if scheduled_for > latest:
        raise BadRequestError(
            f"Consults can be booked up to {clinical.CONSULT_MAX_LEAD_DAYS} days ahead."
        )


def cancel(
    db: Session,
    consult: Consult,
    user: User,
    reason: str | None = None,
    as_of: datetime | None = None,
) -> Consult:
    """Cancel, handing the allowance back if it is early enough.

    Inside the cancellation window the slot is gone whoever cancels, so the
    allowance is spent. Outside it, nothing was consumed and the family keeps
    their consult — the opposite of a lab order, where the sample and the
    laboratory are already paid for.

    `quota_released` is stored so a second cancellation, or a replayed request,
    cannot refund the same booking twice.
    """
    if consult.status != ConsultStatus.SCHEDULED:
        raise BadRequestError("This consult is no longer scheduled.")

    moment = as_of or now()
    consult.status = ConsultStatus.CANCELLED
    consult.cancelled_at = moment
    consult.cancellation_reason = (reason or "").strip() or None

    if _is_refundable(consult, moment) and not consult.quota_released:
        subscription = consult.subscription
        if subscription is not None:
            subscription_service.release_quota(
                db,
                subscription,
                CONSULT_QUOTA,
                # Released against the period the booking was *made* in, not
                # today's. A consult booked on the 30th and cancelled on the 2nd
                # must give its allowance back to the month it was taken from.
                as_of=consult.created_at,
            )
            consult.quota_released = True

    db.flush()
    return consult


def _is_refundable(consult: Consult, moment: datetime) -> bool:
    return consult.scheduled_for - moment >= timedelta(hours=clinical.CONSULT_CANCELLATION_HOURS)


def complete(
    db: Session, consult: Consult, user: User, summary: str | None = None
) -> Consult:
    if consult.status != ConsultStatus.SCHEDULED:
        raise BadRequestError("This consult is no longer scheduled.")
    consult.status = ConsultStatus.COMPLETED
    consult.completed_at = now()
    consult.summary = (summary or "").strip() or None
    db.flush()
    return consult


def mark_no_show(db: Session, consult: Consult, user: User) -> Consult:
    """A missed consult is **not** refunded. The doctor's time was held."""
    if consult.status != ConsultStatus.SCHEDULED:
        raise BadRequestError("This consult is no longer scheduled.")
    consult.status = ConsultStatus.NO_SHOW
    db.flush()
    return consult


def list_for_patient(db: Session, patient_id: int, limit: int = 50) -> list[Consult]:
    return list(
        db.scalars(
            select(Consult)
            .options(selectinload(Consult.patient))
            .where(Consult.patient_id == patient_id)
            .order_by(Consult.scheduled_for.desc(), Consult.id.desc())
            .limit(limit)
        )
    )


def list_upcoming(db: Session, limit: int = 100) -> list[Consult]:
    return list(
        db.scalars(
            select(Consult)
            .options(selectinload(Consult.patient))
            .where(
                Consult.status == ConsultStatus.SCHEDULED,
                Consult.scheduled_for >= now(),
            )
            .order_by(Consult.scheduled_for, Consult.id)
            .limit(limit)
        )
    )


def get_for_user(db: Session, user: User, consult_id: int) -> Consult:
    """Someone else's consult is a 404, exactly as their patient is."""
    from ..core.dependencies import authorize_patient

    consult = db.scalar(
        select(Consult).options(selectinload(Consult.patient)).where(Consult.id == consult_id)
    )
    if consult is None:
        raise NotFoundError("Consult not found.")
    try:
        authorize_patient(db, user, consult.patient_id)
    except NotFoundError:
        raise NotFoundError("Consult not found.") from None
    return consult


def serialize(consult: Consult) -> dict[str, Any]:
    return {
        "id": consult.id,
        "patient_id": consult.patient_id,
        "patient_name": consult.patient.name if consult.patient else None,
        "scheduled_for": consult.scheduled_for,
        "duration_minutes": consult.duration_minutes,
        "status": consult.status.value,
        "reason": consult.reason,
        "doctor_name": consult.doctor_name,
        "cancelled_at": consult.cancelled_at,
        "cancellation_reason": consult.cancellation_reason,
        "quota_released": consult.quota_released,
        "completed_at": consult.completed_at,
        "summary": consult.summary,
        "created_at": consult.created_at,
    }
