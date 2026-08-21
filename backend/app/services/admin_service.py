"""Operational metrics and directory listings for admins."""

from datetime import datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..database import now
from ..models import Alert, AlertStatus, Nurse, NurseStatus, Patient, Visit, VisitStatus


def summary(db: Session) -> dict[str, int]:
    start = datetime.combine(now().date(), time.min)
    end = start + timedelta(days=1)

    patients = db.scalar(select(func.count(Patient.id))) or 0
    nurses = (
        db.scalar(select(func.count(Nurse.id)).where(Nurse.status == NurseStatus.ACTIVE)) or 0
    )
    today_visits = (
        db.scalar(
            select(func.count(Visit.id)).where(Visit.scheduled_at >= start, Visit.scheduled_at < end)
        )
        or 0
    )
    completed_today = (
        db.scalar(
            select(func.count(Visit.id)).where(
                Visit.scheduled_at >= start,
                Visit.scheduled_at < end,
                Visit.status == VisitStatus.COMPLETED,
            )
        )
        or 0
    )
    active_alerts = (
        db.scalar(select(func.count(Alert.id)).where(Alert.status == AlertStatus.ACTIVE)) or 0
    )

    return {
        "patients": int(patients),
        "nurses": int(nurses),
        "today_visits": int(today_visits),
        "completed_today": int(completed_today),
        "active_alerts": int(active_alerts),
    }


def list_nurses(db: Session) -> list[dict[str, Any]]:
    nurses = db.scalars(
        select(Nurse).options(selectinload(Nurse.user)).order_by(Nurse.id)
    ).all()

    payload: list[dict[str, Any]] = []
    for nurse in nurses:
        assigned = (
            db.scalar(
                select(func.count(Visit.id)).where(
                    Visit.nurse_id == nurse.id,
                    Visit.status.in_([VisitStatus.SCHEDULED, VisitStatus.IN_PROGRESS]),
                )
            )
            or 0
        )
        payload.append(
            {
                "id": nurse.id,
                "user_id": nurse.user_id,
                "name": nurse.user.name if nurse.user else "",
                "email": nurse.user.email if nurse.user else "",
                "phone": nurse.user.phone if nurse.user else None,
                "credential": nurse.credential,
                "verification_status": nurse.verification_status.value,
                "status": nurse.status.value,
                "open_visits": int(assigned),
            }
        )
    return payload
