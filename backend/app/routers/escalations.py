"""Escalation queue, timeline and hospital coordination (§4.3, §4.9)."""

from typing import Any

from fastapi import APIRouter, Query, status

from ..core import clinical
from ..core.dependencies import (
    AdminUser,
    CurrentUser,
    DbSession,
    FamilyOrAdminUser,
    authorize_patient,
)
from ..models import EscalationStatus, HospitalBookingStatus, UserRole
from ..schemas.escalation import (
    EmergencyBlockOut,
    EscalationOut,
    EscalationResolve,
    EscalationStepCreate,
    HospitalBookingCreate,
    HospitalBookingOut,
    HospitalBookingUpdate,
)
from ..services import escalation_service

router = APIRouter(tags=["escalations"])


@router.get(
    "/emergency",
    response_model=EmergencyBlockOut,
    summary="The permanent emergency block shown on every clinical screen",
)
def emergency_block(current_user: CurrentUser) -> dict[str, Any]:
    """Served rather than restated in eight components.

    The number and the ladder are recorded, and the assistant's emergency intent
    already uses them. One source means they cannot drift apart.
    """
    return {
        "number": clinical.EMERGENCY_NUMBER,
        "title": clinical.EMERGENCY_BLOCK_TITLE,
        "body": clinical.EMERGENCY_BLOCK_BODY,
        "ladder": list(clinical.ESCALATION_LADDER),
    }


# --------------------------------------------------------------------------
# Escalations
# --------------------------------------------------------------------------


@router.get("/escalations", response_model=list[EscalationOut], summary="Escalation queue (admin)")
def list_escalations(
    current_user: AdminUser,
    db: DbSession,
    escalation_status: EscalationStatus | None = Query(default=None, alias="status"),
) -> list[dict[str, Any]]:
    """Open first, soonest deadline first — the order an operator works them in."""
    events = escalation_service.list_events(db, status=escalation_status)
    db.commit()  # `list_events` stamps any SLA that has just breached
    return [escalation_service.serialize(e) for e in events]


@router.get(
    "/patients/{patient_id}/escalations",
    response_model=list[EscalationOut],
    summary="Escalations for one patient",
)
def list_patient_escalations(
    patient_id: int, current_user: CurrentUser, db: DbSession
) -> list[dict[str, Any]]:
    patient = authorize_patient(db, current_user, patient_id)
    events = escalation_service.list_events(db, patient_id=patient.id)
    db.commit()
    return [escalation_service.serialize(e) for e in events]


@router.get(
    "/escalations/{event_id}",
    response_model=EscalationOut,
    summary="One escalation with its full timeline",
)
def get_escalation(event_id: int, current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    event = escalation_service.get_for_user(db, current_user, event_id)
    db.commit()
    return escalation_service.serialize(event)


@router.post(
    "/escalations/{event_id}/acknowledge",
    response_model=EscalationOut,
    summary="Pick up an escalation (admin)",
)
def acknowledge_escalation(event_id: int, current_user: AdminUser, db: DbSession) -> dict[str, Any]:
    event = escalation_service.get_for_user(db, current_user, event_id)
    escalation_service.acknowledge(db, event, current_user)
    db.commit()
    db.refresh(event)
    return escalation_service.serialize(event)


@router.post(
    "/escalations/{event_id}/resolve",
    response_model=EscalationOut,
    summary="Close an escalation with a note (admin)",
)
def resolve_escalation(
    event_id: int,
    current_user: AdminUser,
    db: DbSession,
    payload: EscalationResolve | None = None,
) -> dict[str, Any]:
    event = escalation_service.get_for_user(db, current_user, event_id)
    note = payload.note if payload is not None else None
    escalation_service.resolve(db, event, current_user, note=note)
    db.commit()
    db.refresh(event)
    return escalation_service.serialize(event)


@router.post(
    "/escalations/{event_id}/steps",
    response_model=EscalationOut,
    summary="Record a contact attempt made by hand (admin)",
)
def add_escalation_step(
    event_id: int, payload: EscalationStepCreate, current_user: AdminUser, db: DbSession
) -> dict[str, Any]:
    """A phone call an admin actually made belongs on the same timeline as the
    automated contact. A record that only holds what the software did is not a
    record of what happened."""
    event = escalation_service.get_for_user(db, current_user, event_id)
    escalation_service.add_step(
        db,
        event,
        actor="Admin",
        channel=payload.channel,
        target=payload.target,
        detail=payload.detail,
    )
    db.commit()
    db.refresh(event)
    return escalation_service.serialize(event)


# --------------------------------------------------------------------------
# Hospital coordination
# --------------------------------------------------------------------------


@router.post(
    "/patients/{patient_id}/hospital-bookings",
    response_model=HospitalBookingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ask the team to coordinate a hospital visit (family or admin)",
)
def request_hospital(
    patient_id: int,
    payload: HospitalBookingCreate,
    current_user: FamilyOrAdminUser,
    db: DbSession,
) -> dict[str, Any]:
    patient = authorize_patient(db, current_user, patient_id)
    booking = escalation_service.request_hospital(
        db,
        patient=patient,
        user=current_user,
        hospital_name=payload.hospital_name,
        reason=payload.reason,
        department=payload.department,
        ambulance_required=payload.ambulance_required,
        preferred_at=payload.preferred_at,
    )
    db.commit()
    db.refresh(booking)
    return escalation_service.serialize_booking(booking)


@router.get(
    "/hospital-bookings",
    response_model=list[HospitalBookingOut],
    summary="Hospital coordination queue with SLA (admin)",
)
def list_hospital_bookings(
    current_user: AdminUser,
    db: DbSession,
    booking_status: HospitalBookingStatus | None = Query(default=None, alias="status"),
) -> list[dict[str, Any]]:
    bookings = escalation_service.list_hospital_bookings(db, status=booking_status)
    db.commit()
    return [escalation_service.serialize_booking(b) for b in bookings]


@router.get(
    "/patients/{patient_id}/hospital-bookings",
    response_model=list[HospitalBookingOut],
    summary="Hospital requests for one patient",
)
def list_patient_bookings(
    patient_id: int, current_user: CurrentUser, db: DbSession
) -> list[dict[str, Any]]:
    patient = authorize_patient(db, current_user, patient_id)
    bookings = escalation_service.list_hospital_bookings(db, patient_id=patient.id)
    db.commit()
    return [escalation_service.serialize_booking(b) for b in bookings]


@router.patch(
    "/hospital-bookings/{booking_id}",
    response_model=HospitalBookingOut,
    summary="Work a hospital request (admin)",
)
def update_hospital_booking(
    booking_id: int, payload: HospitalBookingUpdate, current_user: AdminUser, db: DbSession
) -> dict[str, Any]:
    booking = escalation_service.get_booking_for_user(db, current_user, booking_id)
    escalation_service.update_hospital(
        db,
        booking,
        current_user,
        status=payload.status,
        confirmation_detail=payload.confirmation_detail,
        notes=payload.notes,
    )
    db.commit()
    db.refresh(booking)
    return escalation_service.serialize_booking(booking)
