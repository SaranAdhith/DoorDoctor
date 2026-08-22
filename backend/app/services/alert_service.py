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


def create_alert(
    db: Session,
    *,
    patient: Patient,
    alert_type: str,
    severity: AlertSeverity,
    title: str,
    message: str,
    breaches: list[dict[str, Any]] | None = None,
    vital: Vital | None = None,
    notify: bool = True,
) -> Alert:
    """Create an alert from any source. **The only place an `Alert` row is built.**

    Phase 9 adds three sources with no `Vital` to point at — an abnormal lab, a
    safety-score drop and a wearable breach — so `vital` is optional here and
    `create_threshold_alert` is a thin wrapper that supplies one.

    Keeping a single constructor is not tidiness: the Phase 5 seed's alert count
    is exact *because* nothing writes an `Alert` directly, and
    `notify_alert_recipients` is the only reason a family ever hears about one.
    A second constructor would be a silent alert.
    """
    alert = Alert(
        patient_id=patient.id,
        vitals_id=vital.id if vital is not None else None,
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        status=AlertStatus.ACTIVE,
    )
    alert.breached_parameters = breaches or []
    db.add(alert)
    db.flush()  # assign alert.id before notifications reference it

    if notify:
        notification_service.notify_alert_recipients(db, alert, patient)
    return alert


def create_threshold_alert(
    db: Session,
    *,
    patient: Patient,
    vital: Vital,
    breaches: list[dict[str, Any]],
) -> Alert:
    """Create a single alert covering every parameter breached by one reading."""
    severity = severity_for_breaches(len(breaches))
    return create_alert(
        db,
        patient=patient,
        alert_type="vital_threshold_breach",
        severity=severity,
        title=(
            "Elevated vital reading"
            if severity == AlertSeverity.WARNING
            else "Multiple vitals outside range"
        ),
        message=build_alert_message(breaches),
        breaches=breaches,
        vital=vital,
    )


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


def resolve(db: Session, alert: Alert, user: User, note: str | None = None) -> Alert:
    """Close an alert, optionally recording what was done about it.

    The note is optional so every existing caller behaves identically, but it is
    what §8's journey 3 has always described: the admin "resolves it with a
    note". A blank string is stored as nothing rather than as an empty note.
    """
    if alert.status == AlertStatus.RESOLVED:
        raise BadRequestError("This alert has already been resolved.")

    if alert.acknowledged_by is None:
        alert.acknowledged_by = user.id
        alert.acknowledged_at = now()
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = now()
    if note is not None:
        alert.resolution_note = note.strip() or None
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
        "resolution_note": alert.resolution_note,
        "created_at": alert.created_at,
    }
