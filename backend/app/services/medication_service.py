"""Medication schedules, dose logs, adherence, organiser fills and history.

Phase 10 (§4.12) adds three things and one rule.

The rule: **every edit to a medication writes a `MedicationChange`, and only
this module writes one.** A history with gaps is worse than no history, because
a gap looks like a period when nothing changed.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.exceptions import BadRequestError, NotFoundError
from ..core.ops import PILL_ORGANISER_COMPARTMENTS, PILL_ORGANISER_DAYS
from ..core.pricing import ADD_ONS_BY_CODE
from ..database import now
from ..models import (
    AttachmentKind,
    AuditAction,
    Medication,
    MedicationChange,
    MedicationChangeKind,
    MedicationLog,
    MedicationLogStatus,
    Patient,
    PillOrganiserFill,
    PillOrganiserStatus,
    User,
    Visit,
    VisitStatus,
)
from ..schemas.medication import MedicationCreate, MedicationLogCreate
from . import attachment_service, audit_service

PILL_ORGANISER_ADDON = "pill_organiser"


def list_medications(db: Session, patient_id: int, active_only: bool = False) -> list[Medication]:
    query = select(Medication).where(Medication.patient_id == patient_id)
    if active_only:
        query = query.where(Medication.active.is_(True))
    return list(db.scalars(query.order_by(Medication.scheduled_time, Medication.name)))


def create_medication(
    db: Session, patient_id: int, payload: MedicationCreate, actor: User | None = None
) -> Medication:
    medication = Medication(
        patient_id=patient_id,
        name=payload.name.strip(),
        dosage=payload.dosage.strip(),
        frequency=payload.frequency.strip() or "daily",
        scheduled_time=payload.scheduled_time,
        active=payload.active,
    )
    db.add(medication)
    db.flush()
    record_change(
        db,
        medication,
        kind=MedicationChangeKind.STARTED,
        new_value=f"{medication.dosage}, {medication.frequency} at {medication.scheduled_time}",
        actor=actor,
    )
    db.commit()
    db.refresh(medication)
    return medication


# --------------------------------------------------------------------------
# Change history (§4.12)
#
# "Why is she on half the dose now?" is one of the questions families ask most,
# and a current-state table cannot answer it. Every edit writes a row here, and
# a stopped medication is a row rather than a missing one.
# --------------------------------------------------------------------------


def record_change(
    db: Session,
    medication: Medication,
    *,
    kind: MedicationChangeKind,
    previous_value: str | None = None,
    new_value: str | None = None,
    reason: str | None = None,
    actor: User | None = None,
    at: datetime | None = None,
) -> MedicationChange:
    """The only writer of `MedicationChange`. Public so the seed can backdate.

    `at` exists because history that all happened at the instant the seed ran is
    not history — the same class of bug Phase 9 found in the safety-drop alerts.
    """
    change = MedicationChange(
        medication_id=medication.id,
        patient_id=medication.patient_id,
        kind=kind,
        previous_value=previous_value,
        new_value=new_value,
        reason=(reason or "").strip() or None,
        changed_by=actor.id if actor else None,
        changed_by_name=actor.name if actor else "DoorDoctor",
        changed_at=at or now(),
    )
    db.add(change)
    db.flush()
    return change


def update_medication(
    db: Session,
    medication: Medication,
    *,
    dosage: str | None = None,
    frequency: str | None = None,
    scheduled_time: str | None = None,
    active: bool | None = None,
    reason: str | None = None,
    actor: User | None = None,
) -> Medication:
    """Edit a medication and write down what changed, one row per change.

    A single edit that moves both the dose and the time produces **two** rows.
    Merging them into one "changed" entry would make the history unreadable
    exactly when it matters — a family asking why the dose is different does not
    want to diff two blobs.
    """
    changes: list[tuple[MedicationChangeKind, str | None, str | None]] = []

    if dosage is not None and dosage.strip() and dosage.strip() != medication.dosage:
        changes.append((MedicationChangeKind.DOSAGE_CHANGED, medication.dosage, dosage.strip()))
        medication.dosage = dosage.strip()

    schedule_before = f"{medication.frequency} at {medication.scheduled_time}"
    schedule_touched = False
    if frequency is not None and frequency.strip() and frequency.strip() != medication.frequency:
        medication.frequency = frequency.strip()
        schedule_touched = True
    if scheduled_time is not None and scheduled_time != medication.scheduled_time:
        medication.scheduled_time = scheduled_time
        schedule_touched = True
    if schedule_touched:
        changes.append(
            (
                MedicationChangeKind.SCHEDULE_CHANGED,
                schedule_before,
                f"{medication.frequency} at {medication.scheduled_time}",
            )
        )

    if active is not None and active != medication.active:
        medication.active = active
        changes.append(
            (
                MedicationChangeKind.RESUMED if active else MedicationChangeKind.STOPPED,
                "Stopped" if active else "Active",
                "Active" if active else "Stopped",
            )
        )

    for kind, before, after in changes:
        record_change(
            db,
            medication,
            kind=kind,
            previous_value=before,
            new_value=after,
            reason=reason,
            actor=actor,
        )

    if changes:
        audit_service.record(
            db,
            actor=actor,
            action=AuditAction.MEDICATION_CHANGED,
            subject_type="medication",
            subject_id=medication.id,
            patient_id=medication.patient_id,
            detail=f"{medication.name}: {', '.join(kind.value for kind, _, _ in changes)}.",
        )

    db.commit()
    db.refresh(medication)
    return medication


def change_history(db: Session, patient_id: int, limit: int = 100) -> list[MedicationChange]:
    return list(
        db.scalars(
            select(MedicationChange)
            .where(MedicationChange.patient_id == patient_id)
            .order_by(MedicationChange.changed_at.desc(), MedicationChange.id.desc())
            .limit(limit)
        )
    )


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


def adherence_for_patient(
    db: Session,
    patient_id: int,
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict[str, Any]:
    """administered / total logged doses, optionally only since a given moment.

    Returns `percentage: None` when nothing has been logged - the UI renders
    `No data` rather than 0%, which would wrongly imply missed medication.

    `since` is one optional argument rather than a second function on purpose:
    the plain-language summary reports the same number over a window that the
    dashboard reports over all time, and two implementations of one calculation
    is exactly how those two numbers start disagreeing.
    """
    query = (
        select(MedicationLog.status, func.count(MedicationLog.id))
        .join(Medication, MedicationLog.medication_id == Medication.id)
        .where(Medication.patient_id == patient_id)
    )
    if since is not None:
        query = query.where(MedicationLog.recorded_at >= since)
    if until is not None:
        query = query.where(MedicationLog.recorded_at < until)
    rows = db.execute(query.group_by(MedicationLog.status)).all()

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


# --------------------------------------------------------------------------
# Dose confirmation photos (§4.12)
# --------------------------------------------------------------------------


def attach_dose_photo(
    db: Session, log: MedicationLog, *, data: bytes, uploaded_by: User
) -> MedicationLog:
    """Attach the photograph the nurse took as they gave the dose.

    Replacing an existing photo deletes the old one rather than orphaning it —
    a health record's storage should not grow every time somebody retakes a
    blurry picture.
    """
    medication = db.get(Medication, log.medication_id)
    if medication is None:  # pragma: no cover - defensive
        raise NotFoundError("Medication not found.")
    patient = db.get(Patient, medication.patient_id)
    if patient is None:  # pragma: no cover - defensive
        raise NotFoundError("Patient not found.")

    previous = log.photo
    attachment = attachment_service.store(
        db,
        data=data,
        kind=AttachmentKind.DOSE_PHOTO,
        patient=patient,
        uploaded_by=uploaded_by,
    )
    log.photo_attachment_id = attachment.id
    if previous is not None and previous.id != attachment.id:
        attachment_service.delete(db, previous)

    db.commit()
    db.refresh(log)
    return log


# --------------------------------------------------------------------------
# Pill organiser fills (§4.12)
#
# The ₹199 add-on's first buyer. Phase 9 gave the ₹499 blood panel one and left
# this one priced and unsold; STATE.md recorded it as a deferral against the
# medication work, which is here.
# --------------------------------------------------------------------------


def _subscription_for(db: Session, patient: Patient):
    from ..models import Subscription

    return db.scalar(
        select(Subscription)
        .where(Subscription.family_user_id == patient.family_user_id)
        .order_by(Subscription.id.desc())
        .limit(1)
    )


def already_charged_this_month(db: Session, patient_id: int, moment: datetime) -> bool:
    """Whether this patient's organiser has already been billed this month.

    The add-on is priced **per month**, not per fill. A weekly organiser filled
    four times in March is one ₹199 charge — the family bought the service, not
    the plastic. Charging per fill would quietly turn a ₹199 line into ₹796.
    """
    start = moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return (
        db.scalar(
            select(func.count(PillOrganiserFill.id)).where(
                PillOrganiserFill.patient_id == patient_id,
                PillOrganiserFill.filled_at >= start,
                PillOrganiserFill.invoice_line_id.is_not(None),
            )
        )
        or 0
    ) > 0


def record_fill(
    db: Session,
    *,
    patient: Patient,
    filled_by: User,
    compartments_filled: int,
    visit: Visit | None = None,
    note: str | None = None,
    as_of: datetime | None = None,
) -> PillOrganiserFill:
    """Record an organiser fill, billing the month's add-on if it is not yet billed."""
    from ..services import billing_service

    moment = as_of or now()
    total = PILL_ORGANISER_COMPARTMENTS
    if compartments_filled < 0 or compartments_filled > total:
        raise BadRequestError(f"An organiser has {total} compartments.")

    if compartments_filled == 0:
        status = PillOrganiserStatus.NOT_FILLED
    elif compartments_filled < total:
        status = PillOrganiserStatus.PARTIAL
    else:
        status = PillOrganiserStatus.FILLED

    invoice_line_id: int | None = None
    subscription = _subscription_for(db, patient)
    # A fill nobody managed to make is not a purchase.
    if (
        subscription is not None
        and status != PillOrganiserStatus.NOT_FILLED
        and not already_charged_this_month(db, patient.id, moment)
    ):
        line = billing_service.charge_addon(
            db,
            subscription,
            addon_code=PILL_ORGANISER_ADDON,
            description=f"{ADD_ONS_BY_CODE[PILL_ORGANISER_ADDON].name} — {patient.name}",
            as_of=moment,
        )
        invoice_line_id = line.id

    fill = PillOrganiserFill(
        patient_id=patient.id,
        visit_id=visit.id if visit else None,
        filled_by=filled_by.id,
        filled_by_name=filled_by.name,
        status=status,
        compartments_filled=compartments_filled,
        compartments_total=total,
        covers_until=(moment + timedelta(days=PILL_ORGANISER_DAYS)).date(),
        note=(note or "").strip() or None,
        invoice_line_id=invoice_line_id,
        filled_at=moment,
    )
    db.add(fill)
    db.commit()
    db.refresh(fill)
    return fill


