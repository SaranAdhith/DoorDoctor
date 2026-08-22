"""The Senior Safety Score (§4.5).

**This module contains no numbers.** Every weight, band, window and floor lives
in `core/clinical.py`, which is the one file the founder edits when the real §4
arrives. What lives here is the arithmetic, and the one rule that makes the
score defensible:

> **A component with no data does not score zero.**

No PHQ-2 on file must not read as "worst possible mood"; no wearable must not
read as "unmonitored and unsafe". Missing components are *dropped*, and the
score is rescaled across the weights that did have data. `covered_weight` is
stored on every row so the rescaling is visible rather than flattering, and
below `SAFETY_MIN_COVERED_WEIGHT` no score is published at all — a number
derived from one component is worse than an honest "not enough data yet",
because it looks exactly as authoritative as a real one.

RECORDED: deterministic, 0–100, and a drop of 10 or more points inside 30 days
raises an alert. Everything else is `ASSUMED`.

Family-facing wording goes through `summary_service.plain_metric_label()` and is
checked against the same banned vocabulary Phase 6 defined — a new surface must
not be where "systolic" comes back.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..core import clinical
from ..database import now
from ..models import (
    Alert,
    AlertSeverity,
    Device,
    DeviceReading,
    DeviceStatus,
    Patient,
    SafetyBand,
    SafetyScore,
    Screening,
    ScreeningInstrument,
    Visit,
    VisitStatus,
)
from . import alert_service, medication_service, vitals_service

logger = logging.getLogger("doordoctor.safety")


@dataclass(frozen=True)
class Measured:
    """One component's finding.

    `value` is None when there was nothing to measure — which is *not* zero, and
    the distinction is the whole point of this module.
    """

    value: Optional[float]
    detail: str


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


# --------------------------------------------------------------------------
# The six components. Each returns a 0..1 value or None, plus one plain
# sentence a family member can read.
# --------------------------------------------------------------------------


def _vital_stability(db: Session, patient: Patient, since: datetime, until: datetime) -> Measured:
    readings = vitals_service.history_since(db, patient.id, since, until)
    if len(readings) < clinical.SAFETY_MIN_READINGS:
        return Measured(None, "Not enough checks recorded yet to say.")

    inside = sum(1 for r in readings if not r.threshold_breached)
    return Measured(
        _clamp(inside / len(readings)),
        f"{inside} of {len(readings)} checks were inside the range set for this patient.",
    )


def _medication_adherence(
    db: Session, patient: Patient, since: datetime, until: datetime
) -> Measured:
    taken = medication_service.adherence_for_patient(db, patient.id, since=since, until=until)
    if not taken["total"]:
        return Measured(None, "No doses have been recorded in this period.")
    # The raw counts, not the rounded percentage the dashboard shows: a score
    # built from a display value inherits the display's rounding.
    return Measured(
        _clamp(taken["administered"] / taken["total"]),
        f"{taken['administered']} of {taken['total']} scheduled doses were taken.",
    )


def _care_continuity(db: Session, patient: Patient, since: datetime, until: datetime) -> Measured:
    # Only visits whose time has already come. A week of future bookings is not
    # evidence of anything and would drag every active patient's score down.
    settled = (VisitStatus.COMPLETED, VisitStatus.MISSED, VisitStatus.CANCELLED)
    rows = db.execute(
        select(Visit.status, func.count(Visit.id))
        .where(
            Visit.patient_id == patient.id,
            Visit.scheduled_at >= since,
            Visit.scheduled_at < until,
            Visit.status.in_(settled),
        )
        .group_by(Visit.status)
    ).all()

    counts = {status: int(count) for status, count in rows}
    total = sum(counts.values())
    if not total:
        return Measured(None, "No visits were due in this period.")
    completed = counts.get(VisitStatus.COMPLETED, 0)
    return Measured(
        _clamp(completed / total),
        f"{completed} of {total} planned nurse visits went ahead.",
    )


def _alert_burden(db: Session, patient: Patient, since: datetime, until: datetime) -> Measured:
    """Absence of alerts is real evidence, so this component is never 'no data'."""
    rows = db.execute(
        select(Alert.severity, func.count(Alert.id))
        .where(
            Alert.patient_id == patient.id,
            Alert.created_at >= since,
            Alert.created_at < until,
        )
        .group_by(Alert.severity)
    ).all()

    counts = {severity: int(count) for severity, count in rows}
    raised = sum(counts.values())
    weighted = sum(
        count * (clinical.SAFETY_CRITICAL_MULTIPLIER if severity == AlertSeverity.CRITICAL else 1)
        for severity, count in counts.items()
    )
    value = _clamp(1 - weighted / clinical.SAFETY_ALERT_SATURATION)

    if not raised:
        detail = "Nothing needed the care team's attention in this period."
    elif raised == 1:
        detail = "One thing needed the care team's attention in this period."
    else:
        detail = f"{raised} things needed the care team's attention in this period."
    return Measured(value, detail)


def _mood(db: Session, patient: Patient, since: datetime, until: datetime) -> Measured:
    lookback = until - timedelta(days=clinical.SAFETY_MOOD_LOOKBACK_DAYS)
    screening = db.scalar(
        select(Screening)
        .where(
            Screening.patient_id == patient.id,
            Screening.instrument == ScreeningInstrument.PHQ2,
            Screening.administered_at >= lookback,
            Screening.administered_at < until,
        )
        .order_by(Screening.administered_at.desc(), Screening.id.desc())
        .limit(1)
    )
    if screening is None:
        return Measured(None, "No mood check has been recorded recently.")

    # PHQ-2 counts *upwards* for low mood, so the value is inverted.
    value = _clamp(1 - (screening.score / screening.max_score if screening.max_score else 0))
    if screening.positive:
        detail = "The last mood check suggested a follow-up conversation would help."
    else:
        detail = "The last mood check did not raise any concern."
    return Measured(value, detail)


def _connected_monitoring(
    db: Session, patient: Patient, since: datetime, until: datetime
) -> Measured:
    device_ids = list(
        db.scalars(
            select(Device.id).where(
                Device.patient_id == patient.id, Device.status == DeviceStatus.ACTIVE
            )
        )
    )
    # Not owning a home monitor is not unsafe, and must not cost points. The
    # component is simply dropped and the rest of the scale is rescaled.
    if not device_ids:
        return Measured(None, "No home monitor is connected.")

    readings = db.execute(
        select(
            func.count(DeviceReading.id),
            # `case` rather than casting the boolean: SQLite stores it as 0/1
            # but Postgres does not, and summing a bool is an error there.
            func.coalesce(func.sum(case((DeviceReading.triggered.is_(True), 1), else_=0)), 0),
        ).where(
            DeviceReading.patient_id == patient.id,
            DeviceReading.recorded_at >= since,
            DeviceReading.recorded_at < until,
        )
    ).one()
    total = int(readings[0] or 0)
    triggered = int(readings[1] or 0)

    if not total:
        # A monitor that was connected and then went quiet *is* a finding, and a
        # different one from never having had a monitor at all.
        return Measured(0.0, "A home monitor is connected but has not sent a reading recently.")

    settled = total - triggered
    return Measured(
        _clamp(settled / total),
        f"{settled} of {total} home readings were in the expected range.",
    )


COMPONENT_FUNCTIONS: dict[str, Callable[[Session, Patient, datetime, datetime], Measured]] = {
    "vital_stability": _vital_stability,
    "medication_adherence": _medication_adherence,
    "care_continuity": _care_continuity,
    "alert_burden": _alert_burden,
    "mood": _mood,
    "connected_monitoring": _connected_monitoring,
}


# --------------------------------------------------------------------------
# The score
# --------------------------------------------------------------------------


def compute(
    db: Session, patient: Patient, as_of: datetime | None = None, window_days: int | None = None
) -> dict[str, Any]:
    """Calculate the score without writing anything.

    Deterministic: the same database and the same `as_of` always produce the
    same number. Nothing here reads the clock except through `as_of`.
    """
    until = as_of or now()
    days = window_days or clinical.SAFETY_WINDOW_DAYS
    since = until - timedelta(days=days)

    components: list[dict[str, Any]] = []
    earned = 0.0
    covered = 0

    # Iterated in `SAFETY_COMPONENTS` order, not dict order, so the breakdown a
    # family reads is always in the same order as the constants file.
    for spec in clinical.SAFETY_COMPONENTS:
        measured = COMPONENT_FUNCTIONS[spec.key](db, patient, since, until)
        has_data = measured.value is not None
        points = round(spec.weight * measured.value, 1) if has_data else None
        if has_data:
            earned += spec.weight * measured.value
            covered += spec.weight
        components.append(
            {
                "key": spec.key,
                "label": spec.label,
                "blurb": spec.blurb,
                "weight": spec.weight,
                "value": round(measured.value, 4) if has_data else None,
                "points": points,
                "detail": measured.detail,
                "has_data": has_data,
            }
        )

    available = covered >= clinical.SAFETY_MIN_COVERED_WEIGHT
    score = int(round(earned / covered * clinical.SCORE_MAX)) if available and covered else None
    band = clinical.band_for(score) if score is not None else None

    return {
        "patient_id": patient.id,
        "available": available,
        "score": score,
        "band": band.key if band else None,
        "band_label": band.label if band else None,
        "band_tone": band.tone if band else None,
        "band_blurb": band.blurb if band else None,
        "window_days": days,
        "covered_weight": covered,
        "total_weight": sum(clinical.SAFETY_WEIGHTS.values()),
        "components": components,
        "calculated_at": until,
        "unavailable_reason": (
            None
            if available
            else "There is not enough recorded care yet to publish a safety score."
        ),
    }


def _comparison_score(db: Session, patient_id: int, until: datetime) -> SafetyScore | None:
    """The newest stored score at least the recorded drop-window old.

    Comparing against *yesterday's* score would make the recorded "10 points in
    30 days" rule fire on noise; comparing against the oldest would make it fire
    on ancient history. The newest score outside the window is the one the rule
    actually describes.
    """
    cutoff = until - timedelta(days=clinical.SAFETY_DROP_WINDOW_DAYS)
    return db.scalar(
        select(SafetyScore)
        .where(SafetyScore.patient_id == patient_id, SafetyScore.calculated_at <= cutoff)
        .order_by(SafetyScore.calculated_at.desc(), SafetyScore.id.desc())
        .limit(1)
    )


def record(
    db: Session,
    patient: Patient,
    as_of: datetime | None = None,
    window_days: int | None = None,
    notify: bool = True,
) -> SafetyScore | None:
    """Calculate, store, and raise an alert on the recorded 10-point drop.

    Returns None when there is not enough data to publish a score — nothing is
    stored in that case, so a patient's history never contains a number the
    platform was not willing to show.
    """
    payload = compute(db, patient, as_of=as_of, window_days=window_days)
    if not payload["available"]:
        return None

    until = payload["calculated_at"]
    previous = _comparison_score(db, patient.id, until)
    score = int(payload["score"])
    delta = score - previous.score if previous is not None else None

    row = SafetyScore(
        patient_id=patient.id,
        score=score,
        band=SafetyBand(payload["band"]),
        window_days=payload["window_days"],
        covered_weight=payload["covered_weight"],
        previous_score=previous.score if previous is not None else None,
        delta=delta,
        calculated_at=until,
    )
    row.components = payload["components"]
    db.add(row)
    db.flush()

    if delta is not None and -delta >= clinical.SAFETY_DROP_POINTS:
        _raise_drop_alert(db, patient, row, notify=notify)

    return row


def _raise_drop_alert(
    db: Session, patient: Patient, row: SafetyScore, notify: bool = True
) -> Alert:
    """RECORDED: a 10+ point drop inside 30 days raises an alert.

    Wording and severity are `ASSUMED`. Written in the family's vocabulary
    because a family member sees this alert on their own screen — the whole
    point of the score is that they can read it.
    """
    drop = -(row.delta or 0)
    return alert_service.create_alert(
        db,
        patient=patient,
        alert_type="safety_score_drop",
        severity=AlertSeverity.WARNING,  # ASSUMED
        title="Safety score has fallen",
        message=(
            f"{patient.name}'s safety score has fallen {drop} points "
            f"(from {row.previous_score} to {row.score}) over the last "
            f"{clinical.SAFETY_DROP_WINDOW_DAYS} days. The care team has been asked to review. "
            "This is a monitoring signal, not a medical diagnosis."
        ),
        notify=notify,
    )


def latest(db: Session, patient_id: int) -> SafetyScore | None:
    return db.scalar(
        select(SafetyScore)
        .where(SafetyScore.patient_id == patient_id)
        .order_by(SafetyScore.calculated_at.desc(), SafetyScore.id.desc())
        .limit(1)
    )


def history(db: Session, patient_id: int, limit: int = 24) -> list[SafetyScore]:
    rows = list(
        db.scalars(
            select(SafetyScore)
            .where(SafetyScore.patient_id == patient_id)
            .order_by(SafetyScore.calculated_at.desc(), SafetyScore.id.desc())
            .limit(limit)
        )
    )
    return list(reversed(rows))  # oldest first, for charting


def serialize(row: SafetyScore) -> dict[str, Any]:
    band = clinical.band_for(row.score)
    return {
        "id": row.id,
        "patient_id": row.patient_id,
        "score": row.score,
        "band": row.band.value,
        "band_label": band.label,
        "band_tone": band.tone,
        "band_blurb": band.blurb,
        "window_days": row.window_days,
        "covered_weight": row.covered_weight,
        "total_weight": sum(clinical.SAFETY_WEIGHTS.values()),
        "previous_score": row.previous_score,
        "delta": row.delta,
        "components": row.components,
        "calculated_at": row.calculated_at,
    }
