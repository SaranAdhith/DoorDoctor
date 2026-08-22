"""Visit scheduling, lifecycle transitions and vitals capture during a visit."""

from datetime import datetime, time, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from ..core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from ..database import now
from ..models import (
    Alert,
    Nurse,
    Patient,
    User,
    UserRole,
    Visit,
    VisitStatus,
    Vital,
)
from ..schemas.vital import VitalCreate
from . import alert_service, vitals_service


def _day_bounds(day: datetime) -> tuple[datetime, datetime]:
    start = datetime.combine(day.date(), time.min)
    return start, start + timedelta(days=1)


# The visit list is capped so one request cannot pull a whole year of care.
# Phase 10's visit board replaces this with a windowed, paginated query; until
# then the cap has to clear a forward week plus enough history to be useful,
# because the rows come back newest-first.
VISIT_LIST_LIMIT = 250


def _visible_visits(db: Session, user: User):
    """The base query for what this user may see. `None` means: nothing at all."""
    query = select(Visit).options(selectinload(Visit.patient), selectinload(Visit.nurse))

    if user.role == UserRole.FAMILY:
        return query.join(Patient, Visit.patient_id == Patient.id).where(
            Patient.family_user_id == user.id
        )
    if user.role == UserRole.NURSE:
        nurse = db.scalar(select(Nurse).where(Nurse.user_id == user.id))
        if nurse is None:
            return None
        return query.where(Visit.nurse_id == nurse.id)
    return query


def list_visits_for_user(db: Session, user: User, status: str | None = None) -> list[Visit]:
    query = _visible_visits(db, user)
    if query is None:
        return []

    if status:
        query = query.where(Visit.status == status)

    return list(db.scalars(query.order_by(Visit.scheduled_at.desc()).limit(VISIT_LIST_LIMIT)))


def list_today_visits(db: Session, user: User) -> list[Visit]:
    """Visits scheduled for today.

    A nurse also keeps any still-open visit from an *earlier* day on their
    worklist, so unfinished work is never silently dropped. Admin screens stay
    strictly on today so the dashboard counts and the table agree.

    The day window is applied in the query, not to a page of results. Filtering
    a newest-first page of 100 rows worked while the database held six visits
    and returned an empty board once a forward schedule pushed more than 100
    visits past today — the day the demo grew to a real dataset, the operations
    dashboard would have shown nothing.
    """
    start, end = _day_bounds(now())
    query = _visible_visits(db, user)
    if query is None:
        return []

    today = and_(Visit.scheduled_at >= start, Visit.scheduled_at < end)
    if user.role == UserRole.NURSE:
        unfinished = and_(
            Visit.scheduled_at < start,
            Visit.status.in_([VisitStatus.SCHEDULED, VisitStatus.IN_PROGRESS]),
        )
        query = query.where(or_(today, unfinished))
    else:
        query = query.where(today)

    return list(db.scalars(query.order_by(Visit.scheduled_at)))


