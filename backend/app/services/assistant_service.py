"""The assistant's orchestration (§2.3).

One request walks a fixed path, and the order is the design:

1. **Rate limit.** An LLM endpoint behind a login is metered or it is a bill.
2. **Match the intent** deterministically.
3. **Emergency short-circuits here** — before a pack is built, before a model is
   considered. `assistant_fallback.EMERGENCY_ANSWER` is returned verbatim.
4. **Build the role-scoped context pack.** This is where authorization happened;
   see `assistant_context`.
5. **Compose the deterministic answer.** This is the product, and it is what
   ships with no API key.
6. **Optionally ask the model to answer better**, from the pack and nothing else,
   behind four gates. Any doubt at all falls back to step 5, silently.
7. **Persist the exchange** for the asker, and only the asker.

The gates live here rather than in `llm_client` for the reason Phase 6 wrote
down: the client is transport and the service owns meaning. There is exactly one
LLM client in this codebase and this module does not add a second.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..core.ratelimit import ASSISTANT_PER_USER, limiter
from ..models import AssistantMessage, AssistantSource, Patient, User, UserRole
from . import (
    assistant_context,
    assistant_fallback,
    assistant_intents,
    llm_client,
    summary_service,
)
from .assistant_context import ContextPack
from .assistant_fallback import Answer

logger = logging.getLogger("doordoctor.assistant")

MAX_HISTORY: Final = 50
MIN_ANSWER_CHARS: Final = 20
MAX_ANSWER_CHARS: Final = 1400
"""An answer longer than this is a model that has stopped answering the question.
The deterministic answers run 60–600 characters."""


# --------------------------------------------------------------------------
# The prompt
# --------------------------------------------------------------------------

SYSTEM_PROMPT: Final = """\
You are the DoorDoctor assistant. DoorDoctor is a home healthcare service in \
India: nurses visit elderly people at home, record their health readings and \
their medicines, and families follow along.

You will be given CONTEXT — everything you are allowed to know — and a QUESTION.

Rules, all of them absolute:
- Answer ONLY from the CONTEXT. If the CONTEXT does not contain the answer, say \
plainly that you do not have that information and suggest what you can answer.
- Never state a number that does not appear in the CONTEXT. Never estimate, \
never round, never infer a number.
- Never diagnose, never give medical advice, never suggest starting, stopping or \
changing any medication.
- If the person seems to be describing an emergency, tell them to call 108 \
immediately, then their nurse, then the DoorDoctor care team.
- Warm, calm, direct. Short sentences. Answer the question first, then any \
detail. No greeting, no sign-off, no commentary about your task.

