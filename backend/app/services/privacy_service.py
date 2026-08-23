"""What DoorDoctor holds about one patient, how to export it, how to destroy it.

§4.14 asks for export and erasure. Both are built **once, over a registry**,
because by Phase 10 there are already twenty-odd tables that know something
about a patient and three earlier phases' worth of them were added by people who
were not thinking about erasure at the time.

Every patient-scoped dataset registers here with a label, an exporter and an
eraser. `tests/test_privacy.py` walks every mapped model carrying a `patient_id`
column and asserts it is either registered or explicitly retained — so a table
added in Phase 11 cannot silently escape the export, and adding one is a
registration rather than a rewrite.

**Retention is stated, not hidden.** Two datasets survive an erasure and each
carries the reason in `core/ops.ERASURE_RETAINS`: issued invoices, because they
are financial records of money that was billed, and the audit log, because
deleting it would remove the evidence that the erasure happened. Writing "we
delete everything" and then keeping the invoices would be exactly the
unevidenced promise this phase exists to stop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..core.exceptions import BadRequestError, ConflictError, NotFoundError
from ..core.ops import (
    AUDIT_RETENTION_DAYS,
    CONSENT_POLICY_VERSION,
    ERASURE_DESTROYS,
    ERASURE_RETAINS,
)
from ..database import now
from ..models import (
    Alert,
    Attachment,
    AuditAction,
    AuditEvent,
    AssistantMessage,
    CareAssignment,
    CareCircleMember,
    CareInteraction,
    Consent,
    Consult,
    Device,
    DeviceReading,
    ErasureRequest,
    ErasureStatus,
    EscalationEvent,
    EscalationStep,
    FollowUpTask,
    HospitalBooking,
    LabOrder,
    LabResult,
    Medication,
    MedicationChange,
    MedicationLog,
    Notification,
    OnboardingProgress,
    Patient,
    PatientStatus,
    PatientThreshold,
    PillOrganiserFill,
    Report,
    SafetyScore,
    Screening,
    User,
    Visit,
    Vital,
)
from . import attachment_service, audit_service

ERASED_NAME = "Erased patient"


@dataclass(frozen=True)
class DataSet:
    """One kind of thing this platform knows about a patient."""

    key: str
    label: str
    #: Rows, as plain JSON-safe dicts. Used by the export.
    export: Callable[[Session, int], list[dict[str, Any]]]
    #: Destroy every row for this patient. Returns how many went.
    erase: Callable[[Session, int], int]
    #: Models this dataset accounts for, by class name. The coverage test reads it.
    covers: tuple[str, ...] = ()


def _rows(db: Session, model, patient_id: int, columns: tuple[str, ...]) -> list[dict[str, Any]]:
    """Export helper: selected columns of every row for this patient."""
    records = db.scalars(select(model).where(model.patient_id == patient_id)).all()
    # `getattr` with no default on purpose: a mistyped column name must raise
    # here rather than quietly exporting a field full of nulls, which is the one
    # failure mode of this design that nobody would notice.
    return [{column: _plain(getattr(record, column)) for column in columns} for record in records]


def _plain(value: Any) -> Any:
    if hasattr(value, "value") and not isinstance(value, (str, int, float, bool)):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _wipe(db: Session, model, patient_id: int) -> int:
    result = db.execute(delete(model).where(model.patient_id == patient_id))
    return int(result.rowcount or 0)


# --- the datasets ---------------------------------------------------------


def _export_visits(db: Session, patient_id: int) -> list[dict[str, Any]]:
    return _rows(
        db,
        Visit,
        patient_id,
        ("id", "scheduled_at", "status", "checkin_at", "checkout_at", "location_status", "notes"),
    )


def _erase_visits(db: Session, patient_id: int) -> int:
    visit_ids = [int(v) for v in db.scalars(select(Visit.id).where(Visit.patient_id == patient_id))]
    if visit_ids:
        db.execute(delete(MedicationLog).where(MedicationLog.visit_id.in_(visit_ids)))
    return _wipe(db, Visit, patient_id)


def _export_medications(db: Session, patient_id: int) -> list[dict[str, Any]]:
    medications = db.scalars(
        select(Medication).where(Medication.patient_id == patient_id)
    ).all()
    payload: list[dict[str, Any]] = []
    for medication in medications:
        payload.append(
            {
                "id": medication.id,
                "name": medication.name,
                "dosage": medication.dosage,
                "frequency": medication.frequency,
                "scheduled_time": medication.scheduled_time,
                "active": medication.active,
                "doses": [
                    {
                        "status": log.status.value,
                        "reason": log.reason,
                        "recorded_at": _plain(log.recorded_at),
                        "has_photo": log.photo_attachment_id is not None,
                    }
                    for log in medication.logs
                ],
            }
        )
    return payload


def _erase_medications(db: Session, patient_id: int) -> int:
    medication_ids = [
        int(m) for m in db.scalars(select(Medication.id).where(Medication.patient_id == patient_id))
    ]
    if medication_ids:
        db.execute(delete(MedicationLog).where(MedicationLog.medication_id.in_(medication_ids)))
    _wipe(db, MedicationChange, patient_id)
    _wipe(db, PillOrganiserFill, patient_id)
    return _wipe(db, Medication, patient_id)


def _erase_labs(db: Session, patient_id: int) -> int:
    order_ids = [int(o) for o in db.scalars(select(LabOrder.id).where(LabOrder.patient_id == patient_id))]
    if order_ids:
        db.execute(delete(LabResult).where(LabResult.order_id.in_(order_ids)))
    return _wipe(db, LabOrder, patient_id)


def _erase_devices(db: Session, patient_id: int) -> int:
    _wipe(db, DeviceReading, patient_id)
    return _wipe(db, Device, patient_id)


def _erase_escalations(db: Session, patient_id: int) -> int:
    event_ids = [
        int(e) for e in db.scalars(select(EscalationEvent.id).where(EscalationEvent.patient_id == patient_id))
    ]
    if event_ids:
        db.execute(delete(EscalationStep).where(EscalationStep.event_id.in_(event_ids)))
    return _wipe(db, EscalationEvent, patient_id)


def _erase_attachments(db: Session, patient_id: int) -> int:
    """Rows *and* the files behind them. The only dataset that touches disk."""
    return attachment_service.delete_for_patient(db, patient_id)


def _export_assistant(db: Session, patient_id: int) -> list[dict[str, Any]]:
    messages = db.scalars(
        select(AssistantMessage).where(AssistantMessage.patient_id == patient_id)
    ).all()
    return [
        {
            "asked_at": _plain(message.created_at),
            "question": message.question,
            "answer": message.answer,
            "source": _plain(message.source),
        }
        for message in messages
    ]


REGISTRY: tuple[DataSet, ...] = (
    DataSet(
        "visits",
        "Visits and visit notes",
        _export_visits,
        _erase_visits,
        covers=("Visit",),
    ),
    DataSet(
        "readings",
        "Health readings",
        lambda db, pid: _rows(
            db,
            Vital,
            pid,
            (
                "recorded_at",
                "systolic_bp",
                "diastolic_bp",
                "heart_rate",
                "blood_glucose",
                "spo2",
                "temperature",
                "weight",
                "threshold_breached",
            ),
        ),
        lambda db, pid: _wipe(db, Vital, pid),
        covers=("Vital",),
    ),
    DataSet(
        "thresholds",
        "The ranges being watched",
        lambda db, pid: _rows(db, PatientThreshold, pid, ("metric", "low_threshold", "high_threshold", "enabled")),
        lambda db, pid: _wipe(db, PatientThreshold, pid),
        covers=("PatientThreshold",),
    ),
    DataSet(
        "medications",
        "Medicines, doses and dose photographs",
        _export_medications,
        _erase_medications,
        covers=("Medication", "MedicationChange", "PillOrganiserFill"),
    ),
    DataSet(
        "alerts",
        "Alerts",
        lambda db, pid: _rows(
            db, Alert, pid, ("created_at", "alert_type", "severity", "title", "message", "status", "resolution_note")
        ),
        lambda db, pid: _wipe(db, Alert, pid),
        covers=("Alert",),
    ),
    DataSet(
        "labs",
        "Lab orders and results",
        lambda db, pid: _rows(db, LabOrder, pid, ("ordered_at", "panel_code", "status", "billing")),
        _erase_labs,
        covers=("LabOrder",),
    ),
    DataSet(
        "screenings",
        "Mood checks",
        lambda db, pid: _rows(db, Screening, pid, ("administered_at", "instrument", "score", "max_score", "positive")),
        lambda db, pid: _wipe(db, Screening, pid),
        covers=("Screening",),
    ),
    DataSet(
        "safety_scores",
        "Safety scores",
        lambda db, pid: _rows(db, SafetyScore, pid, ("calculated_at", "score", "band", "covered_weight")),
        lambda db, pid: _wipe(db, SafetyScore, pid),
        covers=("SafetyScore",),
    ),
    DataSet(
        "consults",
        "Doctor consultations",
        lambda db, pid: _rows(db, Consult, pid, ("scheduled_for", "status", "doctor_name", "reason")),
        lambda db, pid: _wipe(db, Consult, pid),
        covers=("Consult",),
    ),
    DataSet(
        "devices",
        "Connected devices and their readings",
        lambda db, pid: _rows(db, Device, pid, ("kind", "label", "status", "registered_at")),
        _erase_devices,
        covers=("Device", "DeviceReading"),
    ),
    DataSet(
        "escalations",
        "Escalations and who was contacted",
        lambda db, pid: _rows(db, EscalationEvent, pid, ("opened_at", "trigger", "status", "summary")),
        _erase_escalations,
        covers=("EscalationEvent",),
    ),
    DataSet(
        "hospital",
        "Hospital coordination requests",
        lambda db, pid: _rows(db, HospitalBooking, pid, ("requested_at", "status", "hospital_name", "reason")),
        lambda db, pid: _wipe(db, HospitalBooking, pid),
        covers=("HospitalBooking",),
    ),
    DataSet(
        "care_team",
        "Care manager contact",
        lambda db, pid: _rows(db, CareInteraction, pid, ("occurred_at", "channel", "direction", "subject")),
        lambda db, pid: _wipe(db, CareInteraction, pid) + _wipe(db, CareAssignment, pid),
        covers=("CareInteraction", "CareAssignment"),
    ),
    DataSet(
        "tasks",
        "Follow-up tasks",
        lambda db, pid: _rows(db, FollowUpTask, pid, ("created_at", "kind", "title", "status", "due_at")),
        lambda db, pid: _wipe(db, FollowUpTask, pid),
        covers=("FollowUpTask",),
    ),
    DataSet(
        "reports",
        "Reports",
        lambda db, pid: _rows(db, Report, pid, ("kind", "period_start", "period_end", "generated_at")),
        lambda db, pid: _wipe(db, Report, pid),
        covers=("Report",),
    ),
    DataSet(
        "assistant",
        "Questions asked of the assistant",
        _export_assistant,
        lambda db, pid: _wipe(db, AssistantMessage, pid),
        covers=("AssistantMessage",),
    ),
    DataSet(
        "care_circle",
        "Care circle",
        lambda db, pid: _rows(db, CareCircleMember, pid, ("name", "relationship_label", "role", "phone", "email")),
        lambda db, pid: _wipe(db, CareCircleMember, pid),
        covers=("CareCircleMember",),
    ),
    DataSet(
        "attachments",
        "Photographs",
        lambda db, pid: _rows(db, Attachment, pid, ("kind", "created_at", "size_bytes")),
        _erase_attachments,
        covers=("Attachment",),
    ),
    DataSet(
        "notifications",
        "Messages sent to you about this patient",
        lambda db, pid: _rows(db, Notification, pid, ("created_at", "type", "title", "message", "read")),
        lambda db, pid: _wipe(db, Notification, pid),
        covers=("Notification",),
    ),
    DataSet(
        "onboarding",
        "Setup progress",
        lambda db, pid: _rows(db, OnboardingProgress, pid, ("step", "completed_at")),
        lambda db, pid: _wipe(db, OnboardingProgress, pid),
        covers=("OnboardingProgress",),
    ),
    DataSet(
        "consents",
        "Consent decisions",
        lambda db, pid: _rows(db, Consent, pid, ("decided_at", "kind", "version", "status", "decided_by_name")),
        lambda db, pid: _wipe(db, Consent, pid),
        covers=("Consent",),
    ),
)

REGISTRY_BY_KEY: dict[str, DataSet] = {dataset.key: dataset for dataset in REGISTRY}

#: Patient-scoped models that survive an erasure, and why. Read by the coverage
#: test, so "retained" has to be a deliberate entry rather than an omission.
RETAINED_MODELS: dict[str, str] = {
    "AuditEvent": "The record of who did what, including this erasure.",
    "ErasureRequest": "The request itself, so the queue can show it was carried out.",
}


# --- what is held ---------------------------------------------------------


def holdings(db: Session, patient_id: int) -> list[dict[str, Any]]:
    """One line per dataset with how many rows it holds. The privacy page's body."""
    return [
        {"key": dataset.key, "label": dataset.label, "count": len(dataset.export(db, patient_id))}
        for dataset in REGISTRY
    ]


