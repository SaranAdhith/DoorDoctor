"""Visit scheduling, lifecycle transitions and vitals capture during a visit."""

from datetime import datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from ..database import now
from ..models import (
    Alert,
    Caregiver,
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


def list_visits_for_user(db: Session, user: User, status: str | None = None) -> list[Visit]:
    query = select(Visit).options(selectinload(Visit.patient), selectinload(Visit.caregiver))

    if user.role == UserRole.FAMILY:
        query = query.join(Patient, Visit.patient_id == Patient.id).where(
            Patient.family_user_id == user.id
        )
    elif user.role == UserRole.CAREGIVER:
        caregiver = db.scalar(select(Caregiver).where(Caregiver.user_id == user.id))
        if caregiver is None:
            return []
        query = query.where(Visit.caregiver_id == caregiver.id)

    if status:
        query = query.where(Visit.status == status)

    return list(db.scalars(query.order_by(Visit.scheduled_at.desc()).limit(100)))


def list_today_visits(db: Session, user: User) -> list[Visit]:
    """Visits scheduled for today.

    A caregiver also keeps any still-open visit from an earlier day on their
    worklist, so unfinished work is never silently dropped. Coordinator screens
    stay strictly on today so the dashboard counts and the table agree.
    """
    start, end = _day_bounds(now())
    visits = list_visits_for_user(db, user)
    keep_open = user.role == UserRole.CAREGIVER

    today: list[Visit] = []
    for visit in visits:
        in_today = start <= visit.scheduled_at < end
        still_open = visit.status in (VisitStatus.SCHEDULED, VisitStatus.IN_PROGRESS)
        if in_today or (keep_open and still_open):
            today.append(visit)
    return sorted(today, key=lambda v: v.scheduled_at)


def create_visit(
    db: Session, *, patient_id: int, caregiver_id: int | None, scheduled_at: datetime
) -> Visit:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise NotFoundError("Patient not found.")

    if caregiver_id is not None:
        caregiver = db.get(Caregiver, caregiver_id)
        if caregiver is None:
            raise NotFoundError("Caregiver not found.")

    visit = Visit(
        patient_id=patient_id,
        caregiver_id=caregiver_id,
        scheduled_at=scheduled_at,
        status=VisitStatus.SCHEDULED,
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit


def assign_caregiver(db: Session, visit: Visit, caregiver_id: int) -> Visit:
    if visit.status in (VisitStatus.COMPLETED, VisitStatus.CANCELLED):
        raise BadRequestError("A completed or cancelled visit cannot be reassigned.")

    caregiver = db.get(Caregiver, caregiver_id)
    if caregiver is None:
        raise NotFoundError("Caregiver not found.")

    visit.caregiver_id = caregiver_id
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

    Threshold evaluation is synchronous: the caregiver sees the outcome in the
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


def ensure_caregiver_can_edit(visit: Visit) -> None:
    if not visit.is_editable:
        raise ForbiddenError("Completed visits are read-only.")


def serialize(visit: Visit, *, include_patient: bool = True, include_caregiver: bool = True) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": visit.id,
        "patient_id": visit.patient_id,
        "caregiver_id": visit.caregiver_id,
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
    if include_caregiver and visit.caregiver is not None and visit.caregiver.user is not None:
        data["caregiver"] = {
            "id": visit.caregiver.id,
            "name": visit.caregiver.user.name,
            "credential": visit.caregiver.credential,
            "phone": visit.caregiver.user.phone,
        }
    return data
