"""Alert creation, listing and lifecycle transitions."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..core.exceptions import BadRequestError, NotFoundError
from ..database import now
from ..models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    Nurse,
    Patient,
    User,
    UserRole,
    Visit,
    Vital,
)
from . import notification_service

METRIC_LABELS: dict[str, str] = {
    "systolic_bp": "Systolic blood pressure",
    "diastolic_bp": "Diastolic blood pressure",
    "heart_rate": "Heart rate",
    "blood_glucose": "Blood glucose",
    "spo2": "SpO2",
    "temperature": "Temperature",
    "weight": "Weight",
}


def severity_for_breaches(breach_count: int) -> AlertSeverity:
    """MVP demonstration rule - not a clinical severity model."""
    if breach_count >= 2:
        return AlertSeverity.CRITICAL
    return AlertSeverity.WARNING


def build_alert_message(breaches: list[dict[str, Any]]) -> str:
    """Neutral, non-diagnostic wording describing what was measured."""
    parts = []
    for breach in breaches:
        label = METRIC_LABELS.get(breach["metric"], breach["metric"])
        parts.append(f"{label} {_format_number(breach['value'])}{breach.get('unit', '')} "
                     f"({breach['direction']} configured threshold "
                     f"{_format_number(breach['threshold'])}{breach.get('unit', '')})")
    joined = "; ".join(parts)
    return (
        f"A recorded reading is outside the configured monitoring range: {joined}. "
        "This is a monitoring alert, not a medical diagnosis."
    )


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def create_threshold_alert(
    db: Session,
    *,
    patient: Patient,
    vital: Vital,
    breaches: list[dict[str, Any]],
) -> Alert:
    """Create a single alert covering every parameter breached by one reading."""
    severity = severity_for_breaches(len(breaches))
    alert = Alert(
        patient_id=patient.id,
        vitals_id=vital.id,
        alert_type="vital_threshold_breach",
        severity=severity,
        title="Elevated vital reading" if severity == AlertSeverity.WARNING else "Multiple vitals outside range",
        message=build_alert_message(breaches),
        status=AlertStatus.ACTIVE,
    )
    alert.breached_parameters = breaches
    db.add(alert)
    db.flush()  # assign alert.id before notifications reference it

    notification_service.notify_alert_recipients(db, alert, patient)
    return alert


def list_alerts_for_user(db: Session, user: User, status: str | None = None) -> list[Alert]:
    query = select(Alert).options(selectinload(Alert.patient), selectinload(Alert.vitals))

    if user.role == UserRole.FAMILY:
        query = query.join(Patient, Alert.patient_id == Patient.id).where(Patient.family_user_id == user.id)
    elif user.role == UserRole.NURSE:
        # Nurses only see alerts for patients they are assigned to.
        patient_ids = (
            select(Visit.patient_id)
            .join(Nurse, Visit.nurse_id == Nurse.id)
            .where(Nurse.user_id == user.id)
        )
        query = query.where(Alert.patient_id.in_(patient_ids))

    if status:
        query = query.where(Alert.status == status)

    return list(db.scalars(query.order_by(Alert.created_at.desc()).limit(100)))


def get_alert_for_user(db: Session, user: User, alert_id: int) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise NotFoundError("Alert not found.")

    if user.role == UserRole.ADMIN:
        return alert
    if user.role == UserRole.FAMILY and alert.patient.family_user_id == user.id:
        return alert
    raise NotFoundError("Alert not found.")


def acknowledge(db: Session, alert: Alert, user: User) -> Alert:
    if alert.status == AlertStatus.RESOLVED:
        raise BadRequestError("This alert has already been resolved.")
    if alert.status == AlertStatus.ACKNOWLEDGED:
        raise BadRequestError("This alert has already been acknowledged.")

    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_by = user.id
    alert.acknowledged_at = now()
    db.commit()
    db.refresh(alert)
    return alert


def resolve(db: Session, alert: Alert, user: User) -> Alert:
    if alert.status == AlertStatus.RESOLVED:
        raise BadRequestError("This alert has already been resolved.")

    if alert.acknowledged_by is None:
        alert.acknowledged_by = user.id
        alert.acknowledged_at = now()
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = now()
    db.commit()
    db.refresh(alert)
    return alert


def serialize(alert: Alert) -> dict[str, Any]:
    return {
        "id": alert.id,
        "patient_id": alert.patient_id,
        "vitals_id": alert.vitals_id,
        "alert_type": alert.alert_type,
        "severity": alert.severity.value,
        "title": alert.title,
        "message": alert.message,
        "breached_parameters": alert.breached_parameters,
        "status": alert.status.value,
        "acknowledged_by": alert.acknowledged_by,
        "acknowledged_at": alert.acknowledged_at,
        "resolved_at": alert.resolved_at,
        "created_at": alert.created_at,
    }
