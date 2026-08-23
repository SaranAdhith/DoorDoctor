"""`--demo-reset`: rewind the live demo path without rebuilding the business.

A full re-seed takes seconds, but it renumbers every invoice and moves every
payment date. Between two demos you rarely want any of that — you want the
148/92 path back, because the last evaluator recorded the reading, raised the
alert and resolved it.

So this rewinds **exactly what a demo run changes**: Lakshmi's visit today goes
back to `scheduled`, the readings and dose logs captured against it are deleted,
and the alerts her visit raised today go with their notifications. Nothing else
is touched — not the other fourteen visits on today's board, which nobody
interacted with, and not a single user, subscription, invoice or historical
record.

Alerts are deleted before the readings they point at: `Alert.vitals_id` is a
foreign key, and SQLite does not enforce foreign keys unless it is asked to, so
a dangling row would survive silently rather than raise.

Out of scope, deliberately: a plan change or cancellation made during the demo.
Rewinding those means unpicking proration credits and invoice history, which is
what a full re-seed is for.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..database import now
from ..models import (
    Alert,
    LocationStatus,
    MedicationLog,
    Notification,
    Nurse,
    Patient,
    User,
    Visit,
    VisitStatus,
    Vital,
)
from .core import DEMO_VISIT_HOUR, DEMO_VISIT_MINUTE, at

DEMO_FAMILY_EMAIL = "family@doordoctor.in"
DEMO_NURSE_EMAIL = "nurse@doordoctor.in"


def _today_bounds() -> tuple[datetime, datetime]:
    start = datetime.combine(now().date(), time.min)
    return start, start + timedelta(days=1)


def demo_reset(db: Session) -> dict[str, int]:
    """Put the live demo path back to its seeded state. Returns what changed."""
    start, end = _today_bounds()

    family = db.scalar(select(User).where(User.email == DEMO_FAMILY_EMAIL))
    nurse_user = db.scalar(select(User).where(User.email == DEMO_NURSE_EMAIL))
    if family is None or nurse_user is None:
        raise RuntimeError("This database has not been seeded. Run `python -m app.seed` first.")

    nurse = db.scalar(select(Nurse).where(Nurse.user_id == nurse_user.id))
    patient = db.scalar(
        select(Patient).where(Patient.family_user_id == family.id).order_by(Patient.id)
    )

    # Every alert raised for the demo patient today, whatever state it ended in.
    alert_ids = list(
        db.scalars(
            select(Alert.id).where(
                Alert.patient_id == patient.id, Alert.created_at >= start, Alert.created_at < end
            )
        )
    )
    if alert_ids:
        db.execute(delete(Notification).where(Notification.alert_id.in_(alert_ids)))
        db.execute(delete(Alert).where(Alert.id.in_(alert_ids)))
        db.flush()

    visits = list(
        db.scalars(
            select(Visit).where(
                Visit.patient_id == patient.id,
                Visit.scheduled_at >= start,
                Visit.scheduled_at < end,
            )
        )
    )
    visit_ids = [visit.id for visit in visits]
    readings = 0
    if visit_ids:
        readings = len(list(db.scalars(select(Vital.id).where(Vital.visit_id.in_(visit_ids)))))
        db.execute(delete(Vital).where(Vital.visit_id.in_(visit_ids)))
        db.execute(delete(MedicationLog).where(MedicationLog.visit_id.in_(visit_ids)))
        db.flush()

    # One scheduled visit at 10:30 with Anitha, and only one — the fixture that
    # drives the alert tests takes the first open visit on her board.
    for extra in visits[1:]:
        db.delete(extra)
    if visits:
        demo_visit = visits[0]
        demo_visit.nurse_id = nurse.id
        demo_visit.scheduled_at = at(0, hour=DEMO_VISIT_HOUR, minute=DEMO_VISIT_MINUTE)
        demo_visit.status = VisitStatus.SCHEDULED
        demo_visit.checkin_at = None
        demo_visit.checkout_at = None
        demo_visit.checkin_lat = None
        demo_visit.checkin_lng = None
        # The location verdict is rewound with the check-in that produced it. A
        # visit that says "verified 11 m from home" but has no check-in time is
        # a record of something that did not happen.
        demo_visit.location_source = "none"
        demo_visit.location_status = LocationStatus.UNAVAILABLE
        demo_visit.location_distance_m = None
        demo_visit.location_accuracy_m = None
        demo_visit.location_detail = None
        demo_visit.notes = None
    else:
        demo_visit = Visit(
            patient_id=patient.id,
            nurse_id=nurse.id,
            scheduled_at=at(0, hour=DEMO_VISIT_HOUR, minute=DEMO_VISIT_MINUTE),
            status=VisitStatus.SCHEDULED,
        )
        db.add(demo_visit)

    db.commit()
    return {
        "alerts_removed": len(alert_ids),
        "readings_removed": readings,
        "visits_removed": max(0, len(visits) - 1),
        "demo_visit_id": demo_visit.id,
    }
