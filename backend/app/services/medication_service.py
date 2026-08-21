"""Medication schedules, administration logs and adherence."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.exceptions import BadRequestError, NotFoundError
from ..database import now
from ..models import Medication, MedicationLog, MedicationLogStatus, Visit, VisitStatus
from ..schemas.medication import MedicationCreate, MedicationLogCreate


def list_medications(db: Session, patient_id: int, active_only: bool = False) -> list[Medication]:
    query = select(Medication).where(Medication.patient_id == patient_id)
    if active_only:
        query = query.where(Medication.active.is_(True))
    return list(db.scalars(query.order_by(Medication.scheduled_time, Medication.name)))


def create_medication(db: Session, patient_id: int, payload: MedicationCreate) -> Medication:
    medication = Medication(
        patient_id=patient_id,
        name=payload.name.strip(),
        dosage=payload.dosage.strip(),
        frequency=payload.frequency.strip() or "daily",
        scheduled_time=payload.scheduled_time,
        active=payload.active,
    )
    db.add(medication)
    db.commit()
    db.refresh(medication)
    return medication


def log_administration(
    db: Session, visit: Visit, payload: MedicationLogCreate, recorded_by: int
) -> MedicationLog:
    """Record one dose outcome against an in-progress visit."""
    if visit.status == VisitStatus.COMPLETED:
        raise BadRequestError("A completed visit can no longer be edited.")
    if visit.status != VisitStatus.IN_PROGRESS or visit.checkin_at is None:
        raise BadRequestError("Visit must be checked in before medication can be logged.")

    medication = db.get(Medication, payload.medication_id)
    if medication is None or medication.patient_id != visit.patient_id:
        raise NotFoundError("Medication not found for this patient.")

    existing = db.scalar(
        select(MedicationLog).where(
            MedicationLog.visit_id == visit.id,
            MedicationLog.medication_id == medication.id,
        )
    )
    reason = payload.reason.strip() if payload.reason else None

    if existing is not None:
        # Re-submitting the same medication during a visit corrects the entry.
        existing.status = payload.status
        existing.reason = reason
        existing.recorded_at = now()
        existing.recorded_by = recorded_by
        db.commit()
        db.refresh(existing)
        return existing

    log = MedicationLog(
        medication_id=medication.id,
        visit_id=visit.id,
        status=payload.status,
        reason=reason,
        recorded_by=recorded_by,
        recorded_at=now(),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def logs_for_visit(db: Session, visit_id: int) -> list[MedicationLog]:
    return list(
        db.scalars(
            select(MedicationLog)
            .where(MedicationLog.visit_id == visit_id)
            .order_by(MedicationLog.recorded_at)
        )
    )


def adherence_for_patient(db: Session, patient_id: int) -> dict[str, Any]:
    """administered / total logged doses.

    Returns `percentage: None` when nothing has been logged - the UI renders
    `No data` rather than 0%, which would wrongly imply missed medication.
    """
    rows = db.execute(
        select(MedicationLog.status, func.count(MedicationLog.id))
        .join(Medication, MedicationLog.medication_id == Medication.id)
        .where(Medication.patient_id == patient_id)
        .group_by(MedicationLog.status)
    ).all()

    counts = {status.value if hasattr(status, "value") else str(status): int(count) for status, count in rows}
    administered = counts.get(MedicationLogStatus.ADMINISTERED.value, 0)
    skipped = counts.get(MedicationLogStatus.SKIPPED.value, 0)
    refused = counts.get(MedicationLogStatus.REFUSED.value, 0)
    total = administered + skipped + refused

    percentage = round(administered / total * 100) if total else None
    return {
        "percentage": percentage,
        "administered": administered,
        "skipped": skipped,
        "refused": refused,
        "total": total,
    }


def serialize(medication: Medication) -> dict[str, Any]:
    return {
        "id": medication.id,
        "patient_id": medication.patient_id,
        "name": medication.name,
        "dosage": medication.dosage,
        "frequency": medication.frequency,
        "scheduled_time": medication.scheduled_time,
        "active": medication.active,
    }


def serialize_log(log: MedicationLog) -> dict[str, Any]:
    return {
        "id": log.id,
        "medication_id": log.medication_id,
        "medication_name": log.medication.name if log.medication else None,
        "visit_id": log.visit_id,
        "status": log.status.value,
        "reason": log.reason,
        "recorded_at": log.recorded_at,
    }
