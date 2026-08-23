"""Nurse directory, credentials and the family-facing profile (§4.10).

`GET /nurses` moved here from `routers/admin.py` — the path is unchanged, the
payload is a superset of what it returned before, and everything about a nurse
now lives in one router.

The family-facing profile is deliberately reached through the **patient**:
`/patients/{patient_id}/nurses/...`. A family member is entitled to know about
the nurse who comes to *their* relative, and the route shape is what enforces
that — there is no `/nurses/{id}` a family can call.
"""

from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from ..core.dependencies import AdminUser, CurrentUser, DbSession, authorize_patient
from ..core.exceptions import NotFoundError
from ..models import NurseCredential, Visit
from ..schemas.nurse import (
    CredentialAdminOut,
    CredentialCreate,
    CredentialDecision,
    NurseAdminOut,
    NurseProfileOut,
    NurseUpdate,
)
from ..services import nurse_service

router = APIRouter(tags=["nurses"])


# --- admin ---------------------------------------------------------------


@router.get("/nurses", response_model=list[NurseAdminOut], summary="Nurse directory (admin)")
def list_nurses(db: DbSession, current_user: AdminUser) -> list[dict[str, Any]]:
    return nurse_service.list_for_admin(db)


@router.get("/nurses/{nurse_id}", response_model=NurseAdminOut, summary="Nurse record (admin)")
def get_nurse(nurse_id: int, db: DbSession, current_user: AdminUser) -> dict[str, Any]:
    return nurse_service.admin_profile(db, nurse_service.get_nurse(db, nurse_id))


@router.patch("/nurses/{nurse_id}", response_model=NurseAdminOut, summary="Update a nurse (admin)")
def update_nurse(
    nurse_id: int, payload: NurseUpdate, db: DbSession, current_user: AdminUser
) -> dict[str, Any]:
    nurse = nurse_service.get_nurse(db, nurse_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(nurse, field, value)
    db.commit()
    db.refresh(nurse)
    return nurse_service.admin_profile(db, nurse)


@router.post(
    "/nurses/{nurse_id}/credentials",
    response_model=CredentialAdminOut,
    status_code=201,
    summary="Record a credential (admin)",
)
def add_credential(
    nurse_id: int, payload: CredentialCreate, db: DbSession, current_user: AdminUser
) -> dict[str, Any]:
    """Recording a credential is not verifying it — it starts `pending`."""
    nurse = nurse_service.get_nurse(db, nurse_id)
    credential = nurse_service.add_credential(db, nurse, **payload.model_dump())
    return nurse_service._credential_admin(credential, credential.created_at.date())


@router.post(
    "/nurse-credentials/{credential_id}/verify",
    response_model=CredentialAdminOut,
    summary="Verify a credential (admin)",
)
def verify_credential(
    credential_id: int, payload: CredentialDecision, db: DbSession, current_user: AdminUser
) -> dict[str, Any]:
    credential = _credential(db, credential_id)
    credential = nurse_service.verify_credential(
        db, credential, verifier=current_user, note=payload.note
    )
    return nurse_service._credential_admin(credential, credential.created_at.date())


@router.post(
    "/nurse-credentials/{credential_id}/reject",
    response_model=CredentialAdminOut,
    summary="Reject a credential (admin)",
)
def reject_credential(
    credential_id: int, payload: CredentialDecision, db: DbSession, current_user: AdminUser
) -> dict[str, Any]:
    credential = _credential(db, credential_id)
    credential = nurse_service.reject_credential(
        db, credential, verifier=current_user, note=payload.note
    )
    return nurse_service._credential_admin(credential, credential.created_at.date())


def _credential(db: DbSession, credential_id: int) -> NurseCredential:
    credential = db.get(NurseCredential, credential_id)
    if credential is None:
        raise NotFoundError("Credential not found.")
    return credential


# --- family --------------------------------------------------------------


@router.get(
    "/patients/{patient_id}/nurses",
    response_model=list[NurseProfileOut],
    summary="Nurses who have visited this patient",
)
def patient_nurses(
    patient_id: int, db: DbSession, current_user: CurrentUser
) -> list[dict[str, Any]]:
    """Everyone who has been to this house, most recent first.

    Only nurses with a visit to *this* patient appear. The directory is not
    browsable from here — a family knows their own nurses, not the roster.
    """
    patient = authorize_patient(db, current_user, patient_id)
    nurse_ids = db.scalars(
        select(Visit.nurse_id)
        .where(Visit.patient_id == patient.id, Visit.nurse_id.is_not(None))
        .order_by(Visit.scheduled_at.desc())
    ).all()
    seen: list[int] = list(dict.fromkeys(int(n) for n in nurse_ids))
    return [
        nurse_service.family_profile(db, nurse_service.get_nurse(db, nurse_id), patient_id=patient.id)
        for nurse_id in seen
    ]


@router.get(
    "/patients/{patient_id}/nurses/{nurse_id}",
    response_model=NurseProfileOut,
    summary="The nurse who visits this patient",
)
def patient_nurse(
    patient_id: int, nurse_id: int, db: DbSession, current_user: CurrentUser
) -> dict[str, Any]:
    patient = authorize_patient(db, current_user, patient_id)
    nurse = nurse_service.get_nurse(db, nurse_id)
    has_visited = db.scalar(
        select(Visit.id).where(Visit.patient_id == patient.id, Visit.nurse_id == nurse.id).limit(1)
    )
    if has_visited is None:
        # A 404 rather than a 403: whether a given nurse exists is not something
        # a family learns by guessing ids.
        raise NotFoundError("Nurse not found.")
    return nurse_service.family_profile(db, nurse, patient_id=patient.id)
