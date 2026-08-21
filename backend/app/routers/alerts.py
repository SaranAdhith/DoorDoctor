"""Alert endpoints. Alerts are monitoring events, never medical diagnoses."""

from typing import Any

from fastapi import APIRouter, Query

from ..core.dependencies import AdminUser, CurrentUser, DbSession
from ..models import Nurse, Visit
from ..schemas.alert import AlertDetailOut, AlertOut
from ..services import alert_service, vitals_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut], summary="Alerts visible to the current user")
def list_alerts(
    current_user: CurrentUser,
    db: DbSession,
    alert_status: str | None = Query(default=None, alias="status"),
) -> list[dict[str, Any]]:
    alerts = alert_service.list_alerts_for_user(db, current_user, alert_status)
    return [alert_service.serialize(a) for a in alerts]


@router.get("/{alert_id}", response_model=AlertDetailOut, summary="Alert detail")
def get_alert(alert_id: int, current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    alert = alert_service.get_alert_for_user(db, current_user, alert_id)
    payload = alert_service.serialize(alert)
    payload["patient_name"] = alert.patient.name if alert.patient else None

    nurse_name = None
    if alert.vitals is not None and alert.vitals.visit_id is not None:
        visit = db.get(Visit, alert.vitals.visit_id)
        if visit is not None and visit.nurse_id is not None:
            nurse = db.get(Nurse, visit.nurse_id)
            if nurse is not None and nurse.user is not None:
                nurse_name = nurse.user.name

    payload["nurse_name"] = nurse_name
    payload["vitals"] = vitals_service.serialize(alert.vitals) if alert.vitals else None
    payload["thresholds"] = [
        {
            "metric": t.metric.value,
            "low_threshold": t.low_threshold,
            "high_threshold": t.high_threshold,
            "enabled": t.enabled,
        }
        for t in vitals_service.load_thresholds(db, alert.patient_id)
    ]
    return payload


@router.post("/{alert_id}/acknowledge", response_model=AlertOut, summary="Acknowledge an alert (admin)")
def acknowledge_alert(alert_id: int, db: DbSession, current_user: AdminUser) -> dict[str, Any]:
    alert = alert_service.get_alert_for_user(db, current_user, alert_id)
    return alert_service.serialize(alert_service.acknowledge(db, alert, current_user))


@router.post("/{alert_id}/resolve", response_model=AlertOut, summary="Resolve an alert (admin)")
def resolve_alert(alert_id: int, db: DbSession, current_user: AdminUser) -> dict[str, Any]:
    alert = alert_service.get_alert_for_user(db, current_user, alert_id)
    return alert_service.serialize(alert_service.resolve(db, alert, current_user))
