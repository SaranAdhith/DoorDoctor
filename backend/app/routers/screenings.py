"""PHQ-2 screening endpoints (§4.7).

A screening is **recorded by staff** — a nurse during a visit, or an admin. A
family reads the result but does not self-administer: the instrument's validity
depends on it being asked, not filled in, and a self-scored PHQ-2 that then
opens a task for a nurse would be a very easy thing to game or to misuse.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from ..core import clinical
from ..core.dependencies import CurrentUser, DbSession, authorize_patient, require_roles
from ..models import User, UserRole
from ..schemas.screening import (
    ScreeningCreate,
    ScreeningInstrumentOut,
    ScreeningOut,
    ScreeningStatusOut,
)
from ..services import screening_service

StaffUser = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.NURSE))]

router = APIRouter(tags=["screenings"])


@router.get(
    "/screenings/instruments/phq2",
    response_model=ScreeningInstrumentOut,
    summary="The PHQ-2 questionnaire",
)
def get_instrument(current_user: CurrentUser) -> dict[str, Any]:
    """Served rather than hard-coded in the client, so the wording of a
    published instrument lives in exactly one place."""
    return screening_service.instrument_definition()


@router.post(
    "/patients/{patient_id}/screenings",
    response_model=ScreeningOut,
    status_code=status.HTTP_201_CREATED,
    summary="Record a PHQ-2 (nurse or admin)",
)
def record_screening(
    patient_id: int, payload: ScreeningCreate, current_user: StaffUser, db: DbSession
) -> dict[str, Any]:
    patient = authorize_patient(db, current_user, patient_id)
    screening = screening_service.record(
        db,
        patient=patient,
        user=current_user,
        answers=payload.answers,
        visit_id=payload.visit_id,
        note=payload.note,
    )
    db.commit()
    db.refresh(screening)
    return screening_service.serialize(screening)


@router.get(
    "/patients/{patient_id}/screenings",
    response_model=list[ScreeningOut],
    summary="Screening history for a patient",
)
def list_screenings(patient_id: int, current_user: CurrentUser, db: DbSession) -> list[dict[str, Any]]:
    patient = authorize_patient(db, current_user, patient_id)
    return [screening_service.serialize(s) for s in screening_service.list_for_patient(db, patient.id)]


@router.get(
    "/patients/{patient_id}/screenings/status",
    response_model=ScreeningStatusOut,
    summary="Whether a screening is due, and the last one",
)
def screening_status(patient_id: int, current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    patient = authorize_patient(db, current_user, patient_id)
    latest = screening_service.latest(db, patient.id)
    return {
        "patient_id": patient.id,
        "due": screening_service.is_due(db, patient.id),
        "cadence_days": clinical.PHQ2_CADENCE_DAYS,
        "latest": screening_service.serialize(latest) if latest else None,
    }
