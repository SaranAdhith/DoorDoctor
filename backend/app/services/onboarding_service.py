"""Getting a new family set up (§4.15).

**A step is complete because the thing is true, not because somebody clicked.**
Four of the five steps are derived from the tables that would carry the result —
consents, thresholds, the care circle, notification preferences — so the
checklist cannot drift away from what it describes. Only "check your relative's
details" is stored, because acknowledging that they are correct leaves no other
trace.

The practical consequence is worth stating: if a family removes everyone from
their care circle, that step goes back to incomplete. That is the checklist
being honest rather than the checklist being broken.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.exceptions import BadRequestError
from ..core.ops import CONSENT_KINDS, ONBOARDING_STEPS, ONBOARDING_STEPS_BY_KEY
from ..models import (
    CareCircleMember,
    NotificationPreference,
    OnboardingProgress,
    Patient,
    PatientThreshold,
    User,
)
from . import consent_service

#: The only step with nothing else to prove it.
ACKNOWLEDGED_STEPS = frozenset({"confirm_patient"})


def _acknowledged(db: Session, user: User, patient: Patient) -> set[str]:
    return {
        row.step
        for row in db.scalars(
            select(OnboardingProgress).where(
                OnboardingProgress.user_id == user.id,
                OnboardingProgress.patient_id == patient.id,
            )
        )
    }


def _is_done(db: Session, user: User, patient: Patient, key: str, acknowledged: set[str]) -> bool:
    if key in ACKNOWLEDGED_STEPS:
        return key in acknowledged

    if key == "consent":
        current = consent_service.current(db, user_id=user.id, patient_id=patient.id)
        return all(
            spec.key in current and current[spec.key].status.value == "granted"
            for spec in CONSENT_KINDS
            if spec.required
        )
    if key == "thresholds":
        return (
            db.scalar(
                select(PatientThreshold.id).where(PatientThreshold.patient_id == patient.id).limit(1)
            )
            is not None
        )
    if key == "care_circle":
        # More than the primary member: the primary is created automatically and
        # its existence proves nothing about whether the family did anything.
        return (
            db.scalar(
                select(CareCircleMember.id)
                .where(
                    CareCircleMember.patient_id == patient.id,
                    CareCircleMember.is_primary.is_(False),
                )
                .limit(1)
            )
            is not None
        )
    if key == "notifications":
        return (
            db.scalar(
                select(NotificationPreference.id)
                .where(NotificationPreference.user_id == user.id)
                .limit(1)
            )
            is not None
        )
    return key in acknowledged  # pragma: no cover - future steps default to a tick


def progress(db: Session, user: User, patient: Patient) -> dict[str, Any]:
    acknowledged = _acknowledged(db, user, patient)
    steps: list[dict[str, Any]] = []
    for spec in ONBOARDING_STEPS:
        done = _is_done(db, user, patient, spec.key, acknowledged)
        steps.append(
            {
                "key": spec.key,
                "label": spec.label,
                "blurb": spec.blurb,
                "path": spec.path,
                "done": done,
                "derived": spec.key not in ACKNOWLEDGED_STEPS,
            }
        )

    completed = sum(1 for step in steps if step["done"])
    return {
        "patient_id": patient.id,
        "steps": steps,
        "completed": completed,
        "total": len(steps),
        "complete": completed == len(steps),
        "next_step": next((step for step in steps if not step["done"]), None),
    }


def acknowledge(db: Session, user: User, patient: Patient, step: str) -> dict[str, Any]:
    """Mark an acknowledgement step done. Derived steps refuse to be ticked."""
    if step not in ONBOARDING_STEPS_BY_KEY:
        raise BadRequestError(f"Unknown onboarding step '{step}'.")
    if step not in ACKNOWLEDGED_STEPS:
        spec = ONBOARDING_STEPS_BY_KEY[step]
        raise BadRequestError(
            f"'{spec.label}' completes itself once the work is done — there is nothing to tick."
        )

    existing = db.scalar(
        select(OnboardingProgress).where(
            OnboardingProgress.user_id == user.id,
            OnboardingProgress.patient_id == patient.id,
            OnboardingProgress.step == step,
        )
    )
    if existing is None:
        db.add(OnboardingProgress(user_id=user.id, patient_id=patient.id, step=step))
        db.commit()
    return progress(db, user, patient)
