"""Onboarding a new family (§4.15)."""

from typing import Any

from fastapi import APIRouter

from ..core.dependencies import CurrentUser, DbSession, authorize_patient
from ..services import onboarding_service

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/patients/{patient_id}", response_model=dict, summary="Setup progress")
def progress(patient_id: int, db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    """Four of the five steps are derived from the work itself, not from a tick."""
    patient = authorize_patient(db, current_user, patient_id)
    return onboarding_service.progress(db, current_user, patient)


@router.post(
    "/patients/{patient_id}/steps/{step}", response_model=dict, summary="Acknowledge a step"
)
def acknowledge(
    patient_id: int, step: str, db: DbSession, current_user: CurrentUser
) -> dict[str, Any]:
    patient = authorize_patient(db, current_user, patient_id)
    return onboarding_service.acknowledge(db, current_user, patient, step)
