"""The care circle: who is around this patient, and who should be told (§4.13).

One rule shapes the whole module: **a circle member who cannot be reached is not
told they will be.** `receives_alerts` on a row with no phone and no email is a
promise the platform cannot keep, so setting it is refused at the boundary
rather than discovered at 2am by a family who thought their uncle had been
called.

The primary member mirrors `Patient.family_user_id` and cannot be removed —
Phase 11 migrates authorization onto this table and needs to know who was first.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.exceptions import BadRequestError, ConflictError, NotFoundError
from ..core.ops import CARE_CIRCLE_MAX_MEMBERS
from ..models import AuditAction, CareCircleMember, CareCircleRole, Patient, User
from . import audit_service


def list_members(db: Session, patient_id: int) -> list[CareCircleMember]:
    return list(
        db.scalars(
            select(CareCircleMember)
            .where(CareCircleMember.patient_id == patient_id)
            .order_by(CareCircleMember.is_primary.desc(), CareCircleMember.id)
        )
    )


def ensure_primary(db: Session, patient: Patient) -> CareCircleMember:
    """The patient's family user, as a circle member. Idempotent."""
    existing = db.scalar(
        select(CareCircleMember).where(
            CareCircleMember.patient_id == patient.id, CareCircleMember.is_primary.is_(True)
        )
    )
    if existing is not None:
        return existing

    family = db.get(User, patient.family_user_id)
    member = CareCircleMember(
        patient_id=patient.id,
        user_id=patient.family_user_id,
        name=family.name if family else "Primary contact",
        relationship_label="Primary contact",
        phone=family.phone if family else None,
        email=family.email if family else None,
        role=CareCircleRole.PRIMARY,
        is_primary=True,
        receives_alerts=True,
        receives_reports=True,
    )
    db.add(member)
    db.flush()
    return member


def add_member(
    db: Session,
    patient: Patient,
    *,
    actor: User,
    name: str,
    relationship_label: str,
    phone: str | None = None,
    email: str | None = None,
    role: CareCircleRole = CareCircleRole.VIEWER,
    receives_alerts: bool = False,
    receives_reports: bool = False,
    note: str | None = None,
) -> CareCircleMember:
    members = list_members(db, patient.id)
    if len(members) >= CARE_CIRCLE_MAX_MEMBERS:
        raise ConflictError(
            f"A care circle holds at most {CARE_CIRCLE_MAX_MEMBERS} people. "
            "Remove someone before adding another."
        )

    email = (email or "").strip().lower() or None
    phone = (phone or "").strip() or None
    if email and any(member.email == email for member in members):
        raise ConflictError("Somebody with that email address is already in the circle.")
    _check_reachable(phone, email, receives_alerts, receives_reports)

    member = CareCircleMember(
        patient_id=patient.id,
        name=name.strip(),
        relationship_label=relationship_label.strip() or "Family",
        phone=phone,
        email=email,
        role=role,
        is_primary=False,
        receives_alerts=receives_alerts,
        receives_reports=receives_reports,
        note=(note or "").strip() or None,
        created_by=actor.id,
    )
    db.add(member)
    _audit(db, actor, patient, f"Added {member.name} ({member.relationship_label}).")
    db.commit()
    db.refresh(member)
    return member


def update_member(
    db: Session, member: CareCircleMember, *, actor: User, **fields: Any
) -> CareCircleMember:
    if "email" in fields and fields["email"] is not None:
        fields["email"] = fields["email"].strip().lower() or None
    for key, value in fields.items():
        setattr(member, key, value)

    _check_reachable(member.phone, member.email, member.receives_alerts, member.receives_reports)

    patient = db.get(Patient, member.patient_id)
    _audit(db, actor, patient, f"Updated {member.name} in the care circle.")
    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, member: CareCircleMember, *, actor: User) -> None:
    if member.is_primary:
        raise BadRequestError(
            "The primary contact cannot be removed from the care circle. "
            "Change who the primary contact is instead."
        )
    patient = db.get(Patient, member.patient_id)
    name = member.name
    db.delete(member)
    _audit(db, actor, patient, f"Removed {name} from the care circle.")
    db.commit()


def get_member(db: Session, member_id: int) -> CareCircleMember:
    member = db.get(CareCircleMember, member_id)
    if member is None:
        raise NotFoundError("Care circle member not found.")
    return member


def alert_recipients(db: Session, patient_id: int) -> list[CareCircleMember]:
    """Everyone in the circle who asked to hear about alerts and can be reached.

    Used by the notification routing. Members with no contact details are
    excluded here rather than being handed to a channel that will fail — but the
    boundary above refuses to create one of those in the first place, so this is
    a safety net for rows written before the rule existed.
    """
    return [
        member
        for member in list_members(db, patient_id)
        if member.receives_alerts and member.is_reachable
    ]


def report_recipients(db: Session, patient_id: int) -> list[CareCircleMember]:
    return [
        member
        for member in list_members(db, patient_id)
        if member.receives_reports and member.is_reachable
    ]


def _check_reachable(
    phone: str | None, email: str | None, receives_alerts: bool, receives_reports: bool
) -> None:
    if (receives_alerts or receives_reports) and not (phone or email):
        raise BadRequestError(
            "Add a phone number or an email address before choosing to send this person messages."
        )


def _audit(db: Session, actor: User, patient: Patient | None, detail: str) -> None:
    audit_service.record(
        db,
        actor=actor,
        action=AuditAction.CARE_CIRCLE_CHANGED,
        subject_type="care_circle",
        subject_id=patient.id if patient else None,
        patient_id=patient.id if patient else None,
        detail=detail,
    )


def serialize(member: CareCircleMember, *, include_contact: bool = True) -> dict[str, Any]:
    """`include_contact=False` is what a nurse sees of somebody else's circle.

    A nurse needs to know who to call in an emergency, which is the primary
    contact and anyone marked as an emergency contact. The rest of the circle's
    phone numbers are not theirs to carry around on a shared device.
    """
    data: dict[str, Any] = {
        "id": member.id,
        "patient_id": member.patient_id,
        "user_id": member.user_id,
        "name": member.name,
        "relationship_label": member.relationship_label,
        "role": member.role.value,
        "is_primary": member.is_primary,
        "receives_alerts": member.receives_alerts,
        "receives_reports": member.receives_reports,
        "has_login": member.user_id is not None,
        "note": member.note,
    }
    if include_contact:
        data["phone"] = member.phone
        data["email"] = member.email
    else:
        data["phone"] = None
        data["email"] = None
    return data
