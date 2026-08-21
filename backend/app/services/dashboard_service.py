"""Single aggregation used by the family dashboard (one request, no N+1 fan-out)."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import now
from ..models import Alert, AlertSeverity, AlertStatus, Caregiver, Patient, Visit, VisitStatus
from . import alert_service, medication_service, vitals_service


def _overall_status(active_alerts: list[Alert]) -> str:
    if any(alert.severity == AlertSeverity.CRITICAL for alert in active_alerts):
        return "Critical Alert"
    if active_alerts:
        return "Attention Required"
    return "Stable"


def _serialize_caregiver(caregiver: Caregiver | None) -> dict[str, Any] | None:
    if caregiver is None or caregiver.user is None:
        return None
    return {
        "id": caregiver.id,
        "user_id": caregiver.user_id,
        "name": caregiver.user.name,
        "email": caregiver.user.email,
        "phone": caregiver.user.phone,
        "credential": caregiver.credential,
        "verification_status": caregiver.verification_status.value,
        "status": caregiver.status.value,
    }


def build_dashboard(db: Session, patient: Patient) -> dict[str, Any]:
    generated_at = now()

    visits = list(
        db.scalars(
            select(Visit)
            .options(selectinload(Visit.caregiver).selectinload(Caregiver.user))
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

    # Preferred caregiver: the one on the next open visit, else the most recent visit.
    caregiver = None
    for visit in upcoming + visits:
        if visit.caregiver is not None:
            caregiver = visit.caregiver
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
        "caregiver": _serialize_caregiver(caregiver),
        "overall_status": _overall_status(active_alerts),
        "thresholds": thresholds,
        "generated_at": generated_at,
    }


def _visit_payload(visit: Visit) -> dict[str, Any]:
    caregiver = visit.caregiver
    return {
        "id": visit.id,
        "patient_id": visit.patient_id,
        "caregiver_id": visit.caregiver_id,
        "caregiver_name": caregiver.user.name if caregiver and caregiver.user else None,
        "scheduled_at": visit.scheduled_at,
        "status": visit.status.value,
        "checkin_at": visit.checkin_at,
        "checkout_at": visit.checkout_at,
        "notes": visit.notes,
    }
