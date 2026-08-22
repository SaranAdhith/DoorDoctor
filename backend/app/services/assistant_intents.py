"""Every question the assistant knows how to answer, in one file.

This module imports nothing from the application. The fallback matcher, the
service, the router and the suggestion endpoint all read *this* catalogue, so an
intent cannot be described in two places and disagree with itself.

Provenance
----------
The build prompt is the source of truth. **§2.3's intent list was never supplied
to a build session**, so the catalogue below is `ASSUMED` — derived from what the
data model can genuinely answer, in the same spirit as `core/pricing.py`'s
invented prices. Every entry is marked, and the reconciliation table lives in
`docs/build-log/STATE.md`.

When the real §2.3 arrives, reconciling it is an edit to this file and nothing
else. **Keep it that way.** The moment a keyword is inlined into
`assistant_fallback.py`, that promise is broken and the reconciliation becomes a
hunt.

Matching
--------
Deterministic, explainable scoring — no model, no embedding, no network:

* a **phrase** is strong evidence and scores `PHRASE_WEIGHT`
* a **keyword** is weak evidence and scores `KEYWORD_WEIGHT`
* the highest-scoring intent available to the caller's role wins; ties break in
  catalogue order, so the more specific intent is listed first
* nothing clearing `MATCH_FLOOR` means `unknown`, which is a real answer rather
  than a failure

Patterns match with a word boundary at the **start** only, so "medicine" also
matches "medicines" and "medication" also matches "medications" without needing
a row each. Purely numeric patterns get a boundary at **both** ends, because
`\\b108` happily matches "1080".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

# Role values, duplicated from `models.enums.UserRole` on purpose: this module
# imports nothing from the application, which is what lets the seed, the tests
# and (later) the public site read it without an import cycle.
FAMILY: Final = "family"
ADMIN: Final = "admin"
BOTH: Final = (FAMILY, ADMIN)

PHRASE_WEIGHT: Final = 4
KEYWORD_WEIGHT: Final = 1
MATCH_FLOOR: Final = 2
"""Below this, the honest answer is "I did not understand that" — which the
fallback turns into a capability answer, not an error."""


@dataclass(frozen=True)
class Intent:
    """One thing a person can ask, and who is allowed to ask it."""

    id: str
    roles: tuple[str, ...]
    title: str
    """Short label carried back in the payload. Not shown as a sentence."""
    suggestion: str
    """The starter question offered as a chip. Written the way a person types."""
    needs_patient: bool = False
    """True when the answer is about one patient and a pack cannot be built without one."""
    phrases: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()

    def score(self, question: str) -> int:
        """How strongly `question` (already lowercased) looks like this intent."""
        total = 0
        for phrase in self.phrases:
            if _pattern(phrase).search(question):
                total += PHRASE_WEIGHT
        for keyword in self.keywords:
            if _pattern(keyword).search(question):
                total += KEYWORD_WEIGHT
        return total


_COMPILED: dict[str, re.Pattern[str]] = {}


def _pattern(text: str) -> re.Pattern[str]:
    """`text` as a start-anchored word-boundary regex, compiled once.

    Numeric patterns are anchored at both ends so "108" does not match "1080" —
    which matters here, because a heart rate can be 108 and an ambulance cannot.
    """
    compiled = _COMPILED.get(text)
    if compiled is None:
        escaped = re.escape(text)
        suffix = r"\b" if text.replace(" ", "").isdigit() else ""
        compiled = re.compile(rf"\b{escaped}{suffix}")
        _COMPILED[text] = compiled
    return compiled


# --------------------------------------------------------------------------
# The emergency intent
#
# Matched FIRST, before role scoping, before a context pack is built, and it
# never reaches a language model. "I think she is having a stroke" is not a
# question to hand to a 70B model with an 8-second timeout and a fallback path.
#
# Phrases only — no weak keyword scoring. A false positive here is alarming and
# a bare word like "help" would produce one on "can you help me read my bill?".
# Every pattern below is unambiguous in context. `108` appears only as an action
# ("call 108") because a blood glucose reading of 108 must not summon an
# ambulance.
# --------------------------------------------------------------------------

EMERGENCY: Final = Intent(
    id="emergency",
    roles=BOTH,
    title="Emergency",
    suggestion="Something is wrong right now",
    phrases=(
        "emergency",
        "ambulance",
        "call 108",
        "dial 108",
        "phone 108",
        "unconscious",
        "unresponsive",
        "not breathing",
        "cannot breathe",
        "can't breathe",
        "cant breathe",
        "struggling to breathe",
        "chest pain",
        "stroke",
        "seizure",
        "collapsed",
        "bleeding",
        "fell down",
        "has fallen",
        "is dying",
        "rush her",
        "rush him",
        "hospital right now",
        "something is wrong right now",
        "in danger",
    ),
)


# --------------------------------------------------------------------------
# The catalogue — every entry ASSUMED (see the provenance note above)
#
# Ordered most specific first, because ties break in catalogue order.
# --------------------------------------------------------------------------

INTENTS: Final[tuple[Intent, ...]] = (
    # -- family ----------------------------------------------------------
    Intent(  # ASSUMED
        id="latest_readings",
        roles=(FAMILY,),
        title="Latest readings",
        suggestion="What were her last readings?",
        needs_patient=True,
        phrases=(
            "last reading",
            "latest reading",
            "recent reading",
            "blood pressure",
            "blood sugar",
            "oxygen level",
            "heart rate",
        ),
        keywords=("reading", "pressure", "sugar", "oxygen", "pulse", "latest", "last", "number"),
    ),
    Intent(  # ASSUMED
        id="medicines",
        roles=(FAMILY,),
        title="Medicines",
        suggestion="Is she taking her medicines?",
        needs_patient=True,
        phrases=(
            "taking her medicine",
            "taking his medicine",
            "taking the medicine",
            "missed a dose",
            "missed any dose",
            "missing dose",
        ),
        keywords=("medicine", "medication", "tablet", "pill", "dose", "taking"),
    ),
    Intent(  # ASSUMED
        id="next_visit",
        roles=(FAMILY,),
        title="Next visit",
        suggestion="When is the next nurse visit?",
        needs_patient=True,
        phrases=("next visit", "when is the next", "when will the nurse", "coming next"),
        keywords=("visit", "when", "next", "schedule", "appointment", "coming"),
    ),
    Intent(  # ASSUMED
        id="who_is_the_nurse",
        roles=(FAMILY,),
        title="The nurse",
        suggestion="Who is the nurse, and are they verified?",
        needs_patient=True,
        phrases=("who is the nurse", "which nurse", "nurse verified", "about the nurse"),
        keywords=("nurse", "verified", "qualified", "credential", "trained", "who"),
    ),
    Intent(  # ASSUMED
        id="about_the_alert",
        roles=(FAMILY,),
        title="That alert",
        suggestion="What was that alert about?",
        needs_patient=True,
        phrases=("that alert", "the alert about", "why was there an alert", "why did you flag"),
        keywords=("alert", "flag", "warning", "notified", "notification", "concern"),
    ),
    Intent(  # ASSUMED
        id="how_have_they_been",
        roles=(FAMILY,),
        title="How they have been",
        suggestion="How has she been this week?",
        needs_patient=True,
        phrases=(
            "how has she been",
            "how has he been",
            "how have they been",
            "how is she doing",
            "how is he doing",
            "how are they doing",
        ),
        keywords=("how", "been", "doing", "week", "summary", "overall", "lately", "recently"),
    ),
    Intent(  # ASSUMED
        id="my_plan",
        roles=(FAMILY,),
        title="My plan",
        suggestion="What does my plan cover?",
        phrases=("my plan", "plan cover", "which plan", "how many visit"),
        keywords=("plan", "cover", "subscription", "included", "tier", "upgrade", "entitle"),
    ),
    Intent(  # ASSUMED
        id="my_payments",
        roles=(FAMILY,),
        title="Payments",
        suggestion="What have I paid so far?",
        phrases=("have i paid", "my invoice", "my bill", "next payment", "how much do i"),
        keywords=("paid", "payment", "invoice", "bill", "charge", "receipt", "credit", "refund"),
    ),
    # -- admin -----------------------------------------------------------
    Intent(  # ASSUMED
        id="unassigned",
        roles=(ADMIN,),
        title="Unassigned visits",
        suggestion="Which visits are unassigned?",
        phrases=("unassigned", "not assigned", "no nurse", "without a nurse", "needs a nurse"),
        keywords=("unassigned", "assign", "unallocated", "uncovered", "gap"),
    ),
    Intent(  # ASSUMED
        id="needs_attention",
        roles=(ADMIN,),
        title="Needs attention",
        suggestion="Which patients need attention today?",
        phrases=("need attention", "needs attention", "who needs", "open alert", "active alert"),
        keywords=("attention", "alert", "urgent", "critical", "escalate", "risk", "worry"),
    ),
    Intent(  # ASSUMED
        id="todays_board",
        roles=(ADMIN,),
        title="Today's board",
        suggestion="What is on the board today?",
        phrases=("the board", "board today", "visits today", "today's visit", "todays visit"),
        keywords=("board", "today", "visit", "schedule", "roster", "run"),
    ),
    Intent(  # ASSUMED
        id="nurse_workload",
        roles=(ADMIN,),
        title="Nurse workload",
        suggestion="How is the nursing team loaded?",
        phrases=("how is nurse", "nurse workload", "which nurse", "how many visits does"),
        keywords=("nurse", "workload", "busy", "capacity", "load", "staff", "team"),
    ),
    Intent(  # ASSUMED
        id="revenue",
        roles=(ADMIN,),
        title="Revenue",
        suggestion="What is MRR, and who is past due?",
        phrases=("past due", "monthly recurring", "how much revenue", "the business doing"),
        keywords=("revenue", "mrr", "arr", "arpu", "income", "overdue", "collect", "churn", "money"),
    ),
    # -- both ------------------------------------------------------------
    Intent(  # ASSUMED
        id="capabilities",
        roles=BOTH,
        title="What I can answer",
        suggestion="What can you tell me about?",
        phrases=("what can you", "what do you know", "what should i ask", "who are you"),
        keywords=("capabilit", "able to"),
    ),
)

UNKNOWN: Final = Intent(
    id="unknown",
    roles=BOTH,
    title="Not understood",
    suggestion="What can you tell me about?",
)

BY_ID: Final[dict[str, Intent]] = {intent.id: intent for intent in (*INTENTS, EMERGENCY, UNKNOWN)}


def for_role(role: str) -> tuple[Intent, ...]:
    """The catalogue entries a caller in `role` may reach.

    Role filtering happens **before** scoring, which is why "which nurse?" can
    mean two different things to a family member and an admin without either
    intent needing to know the other exists.
    """
    return tuple(intent for intent in INTENTS if role in intent.roles)


SUGGESTION_EXCLUDED: Final = ("capabilities",)
"""Intents that stay matchable but are never offered as a chip.

`capabilities` answers "what can you tell me about?" by listing the suggestions —
so offering it *as* a suggestion is circular, and it costs a row in a list that
stacks vertically on a phone."""


def suggestions_for(role: str, *, has_patient: bool) -> list[Intent]:
    """Starter questions to offer this caller.

    Patient-scoped intents are withheld from a family member with no patient
    linked yet — offering "how has she been?" to someone with no relative on the
    platform is a chip that can only disappoint.
    """
    return [
        intent
        for intent in for_role(role)
        if (has_patient or not intent.needs_patient) and intent.id not in SUGGESTION_EXCLUDED
    ]