def list_fills(db: Session, patient_id: int, limit: int = 20) -> list[PillOrganiserFill]:
    return list(
        db.scalars(
            select(PillOrganiserFill)
            .where(PillOrganiserFill.patient_id == patient_id)
            .order_by(PillOrganiserFill.filled_at.desc())
            .limit(limit)
        )
    )


def latest_fill(db: Session, patient_id: int) -> PillOrganiserFill | None:
    fills = list_fills(db, patient_id, limit=1)
    return fills[0] if fills else None


def serialize_fill(fill: PillOrganiserFill) -> dict[str, Any]:
    return {
        "id": fill.id,
        "patient_id": fill.patient_id,
        "visit_id": fill.visit_id,
        "filled_by_name": fill.filled_by_name,
        "status": fill.status.value,
        "compartments_filled": fill.compartments_filled,
        "compartments_total": fill.compartments_total,
        "covers_until": fill.covers_until,
        "note": fill.note,
        "charged": fill.invoice_line_id is not None,
        "filled_at": fill.filled_at,
    }


def serialize_change(change: MedicationChange) -> dict[str, Any]:
    return {
        "id": change.id,
        "medication_id": change.medication_id,
        "medication_name": change.medication.name if change.medication else None,
        "kind": change.kind.value,
        "previous_value": change.previous_value,
        "new_value": change.new_value,
        "reason": change.reason,
        "changed_by_name": change.changed_by_name,
        "changed_at": change.changed_at,
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
        "photo": attachment_service.serialize(log.photo) if log.photo else None,
    }
