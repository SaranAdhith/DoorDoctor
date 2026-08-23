"""Consent decisions (§4.14).

Every decision is a row and nothing is updated in place, so "she withdrew
consent to the assistant in March" survives her granting it again in April. The
current position is the newest row for that kind.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.exceptions import BadRequestError
from ..core.ops import CONSENT_KINDS, CONSENT_KINDS_BY_KEY, CONSENT_POLICY_VERSION
from ..models import AuditAction, Consent, ConsentStatus, Patient, User
from . import audit_service


def record_decision(
    db: Session,
    *,
    user: User,
    kind: str,
    granted: bool,
    patient: Patient | None = None,
    source: str = "privacy_page",
    commit: bool = True,
) -> Consent:
    spec = CONSENT_KINDS_BY_KEY.get(kind)
    if spec is None:
        raise BadRequestError(f"Unknown consent '{kind}'.")
    if spec.required and not granted:
        # Refusing a required consent is not a preference, it is leaving the
        # service. Saying so is more honest than accepting a withdrawal that
        # would have to be ignored by every visit afterwards.
        raise BadRequestError(
            f"{spec.label} is what the service is. To withdraw it, ask DoorDoctor to close the account."
        )

    decision = Consent(
        user_id=user.id,
        patient_id=patient.id if patient else None,
        kind=kind,
        version=CONSENT_POLICY_VERSION,
        status=ConsentStatus.GRANTED if granted else ConsentStatus.WITHDRAWN,
        decided_by=user.id,
        decided_by_name=user.name,
        source=source,
    )
    db.add(decision)
    audit_service.record(
        db,
        actor=user,
        action=AuditAction.CONSENT_GRANTED if granted else AuditAction.CONSENT_WITHDRAWN,
        subject_type="consent",
        subject_id=patient.id if patient else None,
        patient_id=patient.id if patient else None,
        detail=f"{spec.label} — {'granted' if granted else 'withdrawn'} (v{CONSENT_POLICY_VERSION}).",
    )
    if commit:
        db.commit()
        db.refresh(decision)
    else:
        db.flush()
    return decision


def history(db: Session, *, user_id: int, patient_id: int | None = None) -> list[Consent]:
    query = select(Consent).where(Consent.user_id == user_id)
    if patient_id is not None:
        query = query.where(Consent.patient_id == patient_id)
    return list(db.scalars(query.order_by(Consent.decided_at.desc(), Consent.id.desc())))


def current(db: Session, *, user_id: int, patient_id: int | None = None) -> dict[str, Consent]:
    """The newest decision per kind. Older rows stay; they are the history."""
    latest: dict[str, Consent] = {}
    for decision in reversed(history(db, user_id=user_id, patient_id=patient_id)):
        latest[decision.kind] = decision
    return latest


def is_granted(db: Session, *, user_id: int, kind: str, patient_id: int | None = None) -> bool:
    decision = current(db, user_id=user_id, patient_id=patient_id).get(kind)
    return decision is not None and decision.status == ConsentStatus.GRANTED


def summary(db: Session, *, user_id: int, patient_id: int | None = None) -> list[dict[str, Any]]:
    """Every consent this platform asks for, with where it currently stands.

    Built from `CONSENT_KINDS` rather than from the rows, so a consent that has
    never been decided appears as undecided instead of being silently absent.
    """
    latest = current(db, user_id=user_id, patient_id=patient_id)
    rows: list[dict[str, Any]] = []
    for spec in CONSENT_KINDS:
        decision = latest.get(spec.key)
        rows.append(
            {
                "kind": spec.key,
                "label": spec.label,
                "blurb": spec.blurb,
                "required": spec.required,
                "status": decision.status.value if decision else None,
                "granted": bool(decision and decision.status == ConsentStatus.GRANTED),
                "decided_at": decision.decided_at if decision else None,
                "decided_by_name": decision.decided_by_name if decision else None,
                "version": decision.version if decision else None,
                "current_version": CONSENT_POLICY_VERSION,
                # A consent given against an older policy is still a consent; it
                # is flagged so the family can be asked again rather than having
                # their old answer silently reinterpreted as agreement to a
                # document they never saw.
                "needs_review": bool(decision and decision.version != CONSENT_POLICY_VERSION),
            }
        )
    return rows


def serialize(decision: Consent) -> dict[str, Any]:
    return {
        "id": decision.id,
        "kind": decision.kind,
        "label": CONSENT_KINDS_BY_KEY[decision.kind].label
        if decision.kind in CONSENT_KINDS_BY_KEY
        else decision.kind,
        "version": decision.version,
        "status": decision.status.value,
        "decided_at": decision.decided_at,
        "decided_by_name": decision.decided_by_name,
        "source": decision.source,
    }
