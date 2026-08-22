"""Vitals recording and the patient threshold engine.

The threshold engine is the core business rule of the MVP: every reading is
compared against the patient's configured monitoring thresholds inside the same
request that stores the reading, and any breach raises one alert.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Patient, PatientThreshold, Vital, VitalMetric

METRIC_UNITS: dict[str, str] = {
    "systolic_bp": " mmHg",
    "diastolic_bp": " mmHg",
    "heart_rate": " bpm",
    "blood_glucose": " mg/dL",
    "spo2": "%",
    "temperature": " F",
    "weight": " kg",
}

# Demo configuration used when a patient has no threshold rows yet.
DEFAULT_THRESHOLDS: dict[str, tuple[float, float]] = {
    VitalMetric.SYSTOLIC_BP.value: (90, 140),
    VitalMetric.DIASTOLIC_BP.value: (60, 90),
    VitalMetric.HEART_RATE.value: (50, 100),
    VitalMetric.BLOOD_GLUCOSE.value: (70, 180),
    VitalMetric.SPO2.value: (94, 100),
    VitalMetric.TEMPERATURE.value: (95, 100.4),
    VitalMetric.WEIGHT.value: (35, 120),
}


def load_thresholds(db: Session, patient_id: int) -> list[PatientThreshold]:
    return list(
        db.scalars(select(PatientThreshold).where(PatientThreshold.patient_id == patient_id))
    )


def evaluate_thresholds(vital: Vital, thresholds: list[PatientThreshold]) -> list[dict[str, Any]]:
    """Compare a reading against every enabled threshold and collect all breaches."""
    breaches: list[dict[str, Any]] = []

    for threshold in thresholds:
        if not threshold.enabled:
            continue

        metric = threshold.metric.value
        value = getattr(vital, metric, None)
        if value is None:
            continue

        unit = METRIC_UNITS.get(metric, "")

        if threshold.high_threshold is not None and value > threshold.high_threshold:
            breaches.append(
                {
                    "metric": metric,
                    "value": value,
                    "threshold": threshold.high_threshold,
                    "direction": "above",
                    "unit": unit,
                }
            )
        elif threshold.low_threshold is not None and value < threshold.low_threshold:
            breaches.append(
                {
                    "metric": metric,
                    "value": value,
                    "threshold": threshold.low_threshold,
                    "direction": "below",
                    "unit": unit,
                }
            )

    return breaches


def create_default_thresholds(db: Session, patient: Patient) -> list[PatientThreshold]:
    """Seed the demo threshold configuration for a patient that has none."""
    created: list[PatientThreshold] = []
    for metric, (low, high) in DEFAULT_THRESHOLDS.items():
        threshold = PatientThreshold(
            patient_id=patient.id,
            metric=VitalMetric(metric),
            low_threshold=low,
            high_threshold=high,
            enabled=True,
        )
        db.add(threshold)
        created.append(threshold)
    return created


def serialize(vital: Vital) -> dict[str, Any]:
    return {
        "id": vital.id,
        "patient_id": vital.patient_id,
        "visit_id": vital.visit_id,
        "systolic_bp": vital.systolic_bp,
        "diastolic_bp": vital.diastolic_bp,
        "heart_rate": vital.heart_rate,
        "blood_glucose": vital.blood_glucose,
        "spo2": vital.spo2,
        "temperature": vital.temperature,
        "weight": vital.weight,
        "threshold_breached": vital.threshold_breached,
        "recorded_at": vital.recorded_at,
    }


def latest_for_patient(db: Session, patient_id: int) -> Vital | None:
    return db.scalar(
        select(Vital)
        .where(Vital.patient_id == patient_id)
        .order_by(Vital.recorded_at.desc(), Vital.id.desc())
        .limit(1)
    )


def history_since(
    db: Session, patient_id: int, since: datetime, until: datetime | None = None
) -> list[Vital]:
    """Every reading in `[since, until)`, oldest first.

    `history_for_patient` limits by *count*, which is what a chart wants. A
    summary window limits by *date*, which is a different question — thirty
    readings and thirty days are the same thing only by accident.

    `until` exists because a monthly report covers a closed calendar month, not
    "the last 30 days". Without it a July report quotes an August reading.
    """
    query = select(Vital).where(Vital.patient_id == patient_id, Vital.recorded_at >= since)
    if until is not None:
        query = query.where(Vital.recorded_at < until)
    return list(db.scalars(query.order_by(Vital.recorded_at, Vital.id)))


def history_for_patient(db: Session, patient_id: int, limit: int = 30) -> list[Vital]:
    rows = list(
        db.scalars(
            select(Vital)
            .where(Vital.patient_id == patient_id)
            .order_by(Vital.recorded_at.desc(), Vital.id.desc())
            .limit(limit)
        )
    )
    return list(reversed(rows))  # oldest first, for charting
