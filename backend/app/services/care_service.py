"""Care managers, caseloads and interactions (§4.4).

RECORDED: a care manager runs **1:20 shared** or **1:10 dedicated**. Those two
numbers live in `core/pricing.py` beside the entitlement that decides which kind
a plan grants, and are enforced here — a caseload past capacity is refused with
the count in the message.

**A care manager is a profile on an admin user, not a fourth `UserRole`** —
decided with the founder on 2026-08-22. `core/dependencies.py` is untouched, the
three-way route guard survives, and no existing authorization test changes.

Which kind of manager a patient is entitled to comes from
`subscription_service.entitlement(sub, CARE_MANAGER)`. Nothing here reads a plan
code, exactly as Phase 4 built it to.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..core import pricing
from ..core.exceptions import BadRequestError, ConflictError, NotFoundError
from ..database import now
from ..models import (
    CareAssignment,
    CareChannel,
    CareDirection,
    CareInteraction,
    CareManager,
    CareManagerKind,
    Patient,
    Subscription,
    User,
    UserRole,
)
from . import subscription_service

logger = logging.getLogger("doordoctor.care")

# The recorded ratios, read from `pricing.py` rather than restated.
CAPACITY_BY_KIND: dict[CareManagerKind, int] = {
    CareManagerKind.SHARED: pricing.RATIO_SHARED,
    CareManagerKind.DEDICATED: pricing.RATIO_DEDICATED,
}


# --------------------------------------------------------------------------
# Managers
# --------------------------------------------------------------------------


def create_manager(
    db: Session,
    *,
    user: User,
    kind: CareManagerKind,
    languages: str = "",
    capacity: int | None = None,
) -> CareManager:
    """Turn an admin account into a care manager.

    Refuses a non-admin: the whole reason this is a profile rather than a role
    is that a care manager *is* an admin, and letting a nurse hold one would
    quietly create the fourth role the design avoids.
    """
    if user.role != UserRole.ADMIN:
        raise BadRequestError("A care manager profile belongs to an admin account.")

    existing = db.scalar(select(CareManager).where(CareManager.user_id == user.id))
    if existing is not None:
        raise ConflictError(f"{user.name} is already a care manager.")

    manager = CareManager(
        user_id=user.id,
        kind=kind,
        # Defaulted from the recorded ratio, but stored, so one manager can be
        # given a reduced caseload without changing what the plan promises
        # everybody else.
        capacity=capacity if capacity is not None else CAPACITY_BY_KIND[kind],
        languages=languages,
    )
    db.add(manager)
    db.flush()
    return manager


def caseload(db: Session, manager_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(CareAssignment.id)).where(
                CareAssignment.care_manager_id == manager_id,
                CareAssignment.ended_at.is_(None),
            )
        )
        or 0
    )


def list_managers(db: Session, kind: CareManagerKind | None = None) -> list[CareManager]:
    query = select(CareManager).options(selectinload(CareManager.user))
    if kind is not None:
        query = query.where(CareManager.kind == kind)
    return list(db.scalars(query.order_by(CareManager.id)))


def get_manager(db: Session, manager_id: int) -> CareManager:
    manager = db.scalar(
        select(CareManager)
        .options(selectinload(CareManager.user))
        .where(CareManager.id == manager_id)
    )
    if manager is None:
        raise NotFoundError("Care manager not found.")
    return manager


# --------------------------------------------------------------------------
# Entitlement — which kind this patient's plan grants
# --------------------------------------------------------------------------


def _subscription_for(db: Session, patient: Patient) -> Subscription | None:
    return db.scalar(
        select(Subscription)
        .options(selectinload(Subscription.plan))
        .where(Subscription.family_user_id == patient.family_user_id)
        .order_by(Subscription.id.desc())
        .limit(1)
    )


def entitled_kind(db: Session, patient: Patient) -> CareManagerKind | None:
    """What the plan grants, read as data. Never `if plan.code == "premium"`."""
    subscription = _subscription_for(db, patient)
    if subscription is None:
        return None
    value = subscription_service.entitlement(subscription, pricing.CARE_MANAGER)
    if not value:
        return None
    try:
        return CareManagerKind(str(value))
    except ValueError:  # pragma: no cover - an unknown entitlement value
        logger.warning("Unrecognised care_manager entitlement %r", value)
        return None


# --------------------------------------------------------------------------
# Assignment
# --------------------------------------------------------------------------


def current_assignment(db: Session, patient_id: int) -> CareAssignment | None:
    return db.scalar(
        select(CareAssignment)
        .options(
            selectinload(CareAssignment.care_manager).selectinload(CareManager.user)
        )
        .where(CareAssignment.patient_id == patient_id, CareAssignment.ended_at.is_(None))
        .order_by(CareAssignment.id.desc())
        .limit(1)
    )


def assign(
    db: Session, *, patient: Patient, manager: CareManager, as_of: datetime | None = None
) -> CareAssignment:
    """Put a patient on a manager's caseload, honouring the recorded ratio.

    One active assignment per patient is enforced here rather than by a unique
    constraint: `ended_at IS NULL` partial indexes are not portable to SQLite,
    and a constraint that only exists on Postgres is one nobody can rely on.
    """
    if not manager.active:
        raise BadRequestError(f"{manager.user.name} is not taking new patients.")

    load = caseload(db, manager.id)
    if load >= manager.capacity:
        raise ConflictError(
            f"{manager.user.name} is at capacity ({load} of {manager.capacity} patients). "
            "Choose another care manager."
        )

    moment = as_of or now()
    existing = current_assignment(db, patient.id)
    if existing is not None:
        if existing.care_manager_id == manager.id:
            return existing
        end(db, existing, reason="Reassigned", as_of=moment)

    assignment = CareAssignment(
        patient_id=patient.id, care_manager_id=manager.id, assigned_at=moment
    )
    db.add(assignment)
    db.flush()
    logger.info("Patient %s assigned to care manager %s", patient.id, manager.id)
    return assignment


def end(
    db: Session, assignment: CareAssignment, reason: str | None = None, as_of: datetime | None = None
) -> CareAssignment:
    """Close an assignment. Never deleted — a handover is history."""
    if assignment.ended_at is not None:
        raise BadRequestError("This assignment has already ended.")
    assignment.ended_at = as_of or now()
    assignment.ended_reason = (reason or "").strip() or None
    db.flush()
    return assignment


def auto_assign(
    db: Session, patient: Patient, as_of: datetime | None = None
) -> CareAssignment | None:
    """Give the patient the least-loaded manager of the kind their plan grants.

    Returns None rather than raising when the plan grants none or everyone of
    that kind is full: onboarding a patient must not fail because the roster is
    stretched. An unassigned patient is visible on the admin screen; a patient
    who could not be created is not.
    """
    kind = entitled_kind(db, patient)
    if kind is None:
        return None

    candidates = [m for m in list_managers(db, kind=kind) if m.active]
    open_managers = [(caseload(db, m.id), m.id, m) for m in candidates]
    open_managers = [row for row in open_managers if row[0] < row[2].capacity]
    if not open_managers:
        return None

    # Sorted by id as the tie-break, so a fixed-seed run assigns deterministically.
    open_managers.sort(key=lambda row: (row[0], row[1]))
    return assign(db, patient=patient, manager=open_managers[0][2], as_of=as_of)


# --------------------------------------------------------------------------
# Interactions
# --------------------------------------------------------------------------


def log_interaction(
    db: Session,
    *,
    patient: Patient,
    user: User,
    channel: CareChannel,
    subject: str,
    note: str = "",
    direction: CareDirection = CareDirection.OUTBOUND,
    minutes: int | None = None,
    occurred_at: datetime | None = None,
    visible_to_family: bool = True,
) -> CareInteraction:
    assignment = current_assignment(db, patient.id)
    interaction = CareInteraction(
        patient_id=patient.id,
        care_manager_id=assignment.care_manager_id if assignment else None,
        logged_by=user.id,
        channel=channel,
        direction=direction,
        subject=subject.strip(),
        note=(note or "").strip(),
        minutes=minutes,
        occurred_at=occurred_at or now(),
        visible_to_family=visible_to_family,
    )
    db.add(interaction)
    db.flush()
    return interaction


def list_interactions(
    db: Session, patient_id: int, *, for_family: bool, limit: int = 50
) -> list[CareInteraction]:
    """A family sees what was done for them; an admin also sees handover notes."""
    query = (
        select(CareInteraction)
        .options(
            selectinload(CareInteraction.care_manager).selectinload(CareManager.user)
        )
        .where(CareInteraction.patient_id == patient_id)
    )
    if for_family:
        query = query.where(CareInteraction.visible_to_family.is_(True))
    return list(
        db.scalars(
            query.order_by(CareInteraction.occurred_at.desc(), CareInteraction.id.desc()).limit(limit)
        )
    )


# --------------------------------------------------------------------------
# Serialization
# --------------------------------------------------------------------------


def serialize_manager(db: Session, manager: CareManager) -> dict[str, Any]:
    load = caseload(db, manager.id)
    return {
        "id": manager.id,
        "user_id": manager.user_id,
        "name": manager.user.name if manager.user else "Unknown",
        "email": manager.user.email if manager.user else None,
        "phone": manager.user.phone if manager.user else None,
        "kind": manager.kind.value,
        "capacity": manager.capacity,
        "caseload": load,
        "available": max(0, manager.capacity - load),
        "at_capacity": load >= manager.capacity,
        "languages": manager.languages,
        "active": manager.active,
    }


def serialize_assignment(assignment: CareAssignment) -> dict[str, Any]:
    manager = assignment.care_manager
    return {
        "id": assignment.id,
        "patient_id": assignment.patient_id,
        "care_manager_id": assignment.care_manager_id,
        "care_manager_name": manager.user.name if manager and manager.user else None,
        "care_manager_kind": manager.kind.value if manager else None,
        "languages": manager.languages if manager else None,
        "assigned_at": assignment.assigned_at,
        "ended_at": assignment.ended_at,
        "ended_reason": assignment.ended_reason,
    }


def serialize_interaction(interaction: CareInteraction) -> dict[str, Any]:
    manager = interaction.care_manager
    return {
        "id": interaction.id,
        "patient_id": interaction.patient_id,
        "care_manager_id": interaction.care_manager_id,
        "care_manager_name": manager.user.name if manager and manager.user else None,
        "channel": interaction.channel.value,
        "direction": interaction.direction.value,
        "subject": interaction.subject,
        "note": interaction.note,
        "minutes": interaction.minutes,
        "occurred_at": interaction.occurred_at,
        "visible_to_family": interaction.visible_to_family,
    }