Return only the answer text."""

FAMILY_VOICE: Final = """
- You are speaking to a worried family member, not a clinician. Use everyday \
words: "blood pressure", "oxygen level", "blood sugar". Never use the words \
systolic, diastolic, SpO2, adherence, threshold, breach, vitals, metric or \
escalation."""

ADMIN_VOICE: Final = """
- You are speaking to DoorDoctor operations staff. Clinical and commercial \
vocabulary is correct. Be concise and factual; lead with the number they asked \
for."""


def _system_prompt(pack: ContextPack) -> str:
    return SYSTEM_PROMPT + (FAMILY_VOICE if pack.audience == "family" else ADMIN_VOICE)


def _user_prompt(pack: ContextPack, question: str, grounded: str) -> str:
    return (
        f"CONTEXT:\n{pack.render()}\n\n"
        f"QUESTION:\n{question.strip()}\n\n"
        f"A correct but plainly worded answer is:\n{grounded}\n\n"
        "Answer the question. You may reword and combine facts from the CONTEXT. "
        "You may not add anything that is not in it."
    )


# --------------------------------------------------------------------------
# The gates
# --------------------------------------------------------------------------


def _answer_is_acceptable(candidate: str, pack: ContextPack, grounded: str) -> bool:
    """The four gates between a model's output and a reader.

    Ordered cheapest-first. Gate 2 is the one that matters and is the direct
    analogue of Phase 6's "no invented numbers": a model cannot claim a blood
    pressure reading if a digit that is not in the context pack is grounds for
    rejection.
    """
    text = candidate.strip()
    if not (MIN_ANSWER_CHARS <= len(text) <= MAX_ANSWER_CHARS):
        logger.info("Discarding answer: length %d outside bounds", len(text))
        return False

    invented = summary_service.numbers_in(text) - pack.numbers() - summary_service.numbers_in(grounded)
    if invented:
        logger.info("Discarding answer: %d number(s) not present in the context pack", len(invented))
        return False

    # Family answers only. An admin is clinical staff, and "systolic" is the
    # correct word for them — a platform with one voice for both audiences is
    # what would be wrong here, not two.
    if pack.audience == "family":
        banned = summary_service.contains_clinical_language(text)
        if banned is not None:
            logger.info("Discarding answer: used the word %r to a family member", banned)
            return False

    lowered = text.lower()
    for phrase in summary_service.FORBIDDEN_REGISTER:
        if phrase in lowered:
            logger.info("Discarding answer: drifted into advice (%r)", phrase)
            return False

    return True


def _assist(pack: ContextPack, question: str, grounded: str) -> str | None:
    """A better-worded answer, or `None` on any doubt at all.

    `llm_client.complete` never raises — no key, disabled, timeout, 500,
    malformed body and empty completion all return `None` — so there is exactly
    one fallback path here rather than an except-list that drifts.
    """
    if not llm_client.available():
        return None

    candidate = llm_client.complete(
        system=_system_prompt(pack),
        user=_user_prompt(pack, question, grounded),
        timeout=llm_client.ASSISTANT_TIMEOUT,
        max_tokens=500,
    )
    if candidate is None or not _answer_is_acceptable(candidate, pack, grounded):
        return None
    return candidate.strip()


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def ask(
    db: Session,
    user: User,
    question: str,
    patient: Patient | None,
    *,
    assist: bool = True,
) -> dict[str, Any]:
    """Answer one question for one caller.

    `patient` has already been through `authorize_patient` when the caller named
    one. This function never resolves a `patient_id` itself — doing so would put
    an authorization decision in a service that has no business making one.
    """
    limiter.check(
        "assistant:user",
        str(user.id),
        limit=ASSISTANT_PER_USER[0],
        per_seconds=ASSISTANT_PER_USER[1],
    )

    role = user.role.value
    intent = assistant_fallback.match(question, role)

    # The emergency path. No pack, no model, no delay.
    if intent.id == assistant_intents.EMERGENCY.id:
        answer = Answer(
            assistant_fallback.EMERGENCY_ANSWER,
            intent,
            assistant_fallback.DISCLAIMER
            if role == UserRole.FAMILY.value
            else assistant_fallback.ADMIN_DISCLAIMER,
        )
        return _finish(db, user, question, answer, None, AssistantSource.DETERMINISTIC)

    if user.role == UserRole.ADMIN:
        pack = assistant_context.build_admin_pack(db, user)
    else:
        if patient is None:
            patient = assistant_context.primary_patient(db, user)
        pack = assistant_context.build_family_pack(db, user, patient)

    answer = assistant_fallback.answer(intent, pack, question)
    source = AssistantSource.DETERMINISTIC

    if assist:
        assisted = _assist(pack, question, answer.text)
        if assisted is not None:
            answer = Answer(assisted, intent, answer.disclaimer)
            source = AssistantSource.ASSISTED

    return _finish(db, user, question, answer, pack, source)


def _finish(
    db: Session,
    user: User,
    question: str,
    answer: Answer,
    pack: ContextPack | None,
    source: AssistantSource,
) -> dict[str, Any]:
    """Persist the exchange and shape the response."""
    patient_id = pack.patient_id if pack is not None else None
    record = AssistantMessage(
        user_id=user.id,
        patient_id=patient_id,
        question=question.strip(),
        answer=answer.text,
        intent=answer.intent.id,
        source=source,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "id": record.id,
        "question": record.question,
        "answer": record.answer,
        "intent": answer.intent.id,
        "intent_title": answer.intent.title,
        "source": source.value,
        "is_emergency": answer.is_emergency,
        "patient_id": patient_id,
        "disclaimer": answer.disclaimer,
        "suggestions": [
            intent.suggestion
            for intent in suggestions(user, has_patient=patient_id is not None)
            if intent.id != answer.intent.id
        ][:4],
        "created_at": record.created_at,
    }


def suggestions(user: User, *, has_patient: bool) -> list[assistant_intents.Intent]:
    """Starter questions for this caller, read off the catalogue."""
    return assistant_intents.suggestions_for(user.role.value, has_patient=has_patient)


def history(db: Session, user: User, limit: int = MAX_HISTORY) -> list[AssistantMessage]:
    """The caller's **own** exchanges, newest first.

    The `user_id` filter is the whole privacy model of this feature. There is no
    variant of this function that takes another user's id, and adding one is a
    consent decision rather than a convenience — see `models/assistant.py`.
    """
    return list(
        db.scalars(
            select(AssistantMessage)
            .options(selectinload(AssistantMessage.patient))
            .where(AssistantMessage.user_id == user.id)
            .order_by(AssistantMessage.created_at.desc(), AssistantMessage.id.desc())
            .limit(min(limit, MAX_HISTORY))
        )
    )


def serialize(message: AssistantMessage) -> dict[str, Any]:
    intent = assistant_intents.BY_ID.get(message.intent)
    return {
        "id": message.id,
        "question": message.question,
        "answer": message.answer,
        "intent": message.intent,
        "intent_title": intent.title if intent else message.intent,
        "source": message.source.value,
        "is_emergency": message.intent == assistant_intents.EMERGENCY.id,
        "patient_id": message.patient_id,
        "created_at": message.created_at,
    }
