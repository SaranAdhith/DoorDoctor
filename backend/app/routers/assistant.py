"""The AI assistant (§2.3).

Every route here depends on `FamilyOrAdminUser`. **Nurses do not get an
assistant** — that was decided explicitly with the founder rather than left to
fall out of a missing check, and a test asserts the 403. A nurse assistant is a
real feature with its own context pack and its own intents, and it belongs with
Phase 10's nurse operations screens.
"""

from typing import Any

from fastapi import APIRouter, Query

from ..core.dependencies import DbSession, FamilyOrAdminUser, authorize_patient
from ..models import UserRole
from ..schemas.assistant import (
    AssistantAnswerOut,
    AssistantAskRequest,
    AssistantMessageOut,
    AssistantSuggestionOut,
)
from ..services import assistant_context, assistant_service

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/ask", response_model=AssistantAnswerOut, summary="Ask the assistant a question")
def ask(
    payload: AssistantAskRequest,
    current_user: FamilyOrAdminUser,
    db: DbSession,
) -> dict[str, Any]:
    """Answer one question, from a role-scoped context pack and nothing else.

    The patient is resolved **here**, through `authorize_patient`, so someone
    else's patient is a **404** before any context is assembled — a 403 would
    confirm the record exists, which is enough to learn that a named person is a
    DoorDoctor patient.

    Metered at 30 questions per user per hour, raising 429 with `Retry-After`.
    """
    patient = None
    if payload.patient_id is not None and current_user.role != UserRole.ADMIN:
        patient = authorize_patient(db, current_user, payload.patient_id)

    return assistant_service.ask(db, current_user, payload.question, patient)


@router.get(
    "/conversations",
    response_model=list[AssistantMessageOut],
    summary="Your own assistant history",
)
def conversations(
    current_user: FamilyOrAdminUser,
    db: DbSession,
    limit: int = Query(default=assistant_service.MAX_HISTORY, ge=1, le=assistant_service.MAX_HISTORY),
) -> list[dict[str, Any]]:
    """The caller's own exchanges, newest first.

    **Only ever the caller's own.** An admin does not read a family member's
    questions about their mother from this route or any other — see the retention
    note in `models/assistant.py`.
    """
    return [assistant_service.serialize(m) for m in assistant_service.history(db, current_user, limit)]


@router.get(
    "/suggestions",
    response_model=list[AssistantSuggestionOut],
    summary="Starter questions for this caller",
)
def suggestions(
    current_user: FamilyOrAdminUser,
    db: DbSession,
    patient_id: int | None = None,
) -> list[dict[str, Any]]:
    """Role-scoped starter questions.

    Patient-scoped suggestions are withheld from a family member with nobody
    linked yet — a chip that can only disappoint is worse than no chip.
    """
    if current_user.role == UserRole.ADMIN:
        has_patient = True
    elif patient_id is not None:
        authorize_patient(db, current_user, patient_id)
        has_patient = True
    else:
        has_patient = assistant_context.primary_patient(db, current_user) is not None

    return [
        {"intent": intent.id, "title": intent.title, "question": intent.suggestion}
        for intent in assistant_service.suggestions(current_user, has_patient=has_patient)
    ]
