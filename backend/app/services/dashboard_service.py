"""Single aggregation used by the family dashboard (one request, no N+1 fan-out)."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import now
from ..models import Alert, AlertSeverity, AlertStatus, Nurse, Patient, Visit, VisitStatus
from . import alert_service, medication_service, vitals_service


def _overall_status(active_alerts: list[Alert]) -> str:
    if any(alert.severity == AlertSeverity.CRITICAL for alert in active_alerts):
        return "Critical Alert"
    if active_alerts:
        return "Attention Required"
    return "Stable"


def _serialize_nurse(nurse: Nurse | None) -> dict[str, Any] | None:
    if nurse is None or nurse.user is None:
        return None
    return {
        "id": nurse.id,
        "user_id": nurse.user_id,
        "name": nurse.user.name,
        "email": nurse.user.email,
        "phone": nurse.user.phone,
        "credential": nurse.credential,
        "verification_status": nurse.verification_status.value,
        "status": nurse.status.value,
    }


def build_dashboard(db: Session, patient: Patient) -> dict[str, Any]:
    generated_at = now()

    visits = list(
        db.scalars(
            select(Visit)
            .options(selectinload(Visit.nurse).selectinload(Nurse.user))
            .where(Visit.patient_id == patient.id)
            .order_by(Visit.scheduled_at.desc())
            .limit(40)
        )
    )
    upcoming = [
        v for v in visits
        if v.status in (VisitStatus.SCHEDULED, VisitStatus.IN_PROGRESS)
    ]
    upcoming.sort(key=lambda v: v.scheduled_at)
    recent = [v for v in visits if v.status == VisitStatus.COMPLETED][:6]

    active_alerts = list(
        db.scalars(
            select(Alert)
            .where(Alert.patient_id == patient.id, Alert.status != AlertStatus.RESOLVED)
            .order_by(Alert.created_at.desc())
            .limit(10)
        )
    )

    history = vitals_service.history_for_patient(db, patient.id, limit=30)
    current = history[-1] if history else None

    thresholds = vitals_service.load_thresholds(db, patient.id)

    # Preferred nurse: the one on the next open visit, else the most recent visit.
    nurse = None
    for visit in upcoming + visits:
        if visit.nurse is not None:
            nurse = visit.nurse
            break

    return {
        "patient": patient,
        "current_vitals": vitals_service.serialize(current) if current else None,
        "vitals_history": [vitals_service.serialize(v) for v in history],
        "medication_adherence": medication_service.adherence_for_patient(db, patient.id),
        "medications": [
            medication_service.serialize(m)
            for m in medication_service.list_medications(db, patient.id, active_only=True)
        ],
        "upcoming_visits": [_visit_payload(v) for v in upcoming[:5]],
        "recent_visits": [_visit_payload(v) for v in recent],
        "active_alerts": [alert_service.serialize(a) for a in active_alerts],
        "nurse": _serialize_nurse(nurse),
        "overall_status": _overall_status(active_alerts),
        "thresholds": thresholds,
        "generated_at": generated_at,
    }


def _visit_payload(visit: Visit) -> dict[str, Any]:
    nurse = visit.nurse
    return {
        "id": visit.id,
        "patient_id": visit.patient_id,
        "nurse_id": visit.nurse_id,
        "nurse_name": nurse.user.name if nurse and nurse.user else None,
        "scheduled_at": visit.scheduled_at,
        "status": visit.status.value,
        "checkin_at": visit.checkin_at,
        "checkout_at": visit.checkout_at,
        "notes": visit.notes,
    }
