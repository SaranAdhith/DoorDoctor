"""Operational metrics and directory listings for coordinators."""

from datetime import datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..database import now
from ..models import Alert, AlertStatus, Caregiver, CaregiverStatus, Patient, Visit, VisitStatus


def summary(db: Session) -> dict[str, int]:
    start = datetime.combine(now().date(), time.min)
    end = start + timedelta(days=1)

    patients = db.scalar(select(func.count(Patient.id))) or 0
    caregivers = (
        db.scalar(select(func.count(Caregiver.id)).where(Caregiver.status == CaregiverStatus.ACTIVE)) or 0
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
        "caregivers": int(caregivers),
        "today_visits": int(today_visits),
        "completed_today": int(completed_today),
        "active_alerts": int(active_alerts),
    }


def list_caregivers(db: Session) -> list[dict[str, Any]]:
    caregivers = db.scalars(
        select(Caregiver).options(selectinload(Caregiver.user)).order_by(Caregiver.id)
    ).all()

    payload: list[dict[str, Any]] = []
    for caregiver in caregivers:
        assigned = (
            db.scalar(
                select(func.count(Visit.id)).where(
                    Visit.caregiver_id == caregiver.id,
                    Visit.status.in_([VisitStatus.SCHEDULED, VisitStatus.IN_PROGRESS]),
                )
            )
            or 0
        )
        payload.append(
            {
                "id": caregiver.id,
                "user_id": caregiver.user_id,
                "name": caregiver.user.name if caregiver.user else "",
                "email": caregiver.user.email if caregiver.user else "",
                "phone": caregiver.user.phone if caregiver.user else None,
                "credential": caregiver.credential,
                "verification_status": caregiver.verification_status.value,
                "status": caregiver.status.value,
                "open_visits": int(assigned),
            }
        )
    return payload