def create_visit(
    db: Session, *, patient_id: int, nurse_id: int | None, scheduled_at: datetime
) -> Visit:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise NotFoundError("Patient not found.")

    if nurse_id is not None:
        nurse = db.get(Nurse, nurse_id)
        if nurse is None:
            raise NotFoundError("Nurse not found.")

    visit = Visit(
        patient_id=patient_id,
        nurse_id=nurse_id,
        scheduled_at=scheduled_at,
        status=VisitStatus.SCHEDULED,
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit


def assign_nurse(db: Session, visit: Visit, nurse_id: int) -> Visit:
    if visit.status in (VisitStatus.COMPLETED, VisitStatus.CANCELLED):
        raise BadRequestError("A completed or cancelled visit cannot be reassigned.")

    nurse = db.get(Nurse, nurse_id)
    if nurse is None:
        raise NotFoundError("Nurse not found.")

    visit.nurse_id = nurse_id
    db.commit()
    db.refresh(visit)
    return visit


def check_in(db: Session, visit: Visit, lat: float | None = None, lng: float | None = None) -> Visit:
    """scheduled -> in_progress. Location is optional in the MVP."""
    if visit.status == VisitStatus.IN_PROGRESS:
        raise BadRequestError("This visit has already been started.")
    if visit.status != VisitStatus.SCHEDULED:
        raise BadRequestError(f"A visit with status '{visit.status.value}' cannot be started.")

    visit.status = VisitStatus.IN_PROGRESS
    visit.checkin_at = now()
    if lat is not None and lng is not None:
        visit.checkin_lat = lat
        visit.checkin_lng = lng
        visit.location_source = "browser"
    else:
        visit.location_source = "demo/unverified"

    db.commit()
    db.refresh(visit)
    return visit


def check_out(db: Session, visit: Visit) -> Visit:
    if visit.checkin_at is None:
        raise BadRequestError("Visit must be checked in before check-out.")
    if visit.status != VisitStatus.IN_PROGRESS:
        raise BadRequestError(f"A visit with status '{visit.status.value}' cannot be checked out.")

    visit.checkout_at = now()
    db.commit()
    db.refresh(visit)
    return visit


def save_notes(db: Session, visit: Visit, notes: str) -> Visit:
    if not visit.is_editable:
        raise BadRequestError("A completed visit can no longer be edited.")
    visit.notes = notes
    db.commit()
    db.refresh(visit)
    return visit


def record_vitals(db: Session, visit: Visit, payload: VitalCreate) -> dict[str, Any]:
    """Store a reading, run the threshold engine and raise an alert when needed.

    Threshold evaluation is synchronous: the nurse sees the outcome in the
    response to their own submission.
    """
    if visit.status == VisitStatus.COMPLETED:
        raise BadRequestError("A completed visit can no longer be edited.")
    if visit.status != VisitStatus.IN_PROGRESS or visit.checkin_at is None:
        raise BadRequestError("Visit must be checked in before vitals can be recorded.")

    patient = db.get(Patient, visit.patient_id)
    if patient is None:  # pragma: no cover - defensive
        raise NotFoundError("Patient not found.")

    vital = Vital(
        patient_id=patient.id,
        visit_id=visit.id,
        systolic_bp=payload.systolic_bp,
        diastolic_bp=payload.diastolic_bp,
        heart_rate=payload.heart_rate,
        blood_glucose=payload.blood_glucose,
        spo2=payload.spo2,
        temperature=payload.temperature,
        weight=payload.weight,
        recorded_at=now(),
    )
    db.add(vital)
    db.flush()

    thresholds = vitals_service.load_thresholds(db, patient.id)
    if not thresholds:
        thresholds = vitals_service.create_default_thresholds(db, patient)
        db.flush()

    breaches = vitals_service.evaluate_thresholds(vital, thresholds)
    vital.threshold_breached = bool(breaches)

    alerts: list[Alert] = []
    if breaches:
        alerts.append(alert_service.create_threshold_alert(db, patient=patient, vital=vital, breaches=breaches))

    db.commit()
    db.refresh(vital)
    for alert in alerts:
        db.refresh(alert)

    return {
        "vitals": vitals_service.serialize(vital),
        "threshold_breached": vital.threshold_breached,
        "breached_parameters": breaches,
        "alerts_created": [alert_service.serialize(alert) for alert in alerts],
    }


def complete_visit(db: Session, visit: Visit) -> Visit:
    """in_progress -> completed. Requires a check-in and at least one recorded reading."""
    if visit.status == VisitStatus.COMPLETED:
        raise BadRequestError("This visit has already been completed.")
    if visit.status != VisitStatus.IN_PROGRESS or visit.checkin_at is None:
        raise BadRequestError("Visit must be checked in before it can be completed.")

    has_vitals = db.scalar(select(Vital.id).where(Vital.visit_id == visit.id).limit(1))
    if has_vitals is None:
        raise BadRequestError("Vitals must be recorded before a visit can be completed.")

    if visit.checkout_at is None:
        visit.checkout_at = now()
    visit.status = VisitStatus.COMPLETED
    db.commit()
    db.refresh(visit)
    return visit


def ensure_nurse_can_edit(visit: Visit) -> None:
    if not visit.is_editable:
        raise ForbiddenError("Completed visits are read-only.")


def serialize(visit: Visit, *, include_patient: bool = True, include_nurse: bool = True) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": visit.id,
        "patient_id": visit.patient_id,
        "nurse_id": visit.nurse_id,
        "scheduled_at": visit.scheduled_at,
        "status": visit.status.value,
        "checkin_at": visit.checkin_at,
        "checkout_at": visit.checkout_at,
        "location_source": visit.location_source,
        "notes": visit.notes,
    }
    if include_patient and visit.patient is not None:
        data["patient"] = {
            "id": visit.patient.id,
            "name": visit.patient.name,
            "age": visit.patient.age,
            "address": visit.patient.address,
        }
    if include_nurse and visit.nurse is not None and visit.nurse.user is not None:
        data["nurse"] = {
            "id": visit.nurse.id,
            "name": visit.nurse.user.name,
            "credential": visit.nurse.credential,
            "phone": visit.nurse.user.phone,
        }
    return data
