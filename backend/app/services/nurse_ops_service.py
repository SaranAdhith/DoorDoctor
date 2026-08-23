"""A nurse's working day (§4.16).

Four things a nurse needs and a table of visits does not give them:

* **My day** — the worklist in the order it is worked, with yesterday's
  unfinished visits at the top rather than buried under today's.
* **The next-visit brief** — what happened last time, what is open, what is due.
  Assembled server-side from what Phases 5-9 already store, because a nurse
  standing at a door on a phone should not be opening four screens.
* **Hub check-in** — the start of the shift, classified by the same geofence
  arithmetic as a visit check-in.
* **The roster** — their own week.

Nothing here invents a number. Everything is read from rows other services wrote.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..core.exceptions import BadRequestError, NotFoundError
from ..core.ops import HUB_GEOFENCE_RADIUS_M, ZONE_HUBS
from ..database import now
from ..models import (
    Alert,
    AlertStatus,
    FollowUpTask,
    LocationStatus,
    Medication,
    MedicationLog,
    Nurse,
    Patient,
    SafetyScore,
    ShiftCheckIn,
    TaskStatus,
    Visit,
    VisitStatus,
    Vital,
)
from . import location_service, medication_service, vitals_service

OPEN_STATUSES = (VisitStatus.SCHEDULED, VisitStatus.IN_PROGRESS)


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min)
    return start, start + timedelta(days=1)


# --- the day --------------------------------------------------------------


def my_day(db: Session, nurse: Nurse, *, on: date | None = None) -> dict[str, Any]:
    """Today's worklist, plus anything still open from before it.

    Unfinished work from an earlier day sorts **first**, not last. A visit left
    open on Tuesday is the most urgent thing on Wednesday's list, and a
    chronological sort would put it at the bottom where it stays forever.
    """
    day = on or now().date()
    start, end = _day_bounds(day)

    visits = list(
        db.scalars(
            select(Visit)
            .options(selectinload(Visit.patient))
            .where(
                Visit.nurse_id == nurse.id,
                (
                    (Visit.scheduled_at >= start) & (Visit.scheduled_at < end)
                )
                | ((Visit.scheduled_at < start) & Visit.status.in_(OPEN_STATUSES)),
            )
            .order_by(Visit.scheduled_at)
        )
    )

    overdue = [visit for visit in visits if visit.scheduled_at < start]
    today = [visit for visit in visits if visit.scheduled_at >= start]

    shift = open_shift(db, nurse)
    return {
        "date": day,
        "nurse_id": nurse.id,
        "zone": nurse.zone,
        "shift": serialize_shift(shift) if shift else None,
        "carried_over": [_worklist_entry(db, visit, carried_over=True) for visit in overdue],
        "visits": [_worklist_entry(db, visit) for visit in today],
        "counts": {
            "total": len(visits),
            "completed": sum(1 for v in today if v.status == VisitStatus.COMPLETED),
            "remaining": sum(1 for v in visits if v.status in OPEN_STATUSES),
            "carried_over": len(overdue),
        },
        "tasks": [
            {
                "id": task.id,
                "patient_id": task.patient_id,
                "title": task.title,
                "due_at": task.due_at,
                "overdue": task.due_at < now(),
            }
            for task in db.scalars(
                select(FollowUpTask)
                .where(
                    FollowUpTask.assigned_user_id == nurse.user_id,
                    FollowUpTask.status == TaskStatus.OPEN,
                )
                .order_by(FollowUpTask.due_at)
                .limit(20)
            )
        ],
    }


def _worklist_entry(db: Session, visit: Visit, *, carried_over: bool = False) -> dict[str, Any]:
    patient = visit.patient
    open_alerts = (
        db.scalar(
            select(func.count(Alert.id)).where(
                Alert.patient_id == visit.patient_id,
                Alert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]),
            )
        )
        or 0
    )
    return {
        "id": visit.id,
        "patient_id": visit.patient_id,
        "patient_name": patient.name if patient else "",
        "address": patient.address if patient else "",
        "zone": patient.zone if patient else None,
        "scheduled_at": visit.scheduled_at,
        "status": visit.status.value,
        "location_status": visit.location_status.value,
        "open_alerts": int(open_alerts),
        "carried_over": carried_over,
    }


# --- the brief ------------------------------------------------------------


def visit_brief(db: Session, visit: Visit) -> dict[str, Any]:
    """Everything worth knowing before knocking, on one screen.

    Read-only and assembled from stored rows. It computes nothing new — a brief
    that derived its own numbers would be a second opinion about the same
    patient sitting beside the first.
    """
    patient = db.get(Patient, visit.patient_id)
    if patient is None:  # pragma: no cover - defensive
        raise NotFoundError("Patient not found.")

    previous = db.scalar(
        select(Visit)
        .where(
            Visit.patient_id == patient.id,
            Visit.id != visit.id,
            Visit.status == VisitStatus.COMPLETED,
            Visit.scheduled_at <= visit.scheduled_at,
        )
        .order_by(Visit.scheduled_at.desc())
        .limit(1)
    )
    last_reading = db.scalar(
        select(Vital)
        .where(Vital.patient_id == patient.id)
        .order_by(Vital.recorded_at.desc())
        .limit(1)
    )
    open_alerts = list(
        db.scalars(
            select(Alert)
            .where(
                Alert.patient_id == patient.id,
                Alert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]),
            )
            .order_by(Alert.created_at.desc())
            .limit(5)
        )
    )
    score = db.scalar(
        select(SafetyScore)
        .where(SafetyScore.patient_id == patient.id)
        .order_by(SafetyScore.calculated_at.desc())
        .limit(1)
    )
    organiser = medication_service.latest_fill(db, patient.id)

    return {
        "visit_id": visit.id,
        "patient": {
            "id": patient.id,
            "name": patient.name,
            "age": patient.age,
            "address": patient.address,
            "zone": patient.zone,
            "emergency_contact": patient.emergency_contact,
        },
        "scheduled_at": visit.scheduled_at,
        "last_visit": (
            {
                "id": previous.id,
                "scheduled_at": previous.scheduled_at,
                "notes": previous.notes,
                "location_status": previous.location_status.value,
            }
            if previous
            else None
        ),
        "last_reading": vitals_service.serialize(last_reading) if last_reading else None,
        "open_alerts": [
            {
                "id": alert.id,
                "title": alert.title,
                "severity": alert.severity.value,
                "created_at": alert.created_at,
            }
            for alert in open_alerts
        ],
        "medications_due": [
            medication_service.serialize(medication)
            for medication in medication_service.list_medications(
                db, patient.id, active_only=True
            )
        ],
        "doses_logged_here": [
            medication_service.serialize_log(log)
            for log in medication_service.logs_for_visit(db, visit.id)
        ],
        "safety": (
            {"score": score.score, "band": score.band.value, "calculated_at": score.calculated_at}
            if score
            else None
        ),
        "pill_organiser": medication_service.serialize_fill(organiser) if organiser else None,
    }


# --- the shift ------------------------------------------------------------


def open_shift(db: Session, nurse: Nurse) -> ShiftCheckIn | None:
    return db.scalar(
        select(ShiftCheckIn)
        .where(ShiftCheckIn.nurse_id == nurse.id, ShiftCheckIn.ended_at.is_(None))
        .order_by(ShiftCheckIn.started_at.desc())
        .limit(1)
    )


def hub_check_in(
    db: Session,
    nurse: Nurse,
    *,
    lat: float | None = None,
    lng: float | None = None,
    accuracy_m: float | None = None,
    note: str | None = None,
) -> ShiftCheckIn:
    """Start a shift at the zone hub, classified by the same geofence code.

    A wider radius than a home's, because a hub is a building with a car park
    and a nurse checking in from the gate is at work. A nurse whose zone has no
    recorded hub gets `unavailable`, which is the true answer rather than a
    guess.
    """
    if open_shift(db, nurse) is not None:
        raise BadRequestError("This shift is already open. Check out of it first.")

    hub = ZONE_HUBS.get(nurse.zone or "")
    verdict = location_service.classify(
        fix_lat=lat,
        fix_lng=lng,
        home_lat=hub[0] if hub else None,
        home_lng=hub[1] if hub else None,
        accuracy_m=accuracy_m,
        radius_m=HUB_GEOFENCE_RADIUS_M,
    )

    shift = ShiftCheckIn(
        nurse_id=nurse.id,
        zone=nurse.zone,
        started_at=now(),
        lat=lat,
        lng=lng,
        location_source=verdict.source,
        location_status=verdict.status,
        location_distance_m=verdict.distance_m,
        location_accuracy_m=verdict.accuracy_m,
        location_detail=verdict.detail,
        note=(note or "").strip() or None,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


def hub_check_out(db: Session, nurse: Nurse) -> ShiftCheckIn:
    shift = open_shift(db, nurse)
    if shift is None:
        raise BadRequestError("There is no open shift to close.")
    shift.ended_at = now()
    db.commit()
    db.refresh(shift)
    return shift


def serialize_shift(shift: ShiftCheckIn) -> dict[str, Any]:
    return {
        "id": shift.id,
        "nurse_id": shift.nurse_id,
        "zone": shift.zone,
        "started_at": shift.started_at,
        "ended_at": shift.ended_at,
        "location_status": shift.location_status.value,
        "location_distance_m": shift.location_distance_m,
        "location_accuracy_m": shift.location_accuracy_m,
        "location_detail": shift.location_detail,
        "note": shift.note,
        "is_open": shift.is_open,
    }


# --- the roster -----------------------------------------------------------


def roster(db: Session, nurse: Nurse, *, days: int = 7, start: date | None = None) -> dict[str, Any]:
    """The nurse's own week, grouped by day."""
    first = start or now().date()
    begin = datetime.combine(first, time.min)
    end = begin + timedelta(days=days)

    visits = list(
        db.scalars(
            select(Visit)
            .options(selectinload(Visit.patient))
            .where(
                Visit.nurse_id == nurse.id,
                Visit.scheduled_at >= begin,
                Visit.scheduled_at < end,
            )
            .order_by(Visit.scheduled_at)
        )
    )

    by_day: dict[str, list[dict[str, Any]]] = {}
    for visit in visits:
        key = visit.scheduled_at.date().isoformat()
        by_day.setdefault(key, []).append(_worklist_entry(db, visit))

    return {
        "from": first,
        "to": (begin + timedelta(days=days - 1)).date(),
        "days": [
            {"date": (first + timedelta(days=offset)).isoformat(),
             "visits": by_day.get((first + timedelta(days=offset)).isoformat(), [])}
            for offset in range(days)
        ],
        "total": len(visits),
    }