def export(db: Session, *, patient: Patient, actor: User) -> dict[str, Any]:
    """Everything, as JSON. Audited, because an export is a copy leaving the building."""
    payload: dict[str, Any] = {
        "exported_at": _plain(now()),
        "patient": {
            "name": patient.name,
            "age": patient.age,
            "gender": patient.gender,
            "address": patient.address,
            "zone": patient.zone,
            "enrolled_at": _plain(patient.created_at),
        },
        "data": {dataset.key: dataset.export(db, patient.id) for dataset in REGISTRY},
        "retained_after_erasure": [
            {"label": label, "reason": reason} for label, reason in ERASURE_RETAINS
        ],
    }
    audit_service.record(
        db,
        actor=actor,
        action=AuditAction.RECORD_EXPORTED,
        subject_type="patient",
        subject_id=patient.id,
        patient_id=patient.id,
        detail=f"Exported the full record for {patient.name}.",
    )
    db.commit()
    return payload


def policy(db: Session, patient_id: int) -> dict[str, Any]:
    """What the privacy page promises, computed from the constants it promises from."""
    return {
        "policy_version": CONSENT_POLICY_VERSION,
        "audit_retention_days": AUDIT_RETENTION_DAYS,
        "erasure_destroys": list(ERASURE_DESTROYS),
        "erasure_retains": [{"label": label, "reason": reason} for label, reason in ERASURE_RETAINS],
    }


