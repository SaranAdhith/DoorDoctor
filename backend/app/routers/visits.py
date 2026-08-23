"""Visit lifecycle endpoints: schedule, check in, record, complete."""

from typing import Any

from fastapi import APIRouter, Query, status

from ..core.dependencies import (
    AdminUser,
    CurrentUser,
    DbSession,
    authorize_nurse_visit,
    authorize_visit,
)
from ..models import Visit
from ..schemas.medication import MedicationLogCreate, MedicationLogOut
from ..schemas.visit import (
    CheckinRequest,
    VisitAssign,
    VisitCreate,
    VisitDetailOut,
    VisitNotesUpdate,
    VisitOut,
)
from ..schemas.vital import VitalCreate, VitalRecordResponse
from ..services import medication_service, visit_service, vitals_service

router = APIRouter(prefix="/visits", tags=["visits"])


def _detail_payload(db, visit: Visit) -> dict[str, Any]:
    data = visit_service.serialize(visit)
    data["vitals"] = [vitals_service.serialize(v) for v in visit.vitals]
    data["medications"] = [
        medication_service.serialize(m)
        for m in medication_service.list_medications(db, visit.patient_id, active_only=True)
    ]
    data["medication_logs"] = [
        medication_service.serialize_log(log) for log in medication_service.logs_for_visit(db, visit.id)
    ]
    return data


@router.get("", response_model=list[dict], summary="Visits visible to the current user")
def list_visits(
    current_user: CurrentUser,
    db: DbSession,
    visit_status: str | None = Query(default=None, alias="status"),
) -> list[dict[str, Any]]:
    visits = visit_service.list_visits_for_user(db, current_user, visit_status)
    return [visit_service.serialize(v) for v in visits]


@router.get("/today", response_model=list[dict], summary="Today's visits (plus anything still open)")
def list_today(current_user: CurrentUser, db: DbSession) -> list[dict[str, Any]]:
    return [visit_service.serialize(v) for v in visit_service.list_today_visits(db, current_user)]


@router.post(
    "", response_model=VisitOut, status_code=status.HTTP_201_CREATED, summary="Schedule a visit (admin)"
)
def create_visit(payload: VisitCreate, db: DbSession, current_user: AdminUser) -> Visit:
    return visit_service.create_visit(
        db,
        patient_id=payload.patient_id,
        nurse_id=payload.nurse_id,
        scheduled_at=payload.scheduled_at,
    )


@router.get("/{visit_id}", response_model=VisitDetailOut, summary="Visit detail")
def get_visit(visit_id: int, current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    visit = authorize_visit(db, current_user, visit_id)
    return _detail_payload(db, visit)


@router.post("/{visit_id}/assign", response_model=VisitOut, summary="Assign a nurse (admin)")
def assign_nurse(
    visit_id: int, payload: VisitAssign, db: DbSession, current_user: AdminUser
) -> Visit:
    visit = authorize_visit(db, current_user, visit_id)
    return visit_service.assign_nurse(db, visit, payload.nurse_id)


@router.post("/{visit_id}/checkin", response_model=VisitOut, summary="Start a visit (nurse)")
def check_in(
    visit_id: int, db: DbSession, current_user: CurrentUser, payload: CheckinRequest | None = None
) -> Visit:
    visit, _ = authorize_nurse_visit(db, current_user, visit_id)
    lat = payload.lat if payload else None
    lng = payload.lng if payload else None
    accuracy = payload.accuracy_m if payload else None
    return visit_service.check_in(db, visit, lat, lng, accuracy)


@router.post("/{visit_id}/checkout", response_model=VisitOut, summary="Check out of a visit (nurse)")
def check_out(visit_id: int, db: DbSession, current_user: CurrentUser) -> Visit:
    visit, _ = authorize_nurse_visit(db, current_user, visit_id)
    return visit_service.check_out(db, visit)


@router.post("/{visit_id}/notes", response_model=VisitOut, summary="Save visit observations (nurse)")
def save_notes(
    visit_id: int, payload: VisitNotesUpdate, db: DbSession, current_user: CurrentUser
) -> Visit:
    visit, _ = authorize_nurse_visit(db, current_user, visit_id)
    return visit_service.save_notes(db, visit, payload.notes)


@router.post(
    "/{visit_id}/vitals",
    response_model=VitalRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record vitals and run the threshold engine (nurse)",
)
def record_vitals(
    visit_id: int, payload: VitalCreate, db: DbSession, current_user: CurrentUser
) -> dict[str, Any]:
    visit, _ = authorize_nurse_visit(db, current_user, visit_id)
    return visit_service.record_vitals(db, visit, payload)


@router.post(
    "/{visit_id}/medication-logs",
    response_model=MedicationLogOut,
    status_code=status.HTTP_201_CREATED,
    summary="Log a medication dose (nurse)",
)
def log_medication(
    visit_id: int, payload: MedicationLogCreate, db: DbSession, current_user: CurrentUser
):
    visit, _ = authorize_nurse_visit(db, current_user, visit_id)
    return medication_service.log_administration(db, visit, payload, recorded_by=current_user.id)


@router.post("/{visit_id}/complete", response_model=VisitOut, summary="Complete a visit (nurse)")
def complete_visit(visit_id: int, db: DbSession, current_user: CurrentUser) -> Visit:
    visit, _ = authorize_nurse_visit(db, current_user, visit_id)
    return visit_service.complete_visit(db, visit)
