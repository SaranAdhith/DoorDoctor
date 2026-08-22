"""Care manager and interaction endpoints (§4.4).

Managing the roster is admin-only. A family reads their own care team and the
interactions marked family-visible — a care manager's job is to be seen doing
it, and an assignment nobody can see is indistinguishable from no assignment.
"""

from typing import Any

from fastapi import APIRouter, Query, status

from ..core.dependencies import (
    AdminUser,
    CurrentUser,
    DbSession,
    authorize_patient,
)
from ..core.exceptions import BadRequestError, NotFoundError
from ..models import CareManagerKind, User, UserRole
from ..schemas.care import (
    CareAssignmentCreate,
    CareAssignmentOut,
    CareInteractionCreate,
    CareInteractionOut,
    CareManagerCreate,
    CareManagerOut,
    CareTeamOut,
)
from ..services import care_service

router = APIRouter(tags=["care"])


@router.get("/care-managers", response_model=list[CareManagerOut], summary="Care managers (admin)")
def list_managers(
    current_user: AdminUser,
    db: DbSession,
    kind: CareManagerKind | None = Query(default=None),
) -> list[dict[str, Any]]:
    """Each row carries its caseload against the recorded 1:20 / 1:10 capacity."""
    return [care_service.serialize_manager(db, m) for m in care_service.list_managers(db, kind=kind)]


@router.post(
    "/care-managers",
    response_model=CareManagerOut,
    status_code=status.HTTP_201_CREATED,
    summary="Make an admin a care manager (admin)",
)
def create_manager(payload: CareManagerCreate, current_user: AdminUser, db: DbSession) -> dict[str, Any]:
    user = db.get(User, payload.user_id)
    if user is None:
        raise NotFoundError("User not found.")
    manager = care_service.create_manager(
        db, user=user, kind=payload.kind, languages=payload.languages, capacity=payload.capacity
    )
    db.commit()
    db.refresh(manager)
    return care_service.serialize_manager(db, manager)


@router.get(
    "/patients/{patient_id}/care-team",
    response_model=CareTeamOut,
    summary="The patient's care manager and recent contact",
)
def get_care_team(patient_id: int, current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    patient = authorize_patient(db, current_user, patient_id)
    for_family = current_user.role == UserRole.FAMILY
    assignment = care_service.current_assignment(db, patient.id)
    kind = care_service.entitled_kind(db, patient)
    return {
        "patient_id": patient.id,
        "entitled_kind": kind.value if kind else None,
        "assignment": care_service.serialize_assignment(assignment) if assignment else None,
        "interactions": [
            care_service.serialize_interaction(i)
            for i in care_service.list_interactions(db, patient.id, for_family=for_family)
        ],
    }


@router.post(
    "/patients/{patient_id}/care-team",
    response_model=CareAssignmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a care manager (admin)",
)
def assign_manager(
    patient_id: int, payload: CareAssignmentCreate, current_user: AdminUser, db: DbSession
) -> dict[str, Any]:
    """Named manager, or the least-loaded one of the kind the plan grants."""
    patient = authorize_patient(db, current_user, patient_id)

    if payload.care_manager_id is not None:
        manager = care_service.get_manager(db, payload.care_manager_id)
        assignment = care_service.assign(db, patient=patient, manager=manager)
    else:
        assignment = care_service.auto_assign(db, patient)
        if assignment is None:
            raise BadRequestError(
                "No care manager of the kind this plan includes has room. "
                "Assign one explicitly or raise a manager's capacity."
            )

    db.commit()
    db.refresh(assignment)
    return care_service.serialize_assignment(assignment)


@router.delete(
    "/patients/{patient_id}/care-team",
    response_model=CareAssignmentOut,
    summary="End the current assignment (admin)",
)
def end_assignment(patient_id: int, current_user: AdminUser, db: DbSession) -> dict[str, Any]:
    patient = authorize_patient(db, current_user, patient_id)
    assignment = care_service.current_assignment(db, patient.id)
    if assignment is None:
        raise NotFoundError("This patient has no care manager assigned.")
    care_service.end(db, assignment, reason="Ended by admin")
    db.commit()
    db.refresh(assignment)
    return care_service.serialize_assignment(assignment)


@router.post(
    "/patients/{patient_id}/care-interactions",
    response_model=CareInteractionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Log a care interaction (admin)",
)
def log_interaction(
    patient_id: int, payload: CareInteractionCreate, current_user: AdminUser, db: DbSession
) -> dict[str, Any]:
    patient = authorize_patient(db, current_user, patient_id)
    interaction = care_service.log_interaction(
        db,
        patient=patient,
        user=current_user,
        channel=payload.channel,
        subject=payload.subject,
        note=payload.note,
        direction=payload.direction,
        minutes=payload.minutes,
        visible_to_family=payload.visible_to_family,
    )
    db.commit()
    db.refresh(interaction)
    return care_service.serialize_interaction(interaction)


@router.get(
    "/patients/{patient_id}/care-interactions",
    response_model=list[CareInteractionOut],
    summary="Care interactions for a patient",
)
def list_interactions(
    patient_id: int, current_user: CurrentUser, db: DbSession
) -> list[dict[str, Any]]:
    """A family sees what was done for them. An admin also sees handover notes."""
    patient = authorize_patient(db, current_user, patient_id)
    for_family = current_user.role == UserRole.FAMILY
    return [
        care_service.serialize_interaction(i)
        for i in care_service.list_interactions(db, patient.id, for_family=for_family)
    ]
