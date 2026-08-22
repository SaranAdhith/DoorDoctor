"""The AI assistant (§2.3).

The whole point of this file is the first section: **every intent answers with no
API key.** That is the demo configuration on the founder's laptop, and Phase 6
established that proving it is what makes the model optional rather than load
bearing.
"""

import pytest

from app.core.ratelimit import ASSISTANT_PER_USER
from app.models import UserRole
from app.services import (
    assistant_context,
    assistant_fallback,
    assistant_intents,
    assistant_service,
    llm_client,
    summary_service,
)

from .conftest import DEMO_PASSWORD, auth, login

ASK = "/api/v1/assistant/ask"
CONVERSATIONS = "/api/v1/assistant/conversations"
SUGGESTIONS = "/api/v1/assistant/suggestions"


def _ask(client, headers, question, **body):
    response = client.post(ASK, json={"question": question, **body}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------
# Every intent, with no key configured
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "intent", assistant_intents.INTENTS, ids=lambda i: i.id
)
def test_every_intent_is_matched_by_its_own_starter_question(intent):
    """Parametrized over the catalogue, so an intent cannot be added without a test.

    A suggestion chip that does not match the intent it advertises is the worst
    kind of bug here: the product tells the user what to type and then fails to
    understand it.
    """
    role = intent.roles[0]
    assert assistant_fallback.match(intent.suggestion, role).id == intent.id


@pytest.mark.parametrize(
    "intent", assistant_intents.for_role("family"), ids=lambda i: i.id
)
def test_every_family_intent_answers_with_no_key(client, family_headers, intent):
    payload = _ask(client, family_headers, intent.suggestion)
    assert payload["source"] == "deterministic"
    assert len(payload["answer"]) > 20, payload["answer"]


@pytest.mark.parametrize(
    "intent", assistant_intents.for_role("admin"), ids=lambda i: i.id
)
def test_every_admin_intent_answers_with_no_key(client, admin_headers, intent):
    payload = _ask(client, admin_headers, intent.suggestion)
    assert payload["source"] == "deterministic"
    assert len(payload["answer"]) > 20, payload["answer"]


@pytest.mark.parametrize(
    "intent", assistant_intents.for_role("family"), ids=lambda i: i.id
)
def test_no_family_answer_uses_clinical_language(client, family_headers, intent):
    """The Phase 6 vocabulary rule, applied to the assistant.

    A platform that says "blood pressure" on the dashboard and "systolic" in the
    assistant has two voices for one reader.
    """
    payload = _ask(client, family_headers, intent.suggestion)
    banned = summary_service.contains_clinical_language(payload["answer"])
    assert banned is None, f"{intent.id} said {banned!r}: {payload['answer']}"


def test_the_family_context_pack_itself_avoids_clinical_language(db):
    """The pack is written in the reader's vocabulary, not just the answer.

    Which is what makes the banned-word gate nearly unfailable instead of a trap:
    a model copying a phrase straight out of the context cannot reintroduce a
    word the deterministic generator was written to avoid.
    """
    from sqlalchemy import select

    from app.models import User

    user = db.scalars(
        select(User).where(User.role == UserRole.FAMILY).order_by(User.id).limit(1)
    ).first()
    patient = assistant_context.primary_patient(db, user)
    pack = assistant_context.build_family_pack(db, user, patient)
    assert summary_service.contains_clinical_language(pack.render()) is None


def test_an_unmatched_question_still_gets_a_useful_answer(client, family_headers):
    payload = _ask(client, family_headers, "what is the weather in Chennai today")
    assert payload["intent"] == "unknown"
    assert "call 108" in payload["answer"]
    assert payload["suggestions"], "an unmatched question must offer a way forward"


def test_no_upstream_call_is_made_when_no_key_is_configured(client, family_headers, monkeypatch):
    def explode(**kwargs):  # pragma: no cover - must never run
        raise AssertionError("the assistant reached for a model with no key configured")

    monkeypatch.setattr(assistant_service.llm_client, "complete", explode)
    assert _ask(client, family_headers, "How has she been this week?")["source"] == "deterministic"


