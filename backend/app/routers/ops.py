"""Nurse and admin operations (§4.16, §4.17).

Two audiences, one router, because they are two halves of the same day: the
nurse works the visits and the admin works the board they came off.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query

from ..core.dependencies import (
    AdminUser,
    CurrentUser,
    DbSession,
    NurseUser,
    authorize_visit,
    get_nurse_profile,
)
from ..models import VisitStatus
from ..schemas.ops import (
    HubCheckInRequest,
    ShiftCheckInOut,
)
from ..services import nurse_ops_service, ops_service

router = APIRouter(tags=["operations"])


# --- nurse ----------------------------------------------------------------


@router.get("/nurse/my-day", response_model=dict, summary="Today's worklist (nurse)")
def my_day(db: DbSession, current_user: NurseUser) -> dict[str, Any]:
    """Unfinished visits from earlier days sort first, not last."""
    nurse = get_nurse_profile(db, current_user)
    return nurse_ops_service.my_day(db, nurse)


@router.get("/nurse/roster", response_model=dict, summary="The week ahead (nurse)")
def roster(
    db: DbSession, current_user: NurseUser, days: int = Query(default=7, ge=1, le=31)
) -> dict[str, Any]:
    nurse = get_nurse_profile(db, current_user)
    return nurse_ops_service.roster(db, nurse, days=days)


@router.post(
    "/nurse/shift/checkin",
    response_model=ShiftCheckInOut,
    status_code=201,
    summary="Start a shift at the zone hub (nurse)",
)
def hub_check_in(
    payload: HubCheckInRequest, db: DbSession, current_user: NurseUser
) -> dict[str, Any]:
    nurse = get_nurse_profile(db, current_user)
    shift = nurse_ops_service.hub_check_in(
        db,
        nurse,
        lat=payload.lat,
        lng=payload.lng,
        accuracy_m=payload.accuracy_m,
        note=payload.note,
    )
    return nurse_ops_service.serialize_shift(shift)


@router.post(
    "/nurse/shift/checkout", response_model=ShiftCheckInOut, summary="End the shift (nurse)"
)
def hub_check_out(db: DbSession, current_user: NurseUser) -> dict[str, Any]:
    nurse = get_nurse_profile(db, current_user)
    return nurse_ops_service.serialize_shift(nurse_ops_service.hub_check_out(db, nurse))


@router.get(
    "/visits/{visit_id}/brief",
    response_model=dict,
    summary="What to know before knocking",
)
def visit_brief(visit_id: int, db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    """Read through the ordinary visit authorization, so a family can read it too."""
    visit = authorize_visit(db, current_user, visit_id)
    return nurse_ops_service.visit_brief(db, visit)


# --- admin ----------------------------------------------------------------


@router.get("/admin/visit-board", response_model=dict, summary="The visit board (admin)")
def visit_board(
    db: DbSession,
    current_user: AdminUser,
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    status: VisitStatus | None = Query(default=None),
    nurse_id: int | None = Query(default=None),
    zone: str | None = Query(default=None),
    unassigned: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    """A window of the schedule, paginated. Replaces the newest-250 visit list."""
    return ops_service.visit_board(
        db,
        date_from=date_from,
        date_to=date_to,
        status=status,
        nurse_id=nurse_id,
        zone=zone,
        unassigned=unassigned,
        page=page,
        page_size=page_size,
    )


@router.get("/admin/alert-queue", response_model=list[dict], summary="Alert queue with SLA (admin)")
def alert_queue(
    db: DbSession,
    current_user: AdminUser,
    include_resolved: bool = Query(default=False),
) -> list[dict[str, Any]]:
    """Breached first, then soonest deadline — the order an operator works it."""
    return ops_service.alert_queue(db, include_resolved=include_resolved)


@router.get("/admin/outcomes", response_model=dict, summary="Outcome metrics (admin)")
def outcomes(
    db: DbSession, current_user: AdminUser, days: int = Query(default=30, ge=1, le=365)
) -> dict[str, Any]:
    """Computed from rows on every read. There are no stored counters here."""
    return ops_service.outcomes(db, days=days)


@router.get("/admin/zones", response_model=dict, summary="Zone view (admin)")
def zones(db: DbSession, current_user: AdminUser) -> dict[str, Any]:
    """Where each zone sits against the recorded 30-45 subscriber break-even band."""
    return ops_service.zones(db)


@router.get("/admin/shifts", response_model=list[ShiftCheckInOut], summary="Open shifts (admin)")
def open_shifts(db: DbSession, current_user: AdminUser) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from ..models import ShiftCheckIn

    shifts = db.scalars(
        select(ShiftCheckIn).order_by(ShiftCheckIn.started_at.desc()).limit(50)
    ).all()
    return [nurse_ops_service.serialize_shift(shift) for shift in shifts]
