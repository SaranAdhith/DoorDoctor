"""The deterministic assistant — no key, no network, no model (§2.3).

**This is the product.** It is built first, tested first and ships alone; the
Groq path added later in `assistant_service` is a polish pass that must clear
four gates and falls back here silently whenever it cannot. Phase 6 proved the
shape, and the demo configuration on the founder's laptop has no API key at all.

Two jobs, and they are separate on purpose:

* `match()` turns a typed question into an `Intent` using the scored catalogue in
  `assistant_intents`. **No intent string appears in this file** — reconciling
  §2.3 when it finally arrives must stay a one-file change.
* `answer()` composes a reply from a `ContextPack` and nothing else. It never
  touches the database: whatever is not in the pack cannot be said, which is the
  same rule the language model is held to.

The emergency intent is answered here and only here, and `assistant_service`
short-circuits to it before any thought of a model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from . import assistant_intents
from .assistant_context import ContextPack
from .assistant_intents import EMERGENCY, UNKNOWN, Intent

# --------------------------------------------------------------------------
# The two fixed texts
# --------------------------------------------------------------------------

EMERGENCY_ANSWER: Final = (
    "If this is an emergency, call 108 for an ambulance now. Do that first — before "
    "anything else, and before waiting for a reply here.\n\n"
    "Once help is on the way, call your DoorDoctor nurse, and then call the DoorDoctor "
    "care team. Both can be reached from the Alerts screen, and the team will follow up "
    "with you.\n\n"
    "I am an assistant that reads recorded home-care information. I cannot see what is "
    "happening right now and I cannot send help, so please do not wait for me."
)
"""108 → nurse → admin, in that order, fixed, and never generated.

