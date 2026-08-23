"""Nurse profiles, credentials, and the two very different views of them.

§4.10 asks for credential transparency and a family-facing nurse profile. The
two projections live side by side in this one file **so the difference between
them is visible in one screen of code** — a family and an admin are not looking
at the same person's record, and splitting the projections across two modules is
how a registration number ends up on a family's phone.

| | admin sees | family sees |
|---|---|---|
| Name, photo, credential kind, issuing body, verified-on | yes | yes |
| Registration number, personal phone, email | yes | **no** |
| Every patient they cover | yes | **no** — only visits to *this* patient |
| Unverified and rejected credentials | yes | **no** — an unverified claim is not a claim |
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..core.exceptions import BadRequestError, NotFoundError
from ..database import now
from ..models import (
    AuditAction,
    CredentialKind,
    Nurse,
    NurseCredential,
    NurseStatus,
    User,
    VerificationStatus,
    Visit,
    VisitStatus,
)
from . import audit_service


def get_nurse(db: Session, nurse_id: int) -> Nurse:
    nurse = db.scalar(
        select(Nurse)
        .options(selectinload(Nurse.user), selectinload(Nurse.credentials))
        .where(Nurse.id == nurse_id)
    )
    if nurse is None:
        raise NotFoundError("Nurse not found.")
    return nurse


# --- credentials ----------------------------------------------------------


def add_credential(
    db: Session,
    nurse: Nurse,
    *,
    kind: CredentialKind,
    title: str,
    issuing_body: str,
    registration_number: str | None = None,
    issued_on: date | None = None,
    expires_on: date | None = None,
) -> NurseCredential:
    """Record a claim. It starts `pending` — recording is not verifying."""
    credential = NurseCredential(
        nurse_id=nurse.id,
        kind=kind,
        title=title.strip(),
        issuing_body=issuing_body.strip(),
        registration_number=(registration_number or "").strip() or None,
        issued_on=issued_on,
        expires_on=expires_on,
        verification_status=VerificationStatus.PENDING,
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return credential


def verify_credential(
    db: Session, credential: NurseCredential, *, verifier: User, note: str | None = None
) -> NurseCredential:
    """Mark a credential verified, and leave the verifier's name on it.

    The verifier's name is denormalised deliberately. A family reading "verified
    by Priya Raghavan on 12 March" a year after Priya has left must still see
    that sentence; a join to a deleted account would leave it blank.
    """
    if credential.is_expired(now().date()):
        raise BadRequestError("This credential has already expired and cannot be verified.")

    credential.verification_status = VerificationStatus.VERIFIED
    credential.verified_by = verifier.id
    credential.verified_by_name = verifier.name
    credential.verified_at = now()
    credential.note = (note or "").strip() or None

    _sync_nurse_status(db, credential.nurse_id)
    audit_service.record(
        db,
        actor=verifier,
        action=AuditAction.CREDENTIAL_VERIFIED,
        subject_type="nurse_credential",
        subject_id=credential.id,
        detail=f"Verified {credential.title} ({credential.issuing_body}).",
    )
    db.commit()
    db.refresh(credential)
    return credential


def reject_credential(
    db: Session, credential: NurseCredential, *, verifier: User, note: str | None = None
) -> NurseCredential:
    credential.verification_status = VerificationStatus.REJECTED
    credential.verified_by = verifier.id
    credential.verified_by_name = verifier.name
    credential.verified_at = now()
    credential.note = (note or "").strip() or None

    _sync_nurse_status(db, credential.nurse_id)
    audit_service.record(
        db,
        actor=verifier,
        action=AuditAction.CREDENTIAL_REJECTED,
        subject_type="nurse_credential",
        subject_id=credential.id,
        detail=f"Rejected {credential.title} ({credential.issuing_body}).",
    )
    db.commit()
    db.refresh(credential)
    return credential


def _sync_nurse_status(db: Session, nurse_id: int) -> None:
    """A nurse is verified when their registration is.

    The `Nurse.verification_status` column predates this phase and the rest of
    the app reads it. Rather than leave two sources of the same fact to drift,
    it is derived from the registration credential every time one changes.
    """
    nurse = db.get(Nurse, nurse_id)
    if nurse is None:  # pragma: no cover - defensive
        return
    registrations = [
        c for c in nurse.credentials if c.kind == CredentialKind.NURSING_REGISTRATION
    ]
    if any(c.is_verified and not c.is_expired(now().date()) for c in registrations):
        nurse.verification_status = VerificationStatus.VERIFIED
    elif registrations and all(
        c.verification_status == VerificationStatus.REJECTED for c in registrations
    ):
        nurse.verification_status = VerificationStatus.REJECTED
    else:
        nurse.verification_status = VerificationStatus.PENDING


# --- projections ----------------------------------------------------------


def _credential_public(credential: NurseCredential, today: date) -> dict[str, Any]:
    """What a family may see. No registration number, ever."""
    return {
        "id": credential.id,
        "kind": credential.kind.value,
        "title": credential.title,
        "issuing_body": credential.issuing_body,
        "verified_at": credential.verified_at,
        "verified_by_name": credential.verified_by_name,
        "expires_on": credential.expires_on,
        "expired": credential.is_expired(today),
    }


def _credential_admin(credential: NurseCredential, today: date) -> dict[str, Any]:
    data = _credential_public(credential, today)
    data.update(
        {
            "registration_number": credential.registration_number,
            "issued_on": credential.issued_on,
            "verification_status": credential.verification_status.value,
            "note": credential.note,
        }
    )
    return data


def family_profile(db: Session, nurse: Nurse, *, patient_id: int) -> dict[str, Any]:
    """The nurse as their patient's family is entitled to see them.

    Visit counts are scoped to **this patient**. A family learning that their
    nurse has completed 240 visits this quarter learns something about twenty
    other households, and they are not entitled to that.

    Only verified credentials appear. A pending claim is a claim, and showing it
    would invite the reader to treat it as checked.
    """
    today = now().date()
    completed, last_visit = db.execute(
        select(func.count(Visit.id), func.max(Visit.scheduled_at)).where(
            Visit.nurse_id == nurse.id,
            Visit.patient_id == patient_id,
            Visit.status == VisitStatus.COMPLETED,
        )
    ).one()

    return {
        "id": nurse.id,
        "name": nurse.user.name if nurse.user else "",
        "credential": nurse.credential,
        "verification_status": nurse.verification_status.value,
        "status": nurse.status.value,
        "zone": nurse.zone,
        "joined_on": nurse.joined_on,
        "years_experience": nurse.years_experience,
        "languages": [part.strip() for part in (nurse.languages or "").split(",") if part.strip()],
        "bio": nurse.bio,
        "credentials": [
            _credential_public(c, today) for c in nurse.credentials if c.is_verified
        ],
        "visits_to_this_patient": int(completed or 0),
        "last_visit_at": last_visit,
    }


def admin_profile(db: Session, nurse: Nurse) -> dict[str, Any]:
    """The full record, including what is pending and what was rejected."""
    today = now().date()
    open_visits = (
        db.scalar(
            select(func.count(Visit.id)).where(
                Visit.nurse_id == nurse.id,
                Visit.status.in_([VisitStatus.SCHEDULED, VisitStatus.IN_PROGRESS]),
            )
        )
        or 0
    )
    completed = (
        db.scalar(
            select(func.count(Visit.id)).where(
                Visit.nurse_id == nurse.id, Visit.status == VisitStatus.COMPLETED
            )
        )
        or 0
    )
    patients = (
        db.scalar(
            select(func.count(func.distinct(Visit.patient_id))).where(Visit.nurse_id == nurse.id)
        )
        or 0
    )

    return {
        "id": nurse.id,
        "user_id": nurse.user_id,
        "name": nurse.user.name if nurse.user else "",
        "email": nurse.user.email if nurse.user else "",
        "phone": nurse.user.phone if nurse.user else None,
        "credential": nurse.credential,
        "verification_status": nurse.verification_status.value,
        "status": nurse.status.value,
        "zone": nurse.zone,
        "joined_on": nurse.joined_on,
        "years_experience": nurse.years_experience,
        "languages": [part.strip() for part in (nurse.languages or "").split(",") if part.strip()],
        "bio": nurse.bio,
        "credentials": [_credential_admin(c, today) for c in nurse.credentials],
        "open_visits": int(open_visits),
        "completed_visits": int(completed),
        "patients_covered": int(patients),
        "expiring_credentials": [
            _credential_admin(c, today) for c in nurse.credentials if c.is_expired(today)
        ],
    }


def list_for_admin(db: Session) -> list[dict[str, Any]]:
    nurses = db.scalars(
        select(Nurse)
        .options(selectinload(Nurse.user), selectinload(Nurse.credentials))
        .order_by(Nurse.id)
    ).all()
    return [admin_profile(db, nurse) for nurse in nurses]


def set_status(db: Session, nurse: Nurse, status: NurseStatus) -> Nurse:
    nurse.status = status
    db.commit()
    db.refresh(nurse)
    return nurse
