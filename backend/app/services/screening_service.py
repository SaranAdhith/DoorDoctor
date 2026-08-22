"""PHQ-2 screening (§4.7).

PHQ-2 is a **published instrument**, not a DoorDoctor invention. Its two
questions, its four-point answer scale, its 0–6 total and its **cutoff of 3**
come from the instrument and are marked `INSTRUMENT` in `core/clinical.py`.
Reconciling the real §4 must not "correct" them. Only the *cadence* — how often
to screen, and how soon to follow a positive screen up — is `ASSUMED`.

**A positive screen creates a follow-up task and never an alert.** A low mood
score is not a threshold breach, and dressing it as one would be a diagnosis
this platform is not entitled to make. "Positive" here means *screen further*,
which is what the instrument itself says it means.

**Both answers are stored, not only the total.** A 3 made of (3, 0) is not the
same clinical picture as one made of (1, 2), and storing the sum throws that
away permanently.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..core import clinical
from ..core.exceptions import BadRequestError, NotFoundError
from ..database import now
from ..models import Patient, Screening, ScreeningInstrument, TaskKind, User
from . import task_service

logger = logging.getLogger("doordoctor.screenings")

SOURCE_TYPE = "screening"


def instrument_definition() -> dict[str, Any]:
    """The questionnaire as the nurse's screen should render it."""
    return {
        "code": clinical.PHQ2_INSTRUMENT,
        "name": "PHQ-2",
        "preamble": clinical.PHQ2_PREAMBLE,
        "questions": list(clinical.PHQ2_QUESTIONS),
        "answers": [{"value": v, "label": label} for v, label in clinical.PHQ2_ANSWERS],
        "max_total": clinical.PHQ2_MAX_TOTAL,
        "positive_cutoff": clinical.PHQ2_POSITIVE_CUTOFF,
        "cadence_days": clinical.PHQ2_CADENCE_DAYS,
        # Said plainly on the screen, because a screening tool that looks like a
        # diagnosis is how a screening tool does harm.
        "disclaimer": (
            "PHQ-2 is a two-question screen, not a diagnosis. A positive result means "
            "a longer conversation is worth having, and the care team will arrange one."
        ),
    }


def score_answers(answers: list[int]) -> tuple[int, bool]:
    """Total and positivity, straight from the instrument. No database, no clock."""
    if len(answers) != len(clinical.PHQ2_QUESTIONS):
        raise BadRequestError(
            f"PHQ-2 has {len(clinical.PHQ2_QUESTIONS)} questions; "
            f"{len(answers)} answer(s) were given."
        )
    valid = {value for value, _ in clinical.PHQ2_ANSWERS}
    for answer in answers:
        if answer not in valid:
            raise BadRequestError(
                f"Each answer must be one of {sorted(valid)}; got {answer}."
            )
    total = sum(answers)
    return total, total >= clinical.PHQ2_POSITIVE_CUTOFF


def record(
    db: Session,
    *,
    patient: Patient,
    user: User,
    answers: list[int],
    visit_id: int | None = None,
    note: str | None = None,
    as_of: datetime | None = None,
) -> Screening:
    total, positive = score_answers(answers)
    moment = as_of or now()

    screening = Screening(
        patient_id=patient.id,
        instrument=ScreeningInstrument.PHQ2,
        score=total,
        max_score=clinical.PHQ2_MAX_TOTAL,
        positive=positive,
        administered_by=user.id,
        visit_id=visit_id,
        administered_at=moment,
        note=(note or "").strip() or None,
    )
    screening.answers = answers
    db.add(screening)
    db.flush()

    if positive:
        _open_follow_up(db, screening, patient, as_of=moment)

    logger.info(
        "PHQ-2 recorded for patient %s: score=%s positive=%s", patient.id, total, positive
    )
    return screening


def _open_follow_up(db: Session, screening: Screening, patient: Patient, as_of: datetime | None):
    """A task for a human. Never an alert — see the module docstring."""
    existing = task_service.open_for_source(db, SOURCE_TYPE, screening.id)
    if existing is not None:
        return existing
    return task_service.create(
        db,
        patient=patient,
        kind=TaskKind.SCREENING_FOLLOW_UP,
        title=f"Mood follow-up conversation with {patient.name}",
        detail=(
            f"PHQ-2 scored {screening.score} of {screening.max_score}, at or above the "
            f"instrument's cutoff of {clinical.PHQ2_POSITIVE_CUTOFF}. A longer conversation "
            "is indicated. This is a screening result, not a diagnosis."
        ),
        due_in_hours=clinical.PHQ2_FOLLOW_UP_HOURS,
        source_type=SOURCE_TYPE,
        source_id=screening.id,
        assigned_user_id=task_service.assign_to_patients_nurse(db, patient),
        as_of=as_of,
    )


def latest(db: Session, patient_id: int) -> Screening | None:
    return db.scalar(
        select(Screening)
        .where(
            Screening.patient_id == patient_id,
            Screening.instrument == ScreeningInstrument.PHQ2,
        )
        .order_by(Screening.administered_at.desc(), Screening.id.desc())
        .limit(1)
    )


def is_due(db: Session, patient_id: int, as_of: datetime | None = None) -> bool:
    """Cadence is `ASSUMED`. A patient never screened is always due."""
    last = latest(db, patient_id)
    if last is None:
        return True
    moment = as_of or now()
    return last.administered_at <= moment - timedelta(days=clinical.PHQ2_CADENCE_DAYS)


def list_for_patient(db: Session, patient_id: int, limit: int = 24) -> list[Screening]:
    return list(
        db.scalars(
            select(Screening)
            .options(selectinload(Screening.administered_by_user))
            .where(Screening.patient_id == patient_id)
            .order_by(Screening.administered_at.desc(), Screening.id.desc())
            .limit(limit)
        )
    )


def get_for_user(db: Session, user: User, screening_id: int) -> Screening:
    from ..core.dependencies import authorize_patient

    screening = db.get(Screening, screening_id)
    if screening is None:
        raise NotFoundError("Screening not found.")
    try:
        authorize_patient(db, user, screening.patient_id)
    except NotFoundError:
        raise NotFoundError("Screening not found.") from None
    return screening


def serialize(screening: Screening) -> dict[str, Any]:
    return {
        "id": screening.id,
        "patient_id": screening.patient_id,
        "instrument": screening.instrument.value,
        # Both answers, paired with the question each belongs to. A client that
        # only receives the total cannot show what was actually asked.
        "answers": [
            {"question": question, "value": value}
            for question, value in zip(clinical.PHQ2_QUESTIONS, screening.answers)
        ],
        "score": screening.score,
        "max_score": screening.max_score,
        "positive": screening.positive,
        "administered_by": screening.administered_by,
        "administered_by_name": (
            screening.administered_by_user.name if screening.administered_by_user else None
        ),
        "visit_id": screening.visit_id,
        "administered_at": screening.administered_at,
        "note": screening.note,
    }