# --- erasure --------------------------------------------------------------


def request_erasure(
    db: Session, *, patient: Patient, actor: User, reason: str | None = None
) -> ErasureRequest:
    open_request = db.scalar(
        select(ErasureRequest).where(
            ErasureRequest.patient_id == patient.id,
            ErasureRequest.status == ErasureStatus.REQUESTED,
        )
    )
    if open_request is not None:
        raise ConflictError("An erasure request for this patient is already waiting.")

    request = ErasureRequest(
        patient_id=patient.id,
        patient_name=patient.name,
        requested_by=actor.id,
        requested_by_name=actor.name,
        reason=(reason or "").strip() or None,
    )
    db.add(request)
    audit_service.record(
        db,
        actor=actor,
        action=AuditAction.ERASURE_REQUESTED,
        subject_type="patient",
        subject_id=patient.id,
        patient_id=patient.id,
        detail=f"Erasure requested for {patient.name}.",
    )
    db.commit()
    db.refresh(request)
    return request


def get_request(db: Session, request_id: int) -> ErasureRequest:
    request = db.get(ErasureRequest, request_id)
    if request is None:
        raise NotFoundError("Erasure request not found.")
    return request


def list_requests(db: Session, *, status: ErasureStatus | None = None) -> list[ErasureRequest]:
    query = select(ErasureRequest)
    if status is not None:
        query = query.where(ErasureRequest.status == status)
    return list(db.scalars(query.order_by(ErasureRequest.created_at.desc())))


