"""Medication endpoints that are not scoped to a patient path.

Phase 10 (§4.12) adds the dose photograph, the pill organiser and the change
history. Three authorization shapes, and the difference between them is the
point:

* A **photo upload** is a nurse recording what they just did on a visit they
  are checked in to — `authorize_nurse_visit`.
* An **organiser fill** is the same kind of act and is billed, so a nurse or an
  admin may record one and a family may not record one against themselves.
* The **change history** is a family's own record of their relative's medicines
  and is read through `authorize_patient`, like everything else about them.
"""

from typing import Any

from fastapi import APIRouter, File, UploadFile

from ..core.dependencies import (
    CurrentUser,
    DbSession,
    authorize_nurse_visit,
    authorize_patient,
    authorize_visit,
)
from ..core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from ..core.ops import PHOTO_MAX_BYTES
from ..models import Medication, MedicationLog, UserRole, Visit
from ..schemas.medication import (
    MedicationChangeOut,
    MedicationLogOut,
    MedicationUpdate,
    PillOrganiserFillCreate,
    PillOrganiserFillOut,
)
from ..services import medication_service

router = APIRouter(tags=["medications"])


@router.get(
    "/medications/visit/{visit_id}/logs",
    response_model=list[MedicationLogOut],
    summary="Medication logs recorded during a visit",
)
def logs_for_visit(visit_id: int, current_user: CurrentUser, db: DbSession) -> list[Any]:
    visit = authorize_visit(db, current_user, visit_id)
    return [
        medication_service.serialize_log(log)
        for log in medication_service.logs_for_visit(db, visit.id)
    ]


@router.post(
    "/medications/logs/{log_id}/photo",
    response_model=MedicationLogOut,
    summary="Attach a dose confirmation photo (nurse)",
)
async def upload_dose_photo(
    log_id: int, db: DbSession, current_user: CurrentUser, file: UploadFile = File(...)
) -> dict[str, Any]:
    """Upload the photograph taken as the dose was given.

    Read with an explicit cap rather than trusting `UploadFile.size`, which is
    whatever the client's headers claimed. A 4 MB limit enforced against a
    declared length is not a limit.
    """
    log = db.get(MedicationLog, log_id)
    if log is None or log.visit_id is None:
        raise NotFoundError("Dose record not found.")

    # The nurse must own the visit the dose was recorded on, and it must still
    # be open — a photograph added to a closed visit is a photograph of nothing
    # anybody can now check.
    visit, _ = authorize_nurse_visit(db, current_user, log.visit_id)
    if not visit.is_editable:
        raise BadRequestError("A completed visit can no longer be edited.")

    data = await file.read(PHOTO_MAX_BYTES + 1)
    if len(data) > PHOTO_MAX_BYTES:
        raise BadRequestError(f"Photos must be under {PHOTO_MAX_BYTES // (1024 * 1024)} MB.")

    log = medication_service.attach_dose_photo(db, log, data=data, uploaded_by=current_user)
    return medication_service.serialize_log(log)


@router.patch(
    "/medications/{medication_id}",
    response_model=MedicationChangeOut | None,
    summary="Change a medication (family or admin)",
)
def update_medication(
    medication_id: int, payload: MedicationUpdate, db: DbSession, current_user: CurrentUser
) -> Any:
    """Edit a medication. Returns the newest history row, or null if nothing changed."""
    medication = db.get(Medication, medication_id)
    if medication is None:
        raise NotFoundError("Medication not found.")
    authorize_patient(db, current_user, medication.patient_id)
    if current_user.role == UserRole.NURSE:
        raise ForbiddenError("A nurse records doses; changing a prescription is not theirs to do.")

    medication_service.update_medication(
        db,
        medication,
        actor=current_user,
        **payload.model_dump(exclude_unset=True),
    )
    history = medication_service.change_history(db, medication.patient_id, limit=1)
    return medication_service.serialize_change(history[0]) if history else None


@router.get(
    "/patients/{patient_id}/medication-history",
    response_model=list[MedicationChangeOut],
    summary="Every change made to this patient's medicines",
)
def medication_history(
    patient_id: int, db: DbSession, current_user: CurrentUser
) -> list[dict[str, Any]]:
    patient = authorize_patient(db, current_user, patient_id)
    return [
        medication_service.serialize_change(change)
        for change in medication_service.change_history(db, patient.id)
    ]


@router.get(
    "/patients/{patient_id}/pill-organiser",
    response_model=list[PillOrganiserFillOut],
    summary="Pill organiser fills",
)
def list_fills(patient_id: int, db: DbSession, current_user: CurrentUser) -> list[dict[str, Any]]:
    patient = authorize_patient(db, current_user, patient_id)
    return [
        medication_service.serialize_fill(fill)
        for fill in medication_service.list_fills(db, patient.id)
    ]


@router.post(
    "/patients/{patient_id}/pill-organiser",
    response_model=PillOrganiserFillOut,
    status_code=201,
    summary="Record a pill organiser fill (nurse or admin)",
)
def record_fill(
    patient_id: int,
    payload: PillOrganiserFillCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Record a fill. The ₹199 add-on is billed once per month, not once per fill."""
    patient = authorize_patient(db, current_user, patient_id)
    if current_user.role == UserRole.FAMILY:
        raise ForbiddenError("A pill organiser is filled by the care team.")

    visit: Visit | None = None
    if payload.visit_id is not None:
        visit = authorize_visit(db, current_user, payload.visit_id)
        if visit.patient_id != patient.id:
            raise BadRequestError("That visit belongs to a different patient.")

    fill = medication_service.record_fill(
        db,
        patient=patient,
        filled_by=current_user,
        compartments_filled=payload.compartments_filled,
        visit=visit,
        note=payload.note,
    )
    return medication_service.serialize_fill(fill)