# --------------------------------------------------------------------------
# The emergency path
# --------------------------------------------------------------------------

EMERGENCY_QUESTIONS = [
    "I think she is having a stroke",
    "amma has collapsed, what do I do",
    "she is not breathing",
    "should I call an ambulance",
    "he has chest pain right now",
]


@pytest.mark.parametrize("question", EMERGENCY_QUESTIONS)
def test_an_emergency_is_matched_and_never_reaches_the_model(
    client, family_headers, monkeypatch, question
):
    def explode(**kwargs):  # pragma: no cover - must never run
        raise AssertionError("an emergency question was sent to a language model")

    monkeypatch.setattr(assistant_service.llm_client, "complete", explode)
    monkeypatch.setattr(assistant_service.llm_client, "available", lambda: True)

    payload = _ask(client, family_headers, question)
    assert payload["intent"] == "emergency"
    assert payload["is_emergency"] is True


def test_the_emergency_answer_escalates_108_then_nurse_then_admin(client, family_headers):
    answer = _ask(client, family_headers, "she has collapsed")["answer"]
    assert answer.index("108") < answer.index("nurse") < answer.index("care team")


def test_an_admin_asking_about_an_emergency_gets_the_same_escalation(client, admin_headers):
    payload = _ask(client, admin_headers, "a patient is unconscious")
    assert payload["intent"] == "emergency"
    assert "108" in payload["answer"]


NOT_EMERGENCIES = [
    "can you help me read my bill",
    "her blood sugar was 108 at the last check",
    "what does my plan cover",
    "when is the next visit",
]


@pytest.mark.parametrize("question", NOT_EMERGENCIES)
def test_ordinary_questions_are_not_treated_as_emergencies(client, family_headers, question):
    """A false emergency is alarming, and "108" is also a plausible blood sugar.

    The catalogue matches `call 108`, never a bare `108`, for exactly this case.
    """
    assert _ask(client, family_headers, question)["intent"] != "emergency"


# --------------------------------------------------------------------------
# Authorization
# --------------------------------------------------------------------------


