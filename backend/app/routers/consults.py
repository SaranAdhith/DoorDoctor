"""Doctor video consult endpoints (§4.6).

Booking is family or admin — a nurse does not spend a family's allowance.
Completing or marking a no-show is admin-only: those are the operator's record
of what happened, not the customer's.

A refused booking is **409**, not 403. The family is entitled to book consults;
they have used this month's. The client needs to tell those apart without
parsing a sentence.
"""

from typing import Any

from fastapi import APIRouter, status

from ..core import clinical
from ..core.dependencies import (
    AdminUser,
    CurrentUser,
    DbSession,
    FamilyOrAdminUser,
    authorize_patient,
)
from ..schemas.telemedicine import (
    ConsultAllowanceOut,
    ConsultCancel,
    ConsultComplete,
    ConsultCreate,
    ConsultOut,
)
from ..services import consult_service

router = APIRouter(tags=["telemedicine"])


@router.get(
    "/patients/{patient_id}/consults/allowance",
    response_model=ConsultAllowanceOut,
    summary="Consults included this period, and how many are left",
)
def get_allowance(patient_id: int, current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    patient = authorize_patient(db, current_user, patient_id)
    payload = consult_service.allowance(db, patient)
    payload["duration_minutes"] = clinical.CONSULT_DURATION_MINUTES
    payload["cancellation_hours"] = clinical.CONSULT_CANCELLATION_HOURS
    return payload


@router.post(
    "/patients/{patient_id}/consults",
    response_model=ConsultOut,
    status_code=status.HTTP_201_CREATED,
    summary="Book a doctor consult (family or admin)",
)
def book_consult(
    patient_id: int, payload: ConsultCreate, current_user: FamilyOrAdminUser, db: DbSession
) -> dict[str, Any]:
    patient = authorize_patient(db, current_user, patient_id)
    consult = consult_service.book(
        db,
        patient=patient,
        user=current_user,
        scheduled_for=payload.scheduled_for,
        reason=payload.reason,
    )
    db.commit()
    db.refresh(consult)
    return consult_service.serialize(consult)


@router.get(
    "/patients/{patient_id}/consults",
    response_model=list[ConsultOut],
    summary="Consults for a patient",
)
def list_consults(patient_id: int, current_user: CurrentUser, db: DbSession) -> list[dict[str, Any]]:
    patient = authorize_patient(db, current_user, patient_id)
    return [consult_service.serialize(c) for c in consult_service.list_for_patient(db, patient.id)]


@router.get("/consults/upcoming", response_model=list[ConsultOut], summary="Upcoming consults (admin)")
def list_upcoming(current_user: AdminUser, db: DbSession) -> list[dict[str, Any]]:
    return [consult_service.serialize(c) for c in consult_service.list_upcoming(db)]


@router.post(
    "/consults/{consult_id}/cancel",
    response_model=ConsultOut,
    summary="Cancel a consult (family or admin)",
)
def cancel_consult(
    consult_id: int,
    current_user: FamilyOrAdminUser,
    db: DbSession,
    payload: ConsultCancel | None = None,
) -> dict[str, Any]:
    consult = consult_service.get_for_user(db, current_user, consult_id)
    reason = payload.reason if payload is not None else None
    consult_service.cancel(db, consult, current_user, reason=reason)
    db.commit()
    db.refresh(consult)
    return consult_service.serialize(consult)


@router.post(
    "/consults/{consult_id}/complete",
    response_model=ConsultOut,
    summary="Record that a consult happened (admin)",
)
def complete_consult(
    consult_id: int,
    current_user: AdminUser,
    db: DbSession,
    payload: ConsultComplete | None = None,
) -> dict[str, Any]:
    consult = consult_service.get_for_user(db, current_user, consult_id)
    summary = payload.summary if payload is not None else None
    consult_service.complete(db, consult, current_user, summary=summary)
    db.commit()
    db.refresh(consult)
    return consult_service.serialize(consult)


@router.post(
    "/consults/{consult_id}/no-show",
    response_model=ConsultOut,
    summary="Record a missed consult (admin)",
)
def no_show_consult(consult_id: int, current_user: AdminUser, db: DbSession) -> dict[str, Any]:
    consult = consult_service.get_for_user(db, current_user, consult_id)
    consult_service.mark_no_show(db, consult, current_user)
    db.commit()
    db.refresh(consult)
    return consult_service.serialize(consult)
