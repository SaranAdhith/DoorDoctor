"""Care circle endpoints (§4.13).

A nurse **reads** the circle — they need to know who to call — and cannot edit
it, and they do not see everybody's phone number. Contact details belong to the
family; the nurse gets the primary contact and anyone marked as an emergency
contact, which is what an emergency actually needs.
"""

from typing import Any

from fastapi import APIRouter

from ..core.dependencies import CurrentUser, DbSession, authorize_patient
from ..core.exceptions import BadRequestError, ForbiddenError
from ..models import CareCircleRole, UserRole
from ..schemas.care_circle import (
    CareCircleMemberCreate,
    CareCircleMemberOut,
    CareCircleMemberUpdate,
)
from ..services import care_circle_service

router = APIRouter(tags=["care circle"])


@router.get(
    "/patients/{patient_id}/care-circle",
    response_model=list[CareCircleMemberOut],
    summary="Who is around this patient",
)
def list_circle(patient_id: int, db: DbSession, current_user: CurrentUser) -> list[dict[str, Any]]:
    patient = authorize_patient(db, current_user, patient_id)
    care_circle_service.ensure_primary(db, patient)
    db.commit()

    members = care_circle_service.list_members(db, patient.id)
    if current_user.role != UserRole.NURSE:
        return [care_circle_service.serialize(member) for member in members]

    return [
        care_circle_service.serialize(
            member,
            include_contact=member.is_primary
            or member.role == CareCircleRole.EMERGENCY_CONTACT,
        )
        for member in members
    ]


@router.post(
    "/patients/{patient_id}/care-circle",
    response_model=CareCircleMemberOut,
    status_code=201,
    summary="Add someone to the care circle",
)
def add_member(
    patient_id: int,
    payload: CareCircleMemberCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    patient = authorize_patient(db, current_user, patient_id)
    _require_editor(current_user)
    care_circle_service.ensure_primary(db, patient)
    member = care_circle_service.add_member(
        db,
        patient,
        actor=current_user,
        name=payload.name,
        relationship_label=payload.relationship_label,
        phone=payload.phone,
        email=payload.email,
        role=payload.role,
        receives_alerts=payload.receives_alerts,
        receives_reports=payload.receives_reports,
        note=payload.note,
    )
    return care_circle_service.serialize(member)


@router.patch(
    "/care-circle/{member_id}",
    response_model=CareCircleMemberOut,
    summary="Update a care circle member",
)
def update_member(
    member_id: int, payload: CareCircleMemberUpdate, db: DbSession, current_user: CurrentUser
) -> dict[str, Any]:
    member = care_circle_service.get_member(db, member_id)
    authorize_patient(db, current_user, member.patient_id)
    _require_editor(current_user)

    fields = payload.model_dump(exclude_unset=True)
    if member.is_primary and fields.get("receives_alerts") is False:
        raise BadRequestError("The primary contact always receives alerts.")

    member = care_circle_service.update_member(db, member, actor=current_user, **fields)
    return care_circle_service.serialize(member)


@router.delete(
    "/care-circle/{member_id}", status_code=204, summary="Remove someone from the care circle"
)
def remove_member(member_id: int, db: DbSession, current_user: CurrentUser) -> None:
    member = care_circle_service.get_member(db, member_id)
    authorize_patient(db, current_user, member.patient_id)
    _require_editor(current_user)
    care_circle_service.remove_member(db, member, actor=current_user)


def _require_editor(user) -> None:
    if user.role == UserRole.NURSE:
        raise ForbiddenError("A nurse can see the care circle but cannot change it.")