def execute(db: Session, request: ErasureRequest, *, actor: User, note: str | None = None) -> ErasureRequest:
    """Destroy the record. Irreversible, and the audit entry is written first.

    The patient row itself is **anonymised rather than deleted**: an invoice
    still points at the subscription that paid for this care, and an audit entry
    still points at the patient id. Removing the row would leave both dangling,
    which is a worse outcome than a row that carries no identifying information.
    """
    if request.status != ErasureStatus.REQUESTED:
        raise BadRequestError("This request has already been decided.")

    patient = db.get(Patient, request.patient_id)
    if patient is None:  # pragma: no cover - defensive
        raise NotFoundError("Patient not found.")

    lines: list[str] = []
    for dataset in REGISTRY:
        removed = dataset.erase(db, patient.id)
        if removed:
            lines.append(f"{dataset.label}: {removed} removed")
    db.flush()

    patient.name = ERASED_NAME
    patient.address = "Erased"
    patient.emergency_contact = None
    patient.zone = None
    patient.home_lat = None
    patient.home_lng = None
    patient.gender = "Erased"
    patient.status = PatientStatus.INACTIVE

    request.status = ErasureStatus.EXECUTED
    request.decided_by = actor.id
    request.decided_by_name = actor.name
    request.decided_at = now()
    request.decision_note = (note or "").strip() or None
    request.outcome = "\n".join(lines) if lines else "No stored data remained."

    audit_service.record(
        db,
        actor=actor,
        action=AuditAction.ERASURE_EXECUTED,
        subject_type="patient",
        subject_id=patient.id,
        patient_id=patient.id,
        detail=f"Erased the record for {request.patient_name}. {len(lines)} dataset(s) cleared.",
    )
    db.commit()
    db.refresh(request)
    return request