def test_a_family_user_cannot_ask_about_another_familys_patient(
    client, family_headers, other_family
):
    """404, never 403. A 403 confirms the record exists, which is enough to learn
    that a named person is a DoorDoctor patient."""
    response = client.post(
        ASK,
        json={"question": "How has she been?", "patient_id": other_family["patient_id"]},
        headers=family_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Patient not found."


def test_a_family_pack_never_contains_another_familys_patient(client, family_headers, other_family):
    payload = _ask(client, family_headers, "How has she been this week?")
    assert "Other Patient" not in payload["answer"]


def test_a_family_member_omitting_a_patient_gets_their_own(client, family_headers):
    payload = _ask(client, family_headers, "What were her last readings?")
    assert payload["patient_id"] == 1
    assert "Lakshmi" in payload["answer"]


def test_a_nurse_has_no_assistant(client, nurse_headers):
    """Decided explicitly with the founder, not left to fall out of a missing check.

    A nurse assistant needs its own context pack and its own intents and belongs
    with Phase 10's nurse operations screens.
    """
    for method, url in (("post", ASK), ("get", CONVERSATIONS), ("get", SUGGESTIONS)):
        response = getattr(client, method)(
            url, headers=nurse_headers, **({"json": {"question": "hi"}} if method == "post" else {})
        )
        assert response.status_code == 403, url


def test_an_anonymous_caller_is_rejected(client):
    assert client.post(ASK, json={"question": "How has she been?"}).status_code == 401


# --------------------------------------------------------------------------
# History — scoped to the asker, and to nobody else
# --------------------------------------------------------------------------


def test_history_returns_the_callers_own_questions_newest_first(client, family_headers):
    _ask(client, family_headers, "What were her last readings?")
    _ask(client, family_headers, "When is the next nurse visit?")

    response = client.get(CONVERSATIONS, headers=family_headers)
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 2
    assert rows[0]["question"] == "When is the next nurse visit?"


def test_an_admin_cannot_read_a_family_members_history(client, family_headers, admin_headers):
    """The `user_id` filter is the entire privacy model of this feature.

    An admin support tool that reads a daughter's questions about her mother
    needs consent language this build does not have.
    """
    _ask(client, family_headers, "Is she taking her medicines?")

    rows = client.get(CONVERSATIONS, headers=admin_headers).json()
    assert all("medicines" not in row["question"] for row in rows)


def test_a_second_family_cannot_read_the_first_familys_history(
    client, family_headers, other_family
):
    _ask(client, family_headers, "What have I paid so far?")

    other_headers = auth(login(client, other_family["email"], DEMO_PASSWORD))
    assert client.get(CONVERSATIONS, headers=other_headers).json() == []


# --------------------------------------------------------------------------
# Suggestions
# --------------------------------------------------------------------------


def test_suggestions_are_role_scoped(client, family_headers, admin_headers):
    family = {row["intent"] for row in client.get(SUGGESTIONS, headers=family_headers).json()}
    admin = {row["intent"] for row in client.get(SUGGESTIONS, headers=admin_headers).json()}

    assert "my_plan" in family and "revenue" not in family
    assert "revenue" in admin and "my_plan" not in admin


def test_patient_scoped_suggestions_are_withheld_when_no_patient_is_linked(client):
    """`meera@doordoctor.in`'s situation: a subscription but nobody linked yet.

    Offering "how has she been this week?" to someone with no relative on the
    platform is a chip that can only disappoint.
    """
    headers = auth(login(client, "meera@doordoctor.in", DEMO_PASSWORD))
    intents = {row["intent"] for row in client.get(SUGGESTIONS, headers=headers).json()}
    assert "how_have_they_been" not in intents
    assert "my_plan" in intents


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------


def test_the_assistant_is_rate_limited_per_user(client, family_headers):
    """An unmetered LLM endpoint behind a login is the obvious way to burn a tier."""
    limit = ASSISTANT_PER_USER[0]
    for _ in range(limit):
        assert client.post(ASK, json={"question": "hello"}, headers=family_headers).status_code == 200

    response = client.post(ASK, json={"question": "hello"}, headers=family_headers)
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0


def test_the_limit_is_per_user_not_global(client, family_headers, admin_headers):
    for _ in range(ASSISTANT_PER_USER[0]):
        client.post(ASK, json={"question": "hello"}, headers=family_headers)

    assert client.post(ASK, json={"question": "hello"}, headers=admin_headers).status_code == 200


# --------------------------------------------------------------------------
# Request validation
# --------------------------------------------------------------------------


@pytest.mark.parametrize("question", ["", "   ", "x" * 501])
def test_an_unusable_question_is_rejected(client, family_headers, question):
    assert client.post(ASK, json={"question": question}, headers=family_headers).status_code == 422


# --------------------------------------------------------------------------
# The assisted path
# --------------------------------------------------------------------------


@pytest.fixture
def assisted(monkeypatch):
    """Make the assisted path reachable, and hand back a call counter.

    Copied from `test_summary.py` deliberately — one shape for faking the model
    across the suite. `test_llm_client.py` covers faking `httpx` itself.
    """
    monkeypatch.setattr(llm_client.settings, "groq_api_key", "test-key", raising=False)
    monkeypatch.setattr(llm_client.settings, "assistant_enabled", True, raising=False)
    calls: list[str] = []

    def install(reply):
        def fake(*, system, user, timeout, max_tokens=400, temperature=0.2):
            calls.append(user)
            return reply(user) if callable(reply) else reply

        monkeypatch.setattr(assistant_service.llm_client, "complete", fake)

    return install, calls


def test_a_clean_answer_is_used_and_declared(client, family_headers, assisted):
    install, calls = assisted
    install("Lakshmi has been keeping well, and the nurse is happy with how things look.")

    payload = _ask(client, family_headers, "How has she been this week?")
    assert payload["source"] == "assisted"
    assert payload["answer"].startswith("Lakshmi has been keeping well")
    assert len(calls) == 1


def test_the_assistant_uses_the_eight_second_budget(client, family_headers, monkeypatch, assisted):
    """A summary rewrite blocks a dashboard paint; an assistant reply is watched.

    Both call the *same* `llm_client.complete` — there is one client — with
    different timeouts, and this asserts the assistant passes its own.
    """
    seen: list[float] = []

    monkeypatch.setattr(llm_client.settings, "groq_api_key", "test-key", raising=False)

    def fake(*, system, user, timeout, max_tokens=400, temperature=0.2):
        seen.append(timeout)
        return None

    monkeypatch.setattr(assistant_service.llm_client, "complete", fake)
    _ask(client, family_headers, "How has she been this week?")
    assert seen == [llm_client.ASSISTANT_TIMEOUT]


def test_an_answer_that_invents_a_number_is_discarded(client, family_headers, assisted):
    """The strongest gate, and the direct analogue of Phase 6's rule.

    A model cannot claim a blood pressure reading if a digit that is not in the
    context pack is grounds for rejection.
    """
    install, _ = assisted
    install("Lakshmi has been well. Her blood pressure was 171 over 103 at the last check.")

    payload = _ask(client, family_headers, "How has she been this week?")
    assert payload["source"] == "deterministic"
    assert "171" not in payload["answer"]


def test_a_family_answer_that_reintroduces_clinical_language_is_discarded(
    client, family_headers, assisted
):
    install, _ = assisted
    install("Lakshmi has had no systolic threshold breaches this week, which is good news.")

    assert _ask(client, family_headers, "How has she been this week?")["source"] == "deterministic"


def test_the_same_wording_is_kept_for_an_admin(client, admin_headers, assisted):
    """Gate 2 is family-only, and this is what asserts it.

    An admin is clinical staff and "systolic" is the correct word for them. One
    voice for both audiences is what would be wrong here, not two.
    """
    install, _ = assisted
    install("No systolic threshold breaches are open across the board this morning.")

    payload = _ask(client, admin_headers, "Which patients need attention today?")
    assert payload["source"] == "assisted"
    assert "systolic" in payload["answer"]


def test_an_answer_that_drifts_into_advice_is_discarded(client, family_headers, assisted):
    install, _ = assisted
    install("Lakshmi has been well. I recommend she stops taking her evening tablet.")

    assert _ask(client, family_headers, "How has she been this week?")["source"] == "deterministic"


@pytest.mark.parametrize("reply", ["", "Fine.", "x" * 2000])
def test_unusable_answers_fall_back_silently(client, family_headers, assisted, reply):
    install, _ = assisted
    install(reply)

    payload = _ask(client, family_headers, "How has she been this week?")
    assert payload["source"] == "deterministic"
    assert payload["answer"], "the reader still gets an answer"


def test_the_context_pack_is_the_only_thing_the_model_receives(
    client, family_headers, other_family, assisted
):
    """The security boundary, asserted on the wire.

    Whatever the prompt says, another family's patient was never in the context
    to begin with — which is why there is no instruction here for a model to
    disobey.
    """
    install, calls = assisted
    install("Lakshmi has been keeping well this week and the nurse is happy.")

    _ask(client, family_headers, "How has she been this week?")
    prompt = calls[0]
    assert "Lakshmi" in prompt
    assert "Other Patient" not in prompt


def test_the_stored_source_matches_what_was_reported(client, family_headers, assisted):
    install, _ = assisted
    install("Lakshmi has been keeping well this week and the nurse is happy.")

    _ask(client, family_headers, "How has she been this week?")
    assert client.get(CONVERSATIONS, headers=family_headers).json()[0]["source"] == "assisted"
