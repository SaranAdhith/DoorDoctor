"""Privacy and data: what is held, exporting it, and asking for it to go (§4.14).

The family-facing routes all resolve through `authorize_patient`, so a privacy
page shows one patient's holdings and never becomes a way to enumerate anybody
else's. The erasure queue is admin-only, because erasure is executed rather than
performed by the person who asked for it.
"""

from typing import Any

from fastapi import APIRouter, Query

from ..core.dependencies import AdminUser, CurrentUser, DbSession, authorize_patient
from ..core.exceptions import ForbiddenError
from ..models import ErasureStatus, Patient, UserRole
from ..schemas.privacy import (
    ConsentDecision,
    ConsentRecordOut,
    ErasureDecision,
    ErasureRequestCreate,
    ErasureRequestOut,
    PrivacyOverviewOut,
)
from ..services import audit_service, consent_service, privacy_service

router = APIRouter(tags=["privacy"])


@router.get(
    "/privacy/patients/{patient_id}",
    response_model=PrivacyOverviewOut,
    summary="What DoorDoctor holds about this patient",
)
def overview(patient_id: int, db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    patient = authorize_patient(db, current_user, patient_id)
    policy = privacy_service.policy(db, patient.id)
    open_request = next(
        (
            request
            for request in privacy_service.list_requests(db)
            if request.patient_id == patient.id
        ),
        None,
    )
    return {
        "patient_id": patient.id,
        "patient_name": patient.name,
        **policy,
        "holdings": privacy_service.holdings(db, patient.id),
        "consents": consent_service.summary(db, user_id=patient.family_user_id, patient_id=patient.id),
        "consent_history": [
            consent_service.serialize(record)
            for record in consent_service.history(db, user_id=patient.family_user_id, patient_id=patient.id)
        ],
        # Who has opened this record. The family's own reads are not logged at
        # all, and their own *actions* — the consents they granted, the exports
        # they took — are excluded here too: this section answers "who else has
        # been in my mother's record", and answering it with the reader's own
        # four consent rows is alarming and untrue.
        "audit_trail": [
            audit_service.serialize(entry)
            for entry in audit_service.list_events(
                db,
                patient_id=patient.id,
                exclude_actor_user_id=patient.family_user_id,
                limit=50,
            )
        ],
        "erasure_request": privacy_service.serialize_request(open_request) if open_request else None,
    }


@router.post(
    "/privacy/consents",
    response_model=ConsentRecordOut,
    status_code=201,
    summary="Record a consent decision",
)
def record_consent(
    payload: ConsentDecision, db: DbSession, current_user: CurrentUser
) -> dict[str, Any]:
    patient: Patient | None = None
    if payload.patient_id is not None:
        patient = authorize_patient(db, current_user, payload.patient_id)
    if current_user.role == UserRole.NURSE:
        raise ForbiddenError("Consent is the family's to give.")

    decision = consent_service.record_decision(
        db, user=current_user, kind=payload.kind, granted=payload.granted, patient=patient
    )
    return consent_service.serialize(decision)


@router.get(
    "/privacy/patients/{patient_id}/export",
    summary="Download everything held about this patient",
)
def export(patient_id: int, db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    """The whole record as JSON. Audited — an export is a copy leaving the building."""
    patient = authorize_patient(db, current_user, patient_id)
    return privacy_service.export(db, patient=patient, actor=current_user)


@router.post(
    "/privacy/erasure-requests",
    response_model=ErasureRequestOut,
    status_code=201,
    summary="Ask for a patient's record to be destroyed",
)
def request_erasure(
    payload: ErasureRequestCreate, db: DbSession, current_user: CurrentUser
) -> dict[str, Any]:
    patient = authorize_patient(db, current_user, payload.patient_id)
    if current_user.role == UserRole.NURSE:
        raise ForbiddenError("Only the family or an admin can ask for a record to be erased.")
    request = privacy_service.request_erasure(
        db, patient=patient, actor=current_user, reason=payload.reason
    )
    return privacy_service.serialize_request(request)


@router.get(
    "/erasure-requests",
    response_model=list[ErasureRequestOut],
    summary="Erasure queue (admin)",
)
def list_requests(
    db: DbSession,
    current_user: AdminUser,
    status: ErasureStatus | None = Query(default=None),
) -> list[dict[str, Any]]:
    return [
        privacy_service.serialize_request(request)
        for request in privacy_service.list_requests(db, status=status)
    ]


@router.post(
    "/erasure-requests/{request_id}/execute",
    response_model=ErasureRequestOut,
    summary="Carry out an erasure (admin)",
)
def execute(
    request_id: int, payload: ErasureDecision, db: DbSession, current_user: AdminUser
) -> dict[str, Any]:
    """Irreversible. The family asks; an admin carries it out."""
    request = privacy_service.get_request(db, request_id)
    return privacy_service.serialize_request(
        privacy_service.execute(db, request, actor=current_user, note=payload.note)
    )


@router.post(
    "/erasure-requests/{request_id}/decline",
    response_model=ErasureRequestOut,
    summary="Decline an erasure, with a reason (admin)",
)
def decline(
    request_id: int, payload: ErasureDecision, db: DbSession, current_user: AdminUser
) -> dict[str, Any]:
    request = privacy_service.get_request(db, request_id)
    return privacy_service.serialize_request(
        privacy_service.decline(db, request, actor=current_user, note=payload.note or "")
    )


@router.get(
    "/audit",
    response_model=list[dict],
    summary="Audit log (admin)",
)
def audit_log(
    db: DbSession,
    current_user: AdminUser,
    patient_id: int | None = Query(default=None),
    limit: int = Query(default=100, le=500),
) -> list[dict[str, Any]]:
    return [
        audit_service.serialize(entry)
        for entry in audit_service.list_events(db, patient_id=patient_id, limit=limit)
    ]