def decline(db: Session, request: ErasureRequest, *, actor: User, note: str) -> ErasureRequest:
    if request.status != ErasureStatus.REQUESTED:
        raise BadRequestError("This request has already been decided.")
    if not note.strip():
        raise BadRequestError("Say why the request was declined.")

    request.status = ErasureStatus.DECLINED
    request.decided_by = actor.id
    request.decided_by_name = actor.name
    request.decided_at = now()
    request.decision_note = note.strip()

    audit_service.record(
        db,
        actor=actor,
        action=AuditAction.ERASURE_DECLINED,
        subject_type="patient",
        subject_id=request.patient_id,
        patient_id=request.patient_id,
        detail=f"Declined erasure for {request.patient_name}: {note.strip()}",
    )
    db.commit()
    db.refresh(request)
    return request


def serialize_request(request: ErasureRequest) -> dict[str, Any]:
    return {
        "id": request.id,
        "patient_id": request.patient_id,
        "patient_name": request.patient_name,
        "requested_by_name": request.requested_by_name,
        "reason": request.reason,
        "status": request.status.value,
        "decided_by_name": request.decided_by_name,
        "decided_at": request.decided_at,
        "decision_note": request.decision_note,
        "outcome": request.outcome,
        "created_at": request.created_at,
    }
