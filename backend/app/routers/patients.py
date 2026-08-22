"""Patient profile, dashboard, threshold and medication endpoints."""

from typing import Any, Literal

from fastapi import APIRouter, status
from sqlalchemy import select

from ..core.dependencies import CurrentUser, DbSession, authorize_patient, require_family_or_admin
from ..core.exceptions import ForbiddenError
from ..models import Patient, PatientThreshold, User, UserRole, VitalMetric
from ..schemas.medication import MedicationCreate, MedicationOut
from ..schemas.patient import (
    AdherenceOut,
    DashboardOut,
    PatientOut,
    ThresholdOut,
    ThresholdUpdate,
)
from ..schemas.summary import PlainSummaryOut
from ..services import dashboard_service, medication_service, summary_service, vitals_service

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientOut], summary="Patients visible to the current user")
def list_patients(current_user: CurrentUser, db: DbSession) -> list[Patient]:
    query = select(Patient).order_by(Patient.name)
    if current_user.role == UserRole.FAMILY:
        query = query.where(Patient.family_user_id == current_user.id)
    elif current_user.role == UserRole.NURSE:
        # Nurses reach patients through their assigned visits, not this directory.
        raise ForbiddenError("Nurses access patients through their assigned visits.")
    return list(db.scalars(query))


@router.get("/{patient_id}", response_model=PatientOut, summary="Patient profile")
def get_patient(patient_id: int, current_user: CurrentUser, db: DbSession) -> Patient:
    return authorize_patient(db, current_user, patient_id)


@router.get("/{patient_id}/dashboard", response_model=DashboardOut, summary="Aggregated family dashboard")
def get_dashboard(patient_id: int, current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    patient = authorize_patient(db, current_user, patient_id)
    return dashboard_service.build_dashboard(db, patient)


@router.get(
    "/{patient_id}/plain-summary",
    response_model=PlainSummaryOut,
    summary="Plain-language health summary",
)
def plain_summary(
    patient_id: int,
    current_user: CurrentUser,
    db: DbSession,
    window: Literal["7d", "30d", "90d"] = "7d",
) -> dict[str, Any]:
    """The dashboard in the language a family member actually speaks.

    `window` is a `Literal`, so an unrecognised value is a 422 rather than a
    silent fall back to 7 days — a summary that quietly answers a different
    question than the one asked is worse than an error.
    """
    patient = authorize_patient(db, current_user, patient_id)
    return summary_service.plain_summary(db, patient, window)


@router.get("/{patient_id}/medications", response_model=list[MedicationOut], summary="Medication schedule")
def list_medications(patient_id: int, current_user: CurrentUser, db: DbSession):
    patient = authorize_patient(db, current_user, patient_id)
    return medication_service.list_medications(db, patient.id)


@router.post(
    "/{patient_id}/medications",
    response_model=MedicationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a medication to the schedule",
)
def create_medication(
    patient_id: int,
    payload: MedicationCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    if current_user.role not in (UserRole.FAMILY, UserRole.ADMIN):
        raise ForbiddenError("Only a family member or admin can change the medication schedule.")
    patient = authorize_patient(db, current_user, patient_id)
    return medication_service.create_medication(db, patient.id, payload)


@router.get(
    "/{patient_id}/medication-adherence",
    response_model=AdherenceOut,
    summary="Medication adherence for a patient",
)
def medication_adherence(patient_id: int, current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    patient = authorize_patient(db, current_user, patient_id)
    return medication_service.adherence_for_patient(db, patient.id)


@router.get("/{patient_id}/thresholds", response_model=list[ThresholdOut], summary="Monitoring thresholds")
def list_thresholds(patient_id: int, current_user: CurrentUser, db: DbSession):
    patient = authorize_patient(db, current_user, patient_id)
    return vitals_service.load_thresholds(db, patient.id)


@router.put(
    "/{patient_id}/thresholds",
    response_model=list[ThresholdOut],
    summary="Update monitoring thresholds (family or admin)",
)
def update_thresholds(
    patient_id: int,
    payload: list[ThresholdUpdate],
    db: DbSession,
    current_user: CurrentUser,
):
    if current_user.role not in (UserRole.FAMILY, UserRole.ADMIN):
        raise ForbiddenError("Only a family member or admin can configure thresholds.")
    patient = authorize_patient(db, current_user, patient_id)

    existing = {t.metric: t for t in vitals_service.load_thresholds(db, patient.id)}
    for item in payload:
        metric = VitalMetric(item.metric)
        threshold = existing.get(metric)
        if threshold is None:
            threshold = PatientThreshold(patient_id=patient.id, metric=metric)
            db.add(threshold)
        threshold.low_threshold = item.low_threshold
        threshold.high_threshold = item.high_threshold
        threshold.enabled = item.enabled
    db.commit()
    return vitals_service.load_thresholds(db, patient.id)
