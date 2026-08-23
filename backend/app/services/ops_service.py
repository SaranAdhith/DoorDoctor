"""Admin operations: the board, the queue, the outcomes and the zones (§4.17).

**Nothing in this module is a stored counter.** Every number is computed from
the rows it describes, on read. A metric that can drift from its own data is
worse than no metric, because it is believed for exactly as long as it takes
somebody to check it.

The zone view is the one place a business number appears, and it is careful:
the 30-45 subscriber break-even band is RECORDED, the cost model behind it was
never supplied, so this reports **where a zone sits against the band** and
estimates no margin.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from ..core.ops import (
    BREAK_EVEN_MAX_SUBSCRIBERS,
    BREAK_EVEN_MIN_SUBSCRIBERS,
    BREAK_EVEN_NOTE,
    OUTCOME_WINDOW_DAYS,
    VISIT_BOARD_MAX_PAGE_SIZE,
    VISIT_BOARD_PAGE_SIZE,
)
from ..database import now
from ..models import (
    Alert,
    AlertStatus,
    EscalationEvent,
    EscalationStatus,
    LocationStatus,
    Medication,
    MedicationLog,
    MedicationLogStatus,
    Nurse,
    NurseStatus,
    Patient,
    PatientStatus,
    Visit,
    VisitStatus,
)
from . import alert_service, visit_service


# --- the visit board ------------------------------------------------------


def visit_board(
    db: Session,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    status: VisitStatus | None = None,
    nurse_id: int | None = None,
    zone: str | None = None,
    unassigned: bool | None = None,
    page: int = 1,
    page_size: int = VISIT_BOARD_PAGE_SIZE,
) -> dict[str, Any]:
    """A window of the schedule, paginated, oldest first inside the window.

    This replaces `/visits`' newest-250 list, which STATE.md recorded as owed to
    this phase by name: a forward schedule meant the admin table led with next
    week rather than today. A board is a window with a page, not a cap on a
    firehose — and inside a window, ascending is the order the day is worked.
    """
    page = max(1, page)
    page_size = max(1, min(page_size, VISIT_BOARD_MAX_PAGE_SIZE))

    if date_from is None:
        date_from = datetime.combine(now().date(), time.min)
    if date_to is None:
        date_to = date_from + timedelta(days=1)

    filters = [Visit.scheduled_at >= date_from, Visit.scheduled_at < date_to]
    if status is not None:
        filters.append(Visit.status == status)
    if nurse_id is not None:
        filters.append(Visit.nurse_id == nurse_id)
    if unassigned is True:
        filters.append(Visit.nurse_id.is_(None))
    elif unassigned is False:
        filters.append(Visit.nurse_id.is_not(None))

    query = select(Visit).options(selectinload(Visit.patient), selectinload(Visit.nurse))
    count_query = select(func.count(Visit.id))
    if zone:
        query = query.join(Patient, Visit.patient_id == Patient.id)
        count_query = count_query.join(Patient, Visit.patient_id == Patient.id)
        filters.append(Patient.zone == zone)

    query = query.where(*filters).order_by(Visit.scheduled_at).offset((page - 1) * page_size).limit(page_size)
    total = int(db.scalar(count_query.where(*filters)) or 0)

    rows = list(db.scalars(query))
    return {
        "from": date_from,
        "to": date_to,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": max(1, (total + page_size - 1) // page_size),
        "visits": [visit_service.serialize(visit) for visit in rows],
        "summary": _board_summary(db, filters, zone),
    }


def _board_summary(db: Session, filters: list, zone: str | None) -> dict[str, int]:
    """Counts for the whole window, not the page.

    A board that summarised its current page would report a different business
    every time somebody clicked "next".
    """
    query = select(Visit.status, func.count(Visit.id))
    if zone:
        query = query.join(Patient, Visit.patient_id == Patient.id)
    rows = db.execute(query.where(*filters).group_by(Visit.status)).all()
    counts = {status.value: int(count) for status, count in rows}

    unassigned_query = select(func.count(Visit.id))
    if zone:
        unassigned_query = unassigned_query.join(Patient, Visit.patient_id == Patient.id)
    counts["unassigned"] = int(
        db.scalar(unassigned_query.where(*filters, Visit.nurse_id.is_(None))) or 0
    )
    return counts


# --- the alert queue ------------------------------------------------------


def alert_queue(db: Session, *, include_resolved: bool = False, limit: int = 100) -> list[dict[str, Any]]:
    """The queue in the order an operator works it: breached first, then soonest due.

    The SLA clock is stamped on read for anything that has passed its deadline,
    which is what makes a breach survive somebody editing the constants later.
    """
    statuses = [AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]
    if include_resolved:
        statuses.append(AlertStatus.RESOLVED)

    alerts = list(
        db.scalars(
            select(Alert)
            .options(selectinload(Alert.patient))
            .where(Alert.status.in_(statuses))
            .order_by(Alert.sla_due_at.is_(None), Alert.sla_due_at, Alert.created_at)
            .limit(limit)
        )
    )
    for alert in alerts:
        alert_service.refresh_sla(alert)
    db.commit()

    moment = now()
    payload = []
    for alert in alerts:
        data = alert_service.serialize(alert)
        data["patient_name"] = alert.patient.name if alert.patient else ""
        data["zone"] = alert.patient.zone if alert.patient else None
        data["breached"] = alert.sla_breached_at is not None
        data["minutes_remaining"] = (
            int((alert.sla_due_at - moment).total_seconds() // 60)
            if alert.sla_due_at and alert.sla_breached_at is None
            else None
        )
        payload.append(data)

    payload.sort(key=lambda row: (not row["breached"], row["minutes_remaining"] is None, row["minutes_remaining"] or 0))
    return payload


# --- outcomes -------------------------------------------------------------


def outcomes(db: Session, *, days: int = OUTCOME_WINDOW_DAYS) -> dict[str, Any]:
    """What actually happened over a window, computed from rows every time."""
    since = now() - timedelta(days=days)

    visit_rows = db.execute(
        select(Visit.status, func.count(Visit.id))
        .where(Visit.scheduled_at >= since, Visit.scheduled_at < now())
        .group_by(Visit.status)
    ).all()
    visit_counts = {status.value: int(count) for status, count in visit_rows}
    scheduled_total = sum(visit_counts.values())
    completed = visit_counts.get(VisitStatus.COMPLETED.value, 0)

    alerts = list(db.scalars(select(Alert).where(Alert.created_at >= since)))
    resolved = [alert for alert in alerts if alert.resolved_at is not None]
    resolution_minutes = sorted(
        (alert.resolved_at - alert.created_at).total_seconds() / 60 for alert in resolved
    )

    # SLA attainment counts only alerts that have had their chance: an alert
    # raised five minutes ago is neither met nor missed, and counting it as met
    # would flatter every number on this screen.
    judged = [alert for alert in alerts if alert.sla_due_at is not None and alert.sla_due_at < now()]
    met = [alert for alert in judged if alert.sla_breached_at is None]

    dose_rows = db.execute(
        select(MedicationLog.status, func.count(MedicationLog.id))
        .where(MedicationLog.recorded_at >= since)
        .group_by(MedicationLog.status)
    ).all()
    dose_counts = {status.value: int(count) for status, count in dose_rows}
    doses_total = sum(dose_counts.values())

    located = db.execute(
        select(Visit.location_status, func.count(Visit.id))
        .where(Visit.checkin_at.is_not(None), Visit.checkin_at >= since)
        .group_by(Visit.location_status)
    ).all()
    location_counts = {status.value: int(count) for status, count in located}
    located_total = sum(location_counts.values())

    escalations = int(
        db.scalar(select(func.count(EscalationEvent.id)).where(EscalationEvent.opened_at >= since))
        or 0
    )
    escalations_open = int(
        db.scalar(
            select(func.count(EscalationEvent.id)).where(
                EscalationEvent.opened_at >= since, EscalationEvent.status == EscalationStatus.OPEN
            )
        )
        or 0
    )

    return {
        "window_days": days,
        "since": since,
        "visits": {
            "scheduled": scheduled_total,
            "completed": completed,
            "missed": visit_counts.get(VisitStatus.MISSED.value, 0),
            "cancelled": visit_counts.get(VisitStatus.CANCELLED.value, 0),
            "completion_rate": _percentage(completed, scheduled_total),
        },
        "alerts": {
            "raised": len(alerts),
            "resolved": len(resolved),
            "median_minutes_to_resolve": _median(resolution_minutes),
            "sla_judged": len(judged),
            "sla_met": len(met),
            "sla_attainment": _percentage(len(met), len(judged)),
        },
        "medication": {
            "logged": doses_total,
            "administered": dose_counts.get(MedicationLogStatus.ADMINISTERED.value, 0),
            "adherence": _percentage(
                dose_counts.get(MedicationLogStatus.ADMINISTERED.value, 0), doses_total
            ),
        },
        "location": {
            "checked_in": located_total,
            "verified": location_counts.get(LocationStatus.VERIFIED.value, 0),
            "out_of_range": location_counts.get(LocationStatus.OUT_OF_RANGE.value, 0),
            "unavailable": location_counts.get(LocationStatus.UNAVAILABLE.value, 0),
            "verified_rate": _percentage(
                location_counts.get(LocationStatus.VERIFIED.value, 0), located_total
            ),
        },
        "escalations": {"opened": escalations, "still_open": escalations_open},
    }


def _percentage(part: int, whole: int) -> int | None:
    """None rather than 0 when there is nothing to divide.

    The same rule `medication_service.adherence_for_patient` follows: 0% reads
    as a failure, and "no data" is not one.
    """
    return round(part / whole * 100) if whole else None


def _median(values: list[float]) -> int | None:
    if not values:
        return None
    middle = len(values) // 2
    if len(values) % 2:
        return int(values[middle])
    return int((values[middle - 1] + values[middle]) / 2)


# --- zones ----------------------------------------------------------------


def zones(db: Session) -> dict[str, Any]:
    """Every zone against the recorded break-even band, and no invented margin."""
    since = now() - timedelta(days=OUTCOME_WINDOW_DAYS)

    patient_rows = db.execute(
        select(
            Patient.zone,
            func.count(Patient.id),
            func.sum(case((Patient.status == PatientStatus.ACTIVE, 1), else_=0)),
        ).group_by(Patient.zone)
    ).all()
    nurse_rows = db.execute(
        select(Nurse.zone, func.count(Nurse.id))
        .where(Nurse.status == NurseStatus.ACTIVE)
        .group_by(Nurse.zone)
    ).all()
    visit_rows = db.execute(
        select(Patient.zone, func.count(Visit.id))
        .join(Visit, Visit.patient_id == Patient.id)
        .where(Visit.scheduled_at >= since)
        .group_by(Patient.zone)
    ).all()
    alert_rows = db.execute(
        select(Patient.zone, func.count(Alert.id))
        .join(Alert, Alert.patient_id == Patient.id)
        .where(Alert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]))
        .group_by(Patient.zone)
    ).all()

    nurses_by_zone = {zone: int(count) for zone, count in nurse_rows}
    visits_by_zone = {zone: int(count) for zone, count in visit_rows}
    alerts_by_zone = {zone: int(count) for zone, count in alert_rows}

    rows: list[dict[str, Any]] = []
    for zone, total, active in sorted(patient_rows, key=lambda row: (row[0] or "")):
        if zone is None:
            continue
        active_count = int(active or 0)
        rows.append(
            {
                "zone": zone,
                "patients": int(total),
                "active_patients": active_count,
                "nurses": nurses_by_zone.get(zone, 0),
                "visits_in_window": visits_by_zone.get(zone, 0),
                "open_alerts": alerts_by_zone.get(zone, 0),
                "patients_per_nurse": (
                    round(active_count / nurses_by_zone[zone], 1)
                    if nurses_by_zone.get(zone)
                    else None
                ),
                "break_even": _break_even_position(active_count),
                "to_break_even": max(0, BREAK_EVEN_MIN_SUBSCRIBERS - active_count),
            }
        )

    return {
        "window_days": OUTCOME_WINDOW_DAYS,
        "break_even_min": BREAK_EVEN_MIN_SUBSCRIBERS,
        "break_even_max": BREAK_EVEN_MAX_SUBSCRIBERS,
        "note": BREAK_EVEN_NOTE,
        "zones": rows,
    }


def _break_even_position(active: int) -> str:
    """Where a zone sits against the band. Three words, and no forecast.

    RECORDED: a zone is expected to cover its cost somewhere between 30 and 45
    subscribers. The cost model behind that was never supplied, so this says
    which side of the band a zone is on and stops there.
    """
    if active < BREAK_EVEN_MIN_SUBSCRIBERS:
        return "below"
    if active <= BREAK_EVEN_MAX_SUBSCRIBERS:
        return "within"
    return "above"