Written out rather than assembled because there is no state of the database in
which the right answer to "she has collapsed" is different."""

DISCLAIMER: Final = (
    "I answer from the visit records DoorDoctor has for your family. I am not a doctor "
    "and this is not a medical diagnosis. In an emergency, call 108."
)

ADMIN_DISCLAIMER: Final = (
    "Answered from DoorDoctor's operational records. Figures are live at the time of "
    "asking and are not a clinical judgement."
)


@dataclass(frozen=True)
class Answer:
    """One deterministic reply, plus what the caller should know about it."""

    text: str
    intent: Intent
    disclaimer: str

    @property
    def is_emergency(self) -> bool:
        return self.intent.id == EMERGENCY.id


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------


def match(question: str, role: str) -> Intent:
    """The intent behind `question`, for a caller in `role`.

    Emergency is tested first and outside the scoring, because it is not
    competing with the other intents — it overrides them. "She has collapsed,
    when is the next visit?" is an emergency that happens to mention a visit.
    """
    text = " ".join(question.lower().split())
    if EMERGENCY.score(text):
        return EMERGENCY

    candidates = assistant_intents.for_role(role)
    if not candidates:
        return UNKNOWN

    best = max(candidates, key=lambda intent: intent.score(text))
    if best.score(text) < assistant_intents.MATCH_FLOOR:
        return UNKNOWN
    return best


# --------------------------------------------------------------------------
# Answering
# --------------------------------------------------------------------------


def answer(intent: Intent, pack: ContextPack, question: str = "") -> Answer:
    """Compose a reply to `intent` from `pack`.

    Every branch below reads `pack.facts` and nothing else. A branch that reached
    for a session would be a second, unauthorized route to the data the pack
    exists to bound.
    """
    disclaimer = ADMIN_DISCLAIMER if pack.audience == "admin" else DISCLAIMER
    if intent.id == EMERGENCY.id:
        return Answer(EMERGENCY_ANSWER, EMERGENCY, disclaimer)

    builder = _BUILDERS.get(intent.id)
    text = builder(pack) if builder else _capabilities(pack)
    if not text.strip():
        # A matched intent with nothing to say still owes the reader a sentence.
        text = _nothing_to_say(pack)
    return Answer(text.strip(), intent, disclaimer)


def _paragraphs(*blocks: str) -> str:
    return "\n\n".join(block.strip() for block in blocks if block and block.strip())


def _fact(pack: ContextPack, key: str) -> Any:
    return pack.facts.get(key)


def _first(pack: ContextPack) -> str:
    return pack.patient_first_name or "your relative"


def _no_patient() -> str:
    return (
        "There is no relative linked to your DoorDoctor account yet, so I do not have "
        "any care records to look at. DoorDoctor will link one for you — ask the care "
        "team and it will appear on your dashboard."
    )


# -- family ----------------------------------------------------------------


def _how_have_they_been(pack: ContextPack) -> str:
    summary = _fact(pack, "summary")
    if not summary:
        return _no_patient()
    return _paragraphs(summary["headline"], *summary["paragraphs"])


def _latest_readings(pack: ContextPack) -> str:
    reading = _fact(pack, "latest_reading")
    if not reading:
        if _fact(pack, "patient") is None:
            return _no_patient()
        return (
            f"No checks have been recorded for {_first(pack)} yet. The nurse records a "
            "set of readings at every home visit, and they will appear here after the "
            "first one."
        )
    described = "; ".join(reading["described"])
    flagged = (
        " One of those was outside the range DoorDoctor watches, so a nurse looked at it "
        "again."
        if reading["flagged"]
        else " All of those were inside the range DoorDoctor watches."
    )
    return (
        f"At the check on {reading['recorded_on']}, {_first(pack)}'s readings were: "
        f"{described}.{flagged}"
    )


def _medicines(pack: ContextPack) -> str:
    medicines = _fact(pack, "medicines")
    if not medicines:
        if _fact(pack, "patient") is None:
            return _no_patient()
        return (
            f"No medicine doses have been recorded for {_first(pack)} recently, so I "
            "cannot say how the medicines are going. The nurse records each dose during "
            "a visit."
        )
    taken, total, pct = medicines["taken"], medicines["total"], medicines["percentage"]
    if pct is not None and pct >= 90:
        verdict = "which is very good"
    elif pct is not None and pct >= 80:
        verdict = "which is good"
    elif pct is not None and pct >= 65:
        verdict = "so a few were missed"
    else:
        verdict = "so several were missed, which is worth asking your nurse about"
    return (
        f"{_first(pack)} took {taken} of the {total} medicine doses the nurse recorded in "
        f"the last {medicines['window_days']} days, {verdict}."
    )


def _next_visit(pack: ContextPack) -> str:
    visit = _fact(pack, "next_visit")
    if not visit:
        if _fact(pack, "patient") is None:
            return _no_patient()
        return (
            "No nurse visit is booked yet. DoorDoctor will be in touch to schedule the "
            "next one, and you can also ask the care team to book it."
        )
    who = (
        f"{visit['nurse_name']} is the nurse coming."
        if visit["nurse_name"]
        else "A nurse has not been assigned to it yet — DoorDoctor will confirm who is coming."
    )
    return f"The next nurse visit is on {visit['when']}. {who}"


def _who_is_the_nurse(pack: ContextPack) -> str:
    nurse = _fact(pack, "nurse")
    if not nurse:
        if _fact(pack, "patient") is None:
            return _no_patient()
        return (
            "No nurse has been assigned yet. Every DoorDoctor nurse is a qualified "
            "professional whose documents are checked before they visit a home."
        )
    standing = (
        "DoorDoctor has checked and verified their documents."
        if nurse["verified"]
        else "DoorDoctor is still completing their document check."
    )
    return (
        f"{nurse['name']} is the nurse caring for {_first(pack)}, and is a qualified "
        f"{nurse['credential']}. {standing}"
    )


def _about_the_alert(pack: ContextPack) -> str:
    alerts = _fact(pack, "alerts")
    if not alerts or not alerts["recent"]:
        if _fact(pack, "patient") is None:
            return _no_patient()
        return (
            f"Nothing has been flagged for {_first(pack)} recently. DoorDoctor checks "
            "every reading against the range set for them, and lets you know when one "
            "falls outside it."
        )

    lines = []
    for entry in alerts["recent"][:3]:
        about = _join(entry["about"])
        state = (
            "The care team is still reviewing it."
            if entry["open"]
            else "It has since been reviewed and closed."
        )
        lines.append(
            f"On {entry['when']}, {_first(pack)}'s {about} was outside the range "
            f"DoorDoctor watches. {state}"
        )
    closing = (
        "A flag means a reading fell outside the range set for your relative. It is not a "
        "diagnosis — a nurse looks at every one."
    )
    return _paragraphs("\n".join(lines), closing)


def _my_plan(pack: ContextPack) -> str:
    plan = _fact(pack, "plan")
    if not plan:
        return (
            "There is no active DoorDoctor plan on your account at the moment. The care "
            "team can talk you through the options."
        )
    visits = (
        f"It includes {plan['visits_per_month']} nurse visits a month"
        if plan["visits_per_month"] is not None
        else "It includes unlimited nurse visits"
    )
    return (
        f"You are on the {plan['name']} plan at {plan['price']} per "
        f"{plan['cycle'].replace('ly', '')}. {visits}, and it renews on "
        f"{plan['renews_on']}. You can see everything it covers on the My Plan screen."
    )


def _my_payments(pack: ContextPack) -> str:
    payments = _fact(pack, "payments")
    if not payments:
        return "There are no DoorDoctor invoices on your account yet."
    lines = [
        f"You have paid {payments['paid_count']} DoorDoctor "
        f"{_plural(payments['paid_count'], 'invoice')}, {payments['total_paid']} in total."
    ]
    if payments["outstanding_count"]:
        lines.append(
            f"{payments['outstanding_count']} "
            f"{_plural(payments['outstanding_count'], 'invoice is', 'invoices are')} "
            "still open. You can open every invoice as a PDF from the My Plan screen."
        )
    else:
        lines.append(
            "There is nothing outstanding. You can open every invoice as a PDF from the "
            "My Plan screen."
        )
    return " ".join(lines)


# -- admin -----------------------------------------------------------------


def _needs_attention(pack: ContextPack) -> str:
    alerts = _fact(pack, "alerts") or {}
    if not alerts.get("open"):
        return "No alerts are open. Nothing needs attention on the clinical queue right now."

    lines = [
        f"{alerts['open']} open {_plural(alerts['open'], 'alert')}, "
        f"{alerts['critical']} of them critical."
    ]
    for item in alerts.get("items", []):
        lines.append(
            f"· {item['patient']} — {item['severity']} · {_join(item['parameters'])} · "
            f"raised {item['raised_on']} · {item['status']}"
        )
    return "\n".join(lines)


def _todays_board(pack: ContextPack) -> str:
    today = _fact(pack, "today") or {}
    patients = _fact(pack, "patients") or {}
    total = today.get("total", 0)
    lines = [
        f"Today's board: {total} {_plural(total, 'visit')} — "
        f"{today.get('completed', 0)} completed, {today.get('in_progress', 0)} in progress, "
        f"{today.get('scheduled', 0)} still scheduled."
    ]
    unassigned = today.get("unassigned", 0)
    if unassigned:
        lines.append(
            f"{unassigned} still {_plural(unassigned, 'has', 'have')} no nurse assigned."
        )
    else:
        lines.append("Every visit today has a nurse assigned.")
    if patients:
        active = patients.get("active", 0)
        lines.append(
            f"{active} active {_plural(active, 'patient')} out of "
            f"{patients.get('total', 0)} on the books."
        )
    return " ".join(lines)


def _unassigned(pack: ContextPack) -> str:
    today = _fact(pack, "today") or {}
    detail = today.get("unassigned_detail") or []
    if not detail:
        return "Every visit on today's board has a nurse assigned."
    lines = [
        f"{len(detail)} of today's visits {_plural(len(detail), 'has', 'have')} "
        "no nurse assigned:"
    ]
    lines.extend(f"· {entry}" for entry in detail)
    lines.append("Assign them from the Visits screen.")
    return "\n".join(lines)


def _nurse_workload(pack: ContextPack) -> str:
    nurses = _fact(pack, "nurses") or {}
    if not nurses.get("total"):
        return "There are no nurses on the roster."
    lines = [
        f"{nurses['total']} {_plural(nurses['total'], 'nurse')} on the roster — "
        f"{nurses['active']} active, {nurses['unverified']} not yet verified."
    ]
    for entry in nurses.get("busiest", []):
        lines.append(
            f"· {entry['name']} — {entry['open_visits']} open "
            f"{_plural(entry['open_visits'], 'visit')}"
        )
    return "\n".join(lines)


def _revenue(pack: ContextPack) -> str:
    revenue = _fact(pack, "revenue") or {}
    if not revenue:
        return "No revenue figures are available."
    lines = [
        f"MRR is {revenue['mrr']} across {revenue['active_subscriptions']} active "
        f"{_plural(revenue['active_subscriptions'], 'subscription')}, "
        f"an ARR of {revenue['arr']}.",
        f"{revenue['collected_this_month']} collected this month; "
        f"{revenue['overdue']} overdue.",
    ]
    accounts = revenue.get("past_due_accounts") or []
    if accounts:
        lines.append(f"Past due: {_join(accounts)}.")
    else:
        lines.append("No account is past due.")
    for row in revenue.get("by_plan", []):
        lines.append(
            f"· {row['plan']} — {row['subscribers']} "
            f"{_plural(row['subscribers'], 'subscriber')}"
        )
    return "\n".join(lines)


# -- both ------------------------------------------------------------------


def _capabilities(pack: ContextPack) -> str:
    """What this assistant can answer, read off the catalogue itself.

    Listing the intents by hand here would be the second place an intent string
    lives, and the first thing to go stale when §2.3 arrives.
    """
    role = assistant_intents.FAMILY if pack.audience == "family" else assistant_intents.ADMIN
    available = assistant_intents.suggestions_for(
        role, has_patient=pack.patient_id is not None
    )
    opening = (
        "I can answer questions about the care DoorDoctor is providing for your family. "
        "Try one of these:"
        if pack.audience == "family"
        else "I can answer questions about how DoorDoctor is running today. Try one of these:"
    )
    listed = "\n".join(f"· {intent.suggestion}" for intent in available)
    closing = (
        "If something is wrong right now, call 108 first."
        if pack.audience == "family"
        else "I read the same records the dashboards do."
    )
    return _paragraphs(opening, listed, closing)


def _nothing_to_say(pack: ContextPack) -> str:
    return _paragraphs(
        "I do not have anything recorded that answers that yet.", _capabilities(pack)
    )


_BUILDERS: Final[dict[str, Any]] = {
    "how_have_they_been": _how_have_they_been,
    "latest_readings": _latest_readings,
    "medicines": _medicines,
    "next_visit": _next_visit,
    "who_is_the_nurse": _who_is_the_nurse,
    "about_the_alert": _about_the_alert,
    "my_plan": _my_plan,
    "my_payments": _my_payments,
    "needs_attention": _needs_attention,
    "todays_board": _todays_board,
    "unassigned": _unassigned,
    "nurse_workload": _nurse_workload,
    "revenue": _revenue,
    "capabilities": _capabilities,
    UNKNOWN.id: _capabilities,
}


def _join(items: list[str]) -> str:
    if not items:
        return "a reading"
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" and {items[-1]}"


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return singular if count == 1 else (plural or f"{singular}s")
