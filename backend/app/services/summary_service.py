"""Plain-language health summaries for family members (§2.2).

The rule this module exists to enforce:

    A family member reads "her blood pressure has been steady this week",
    never "no systolic threshold breaches in the 7d window".

That rule is machine-checked. `contains_clinical_language()` is applied to the
deterministic output by the test suite *and* to any LLM rewrite at runtime, so a
model cannot reintroduce the vocabulary the deterministic generator was written
to avoid.

The deterministic generator is the product. The Groq rewrite is an optional
polish pass that must clear four gates before it is shown to anyone, and falls
back silently when it cannot. The demo works with no key and no network.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import fmean
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import now
from ..models import Alert, AlertStatus, Patient, Visit, VisitStatus, Vital
from . import llm_client, medication_service, vitals_service

logger = logging.getLogger("doordoctor.summary")

# --------------------------------------------------------------------------
# Windows
# --------------------------------------------------------------------------

WINDOWS: Final[dict[str, tuple[int, str]]] = {
    "7d": (7, "the last 7 days"),
    "30d": (30, "the last 30 days"),
    "90d": (90, "the last 3 months"),
}

DEFAULT_WINDOW: Final = "7d"

# --------------------------------------------------------------------------
# The banned vocabulary — this list *is* the specification
# --------------------------------------------------------------------------

BANNED_WORDS: Final[tuple[str, ...]] = (
    "systolic",
    "diastolic",
    "spo2",
    "sp02",
    "adherence",
    "threshold",
    "breach",
    "vitals",
    "metric",
    "escalation",
)


def contains_clinical_language(text: str) -> str | None:
    """The first banned word found in `text`, or None.

    Substring matching on purpose: "thresholds", "breached" and "escalations"
    are the same failure as their stems, and a word-boundary check would let
    every one of them through.
    """
    lowered = text.lower()
    for word in BANNED_WORDS:
        if word in lowered:
            return word
    return None


# What a family member calls each thing the platform measures.
#
# This lives here rather than in the assistant because *this module owns the
# vocabulary rule*, and a second table elsewhere is how "blood sugar" and
# "glucose" start appearing on the same screen. `alert_service.METRIC_LABELS` is
# the clinical counterpart and is correct for admins — the two are deliberately
# different, not duplicates.
#
# Both halves of a blood pressure map to the same phrase: a family member does
# not think of two numbers, so callers listing several breached measurements
# must de-duplicate.
PLAIN_METRIC_LABELS: Final[dict[str, str]] = {
    "systolic_bp": "blood pressure",
    "diastolic_bp": "blood pressure",
    "heart_rate": "heart rate",
    "blood_glucose": "blood sugar",
    "spo2": "oxygen level",
    "temperature": "temperature",
    "weight": "weight",
}


def plain_metric_label(metric: str) -> str:
    """A measurement's name in the reader's vocabulary.

    Falls back to "reading", which is vague but never wrong and never leaks a
    column name to a family member.
    """
    return PLAIN_METRIC_LABELS.get(metric, "reading")


# --------------------------------------------------------------------------
# What counts as a change worth mentioning
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Measure:
    """One thing the summary can talk about, in the reader's vocabulary."""

    key: str
    """Attribute on `Vital`. Never shown to the reader."""
    label: str
    """What a family member calls it."""
    decimals: int
    noticeable: float
    """Smallest shift in the mean worth calling a trend rather than noise."""
    rising: str
    """How to describe the mean going up."""
    falling: str
    """How to describe the mean coming down."""
    worse_when: str | None
    """"up", "down", or None when either direction is simply a change."""
    unit: str = ""
    """Spelled out, not abbreviated — `percent`, not `%`."""
    detail: str = ""
    """Names the number being averaged when the label alone is ambiguous.

    Blood pressure is two numbers under one name; the trend is computed on the
    upper one, so it has to say so rather than quote a bare 142 the reader
    cannot place.
    """
    plural_subject: bool = False
    """True when the label takes `have` rather than `has`."""


# The floors are the difference between a generator anyone believes and one that
# reports a trend every single week. Below them the honest answer is "steady",
# which is a real finding and the most common one.
MEASURES: Final[tuple[Measure, ...]] = (
    Measure("systolic_bp", "blood pressure", 0, 5.0, "has been running a little higher",
            "has come down", "up", detail="the upper reading"),
    Measure("blood_glucose", "blood sugar", 0, 15.0, "has crept up", "has come down", "up"),
    Measure("spo2", "oxygen levels", 0, 1.5, "have improved", "have dipped a little", "down",
            unit=" percent", plural_subject=True),
    Measure("heart_rate", "heart rate", 0, 5.0, "has been a little faster",
            "has been a little slower", None, unit=" beats a minute"),
    Measure("temperature", "temperature", 1, 0.5, "has been a little warmer",
            "has been a little cooler", "up", unit=" degrees"),
    Measure("weight", "weight", 1, 1.5, "has gone up", "has come down", None, unit=" kg"),
)

MIN_READINGS_FOR_TREND: Final = 4

DISCLAIMER: Final = (
    "This summary describes readings taken at home during nurse visits. It is not a "
    "medical diagnosis. If you are worried about {first_name} right now, call 108 and "
    "then your nurse."
)


# --------------------------------------------------------------------------
# Small formatting helpers
# --------------------------------------------------------------------------


def _number(value: float, decimals: int = 0) -> str:
    if decimals == 0:
        return str(int(round(value)))
    return f"{value:.{decimals}f}"


def _day(moment: datetime) -> str:
    """`21 August` — no zero padding, no year, because families read it aloud."""
    return f"{moment.day} {moment:%B}"


def _weekday(moment: datetime) -> str:
    return f"{moment:%A} {moment.day} {moment:%B}"


def _clock(moment: datetime) -> str:
    hour = moment.hour % 12 or 12
    suffix = "am" if moment.hour < 12 else "pm"
    return f"{hour}:{moment.minute:02d} {suffix}"


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return singular if count == 1 else (plural or f"{singular}s")


def _first_name(patient: Patient) -> str:
    return patient.name.split()[0]


# --------------------------------------------------------------------------
# Trend detection
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Trend:
    measure: Measure
    direction: str
    """`steady`, `up` or `down`."""
    early: float
    late: float

    @property
    def tone(self) -> str:
        if self.direction == "steady":
            return "good"
        if self.measure.worse_when is None:
            return "watch"
        return "watch" if self.direction == self.measure.worse_when else "good"


def _trend_for(readings: list[Vital], measure: Measure) -> Trend | None:
    """Compare the first half of the window against the second half.

    Returns None when there is too little to say. Two readings a fortnight apart
    describe a pair of moments, not a direction.
    """
    values = [
        float(getattr(reading, measure.key))
        for reading in readings
        if getattr(reading, measure.key) is not None
    ]
    if len(values) < MIN_READINGS_FOR_TREND:
        return None

    half = len(values) // 2
    early = fmean(values[:half])
    late = fmean(values[-half:])
    delta = late - early

    if abs(delta) < measure.noticeable:
        return Trend(measure, "steady", early, late)
    return Trend(measure, "up" if delta > 0 else "down", early, late)


def _describe(trend: Trend, first_name: str) -> str:
    measure = trend.measure
    subject = f"{first_name}'s {measure.label}"
    early = _number(trend.early, measure.decimals) + measure.unit
    late = _number(trend.late, measure.decimals) + measure.unit

    if trend.direction == "steady":
        verb = "have been steady" if measure.plural_subject else "has been steady"
        if measure.detail:
            return f"{subject} {verb}, with {measure.detail} averaging around {late}."
        return f"{subject} {verb}, averaging around {late}."

    movement = measure.rising if trend.direction == "up" else measure.falling
    averaged = f"{measure.detail} averaged" if measure.detail else "averaging"
    return (
        f"{subject} {movement} — {averaged} {early} earlier in the period and "
        f"{late} more recently."
    )


def _join(items: list[str]) -> str:
    """`a`, `a and b`, `a, b and c` — an Oxford-comma-free list a person reads aloud."""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" and {items[-1]}"


# --------------------------------------------------------------------------
# The deterministic generator
# --------------------------------------------------------------------------


def build_deterministic(db: Session, patient: Patient, window: str) -> dict[str, Any]:
    """The summary over a rolling window ending now.

    Assembled from data alone. No network, no key, no model.
    """
    days, window_label = WINDOWS[window]
    until = now()
    return build_for_period(
        db, patient, until - timedelta(days=days), until, window_label, window=window
    )


def build_for_period(
    db: Session,
    patient: Patient,
    since: datetime,
    until: datetime,
    window_label: str,
    *,
    window: str = DEFAULT_WINDOW,
) -> dict[str, Any]:
    """The summary over an explicit `[since, until)` period.

    Reports need this rather than a rolling window: a monthly report covers a
    closed calendar month, and describing it as "the last 30 days" would put
    August readings in a document headed July.
    """
    generated_at = now()
    first = _first_name(patient)

    readings = vitals_service.history_since(db, patient.id, since, until)
    doses = medication_service.adherence_for_patient(db, patient.id, since=since, until=until)

    visits = list(
        db.scalars(
            select(Visit)
            .where(
                Visit.patient_id == patient.id,
                Visit.scheduled_at >= since,
                Visit.scheduled_at < until,
            )
            .order_by(Visit.scheduled_at)
        )
    )
    completed_visits = [v for v in visits if v.status == VisitStatus.COMPLETED]
    next_visit = db.scalar(
        select(Visit)
        .where(
            Visit.patient_id == patient.id,
            Visit.scheduled_at >= generated_at,  # from now, not from the period end
            Visit.status.in_((VisitStatus.SCHEDULED, VisitStatus.IN_PROGRESS)),
        )
        .order_by(Visit.scheduled_at)
        .limit(1)
    )

    alerts = list(
        db.scalars(
            select(Alert)
            .where(
                Alert.patient_id == patient.id,
                Alert.created_at >= since,
                Alert.created_at < until,
            )
            .order_by(Alert.created_at)
        )
    )
    open_alerts = [a for a in alerts if a.status != AlertStatus.RESOLVED]
    closed_alerts = [a for a in alerts if a.status == AlertStatus.RESOLVED]
    flagged_readings = [r for r in readings if r.threshold_breached]

    paragraphs: list[str] = []
    highlights: list[dict[str, str]] = []
    next_steps: list[str] = []

    # -- Paragraph 1: how they have been ---------------------------------
    if not readings:
        headline = f"We have not recorded any checks for {first} in {window_label}."
        paragraphs.append(
            f"No nurse visit in {window_label} has produced a set of readings for {first}, "
            "so there is nothing new to report on how they have been."
        )
        highlights.append({"tone": "watch", "text": "No readings in this period"})
    else:
        count = len(readings)
        latest = readings[-1]
        paragraphs.append(
            f"{first} was checked {count} {_plural(count, 'time')} in {window_label}. "
            f"The most recent check was on {_day(latest.recorded_at)}, when {first}'s blood "
            f"pressure was {_number(latest.systolic_bp)} over {_number(latest.diastolic_bp)} "
            f"and oxygen level was {_number(latest.spo2)} percent."
        )

        if open_alerts:
            headline = (
                f"{first} needs a closer look — the care team is reviewing "
                f"{len(open_alerts)} {_plural(len(open_alerts), 'reading')}."
            )
        elif flagged_readings:
            headline = (
                f"{first} has been mostly well, with a few readings we looked at more closely."
            )
        else:
            headline = f"{first} has been doing well over {window_label}."

    # -- Paragraph 2: trends ---------------------------------------------
    trends = [t for t in (_trend_for(readings, m) for m in MEASURES) if t is not None]
    if trends:
        moving = [t for t in trends if t.direction != "steady"]
        steady = [t for t in trends if t.direction == "steady"]

        sentences = [_describe(t, first) for t in moving[:2]]
        if steady:
            joined = _join([t.measure.label for t in steady[:3]])
            if sentences:
                # "Everything else" only makes sense when something *is* moving.
                sentences.append(f"Everything else has held steady, including {first}'s {joined}.")
            else:
                sentences.append(f"{first}'s {joined} have all held steady.")

        paragraphs.append(" ".join(sentences))

        for trend in moving[:2]:
            highlights.append(
                {
                    "tone": trend.tone,
                    "text": f"{trend.measure.label.capitalize()} "
                            f"{'up' if trend.direction == 'up' else 'down'}",
                }
            )
        for trend in steady[:2]:
            highlights.append(
                {"tone": "good", "text": f"{trend.measure.label.capitalize()} steady"}
            )

    if flagged_readings:
        n = len(flagged_readings)
        if n == 1:
            paragraphs.append(
                f"One of those readings was outside the range we watch for {first}, so a "
                "nurse looked at it again."
            )
        else:
            paragraphs.append(
                f"{n} of those readings were outside the range we watch for {first}, so a "
                "nurse looked at them again."
            )

    # -- Paragraph 3: medicines ------------------------------------------
    if doses["total"]:
        taken, total, pct = doses["administered"], doses["total"], doses["percentage"]
        if pct >= 90:
            verdict = "which is very good"
        elif pct >= 80:
            verdict = "which is good"
        elif pct >= 65:
            verdict = "so a few were missed"
        else:
            verdict = "so several were missed, which is worth asking your nurse about"
        paragraphs.append(
            f"{first} took {taken} of the {total} medicine doses the nurse recorded in "
            f"{window_label}, {verdict}."
        )
        highlights.append(
            {
                "tone": "good" if pct >= 80 else "watch",
                "text": f"{taken} of {total} doses taken",
            }
        )
    else:
        paragraphs.append(
            f"No medicine doses were recorded for {first} in {window_label}."
        )

    # -- Paragraph 4: visits and what the team did ------------------------
    care: list[str] = []
    if completed_visits:
        n = len(completed_visits)
        care.append(f"A nurse completed {n} home {_plural(n, 'visit')} in {window_label}.")
    if closed_alerts:
        n = len(closed_alerts)
        care.append(
            f"{n} {_plural(n, 'reading')} we flagged {_plural(n, 'has', 'have')} since been "
            "reviewed and closed."
        )
    if open_alerts:
        n = len(open_alerts)
        care.append(
            f"{n} {_plural(n, 'reading')} {_plural(n, 'is', 'are')} still with the care team."
        )
        highlights.append(
            {"tone": "attention", "text": f"{n} still being reviewed"}
        )
    if next_visit is not None:
        care.append(
            f"The next visit is on {_weekday(next_visit.scheduled_at)} at "
            f"{_clock(next_visit.scheduled_at)}."
        )
    if care:
        paragraphs.append(" ".join(care))

    # -- What happens next -------------------------------------------------
    if open_alerts:
        next_steps.append(
            "The DoorDoctor care team is reviewing the readings we flagged and will call "
            "you if anything changes."
        )
    if next_visit is not None:
        next_steps.append(
            f"{first}'s next nurse visit is on {_weekday(next_visit.scheduled_at)} at "
            f"{_clock(next_visit.scheduled_at)}."
        )
    else:
        next_steps.append(
            "No visit is booked yet — we will be in touch to schedule the next one."
        )
    next_steps.append(
        "You can ask the nurse anything at the next visit, or call DoorDoctor at any time."
    )

    # Four chips at most, worst first — a row of nine is a wall, not a summary.
    tone_order = {"attention": 0, "watch": 1, "good": 2}
    highlights.sort(key=lambda h: tone_order.get(h["tone"], 3))

    return {
        "patient_id": patient.id,
        "patient_name": patient.name,
        "window": window,
        "window_label": window_label,
        "headline": headline,
        "paragraphs": paragraphs,
        "highlights": highlights[:4],
        "what_happens_next": next_steps,
        "reading_count": len(readings),
        "dose_count": doses["total"],
        "visit_count": len(completed_visits),
        "flagged_count": len(flagged_readings),
        "open_alert_count": len(open_alerts),
        "generated_at": generated_at,
        "source": "deterministic",
        "disclaimer": DISCLAIMER.format(first_name=first),
    }


# --------------------------------------------------------------------------
# The optional rewrite
# --------------------------------------------------------------------------

SYSTEM_PROMPT: Final = """\
You rewrite home-care health updates so a worried family member can read them \
easily. You are given an update that is already factually correct.

Rules, all of them absolute:
- Keep every fact exactly as given. Do not add, remove or change any number.
- Never introduce a number that is not already in the text.
- Never use these words: systolic, diastolic, SpO2, adherence, threshold, \
breach, vitals, metric, escalation.
- Never diagnose, never give medical advice, never mention medication changes.
- Warm, calm, plain English. Short sentences. No bullet points, no headings.
- Do not add a greeting, a sign-off, or any commentary about your task.

Return the one-sentence headline on the first line, then the paragraphs, \
separated by blank lines. Return nothing else."""

# A summary that has drifted into advice has stopped being a summary.
FORBIDDEN_REGISTER: Final[tuple[str, ...]] = (
    "diagnos",
    "prescri",
    "should stop taking",
    "you must",
    "i recommend",
    "we recommend",
    "emergency room",
)

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def numbers_in(text: str) -> set[str]:
    """Every number appearing in `text`.

    Public because the assistant's "no claim outside the context pack" gate is
    the same idea as this module's "no invented number" gate, and one regex for
    both is what keeps them from drifting apart.
    """
    return set(_NUMBER.findall(text))


def _rewrite_is_acceptable(rewrite: str, source: str) -> bool:
    """The four gates between a model's output and a family member's eyes.

    Ordered cheapest-first. Gate 2 is the one that matters: a model cannot
    invent a blood pressure reading if a digit it was not given is grounds for
    rejection.
    """
    banned = contains_clinical_language(rewrite)
    if banned is not None:
        logger.info("Discarding rewrite: reintroduced the word %r", banned)
        return False

    invented = numbers_in(rewrite) - numbers_in(source)
    if invented:
        logger.info("Discarding rewrite: %d number(s) not present in the source", len(invented))
        return False

    if not (0.5 * len(source) <= len(rewrite) <= 2.0 * len(source)):
        logger.info("Discarding rewrite: length %d against a source of %d", len(rewrite), len(source))
        return False

    lowered = rewrite.lower()
    for phrase in FORBIDDEN_REGISTER:
        if phrase in lowered:
            logger.info("Discarding rewrite: drifted into advice (%r)", phrase)
            return False

    return True


def _source_text(payload: dict[str, Any]) -> str:
    return "\n\n".join([payload["headline"], *payload["paragraphs"]])


def _assist(payload: dict[str, Any]) -> dict[str, Any]:
    """Try to warm up the wording. Returns `payload` unchanged on any doubt.

    Only the headline and the paragraphs are ever rewritten. The highlights and
    the next steps carry tones and drive UI, and handing a model something the
    interface depends on is a larger surface than this feature needs.
    """
    if not llm_client.available():
        return payload

    source = _source_text(payload)
    rewrite = llm_client.complete(
        system=SYSTEM_PROMPT,
        user=source,
        timeout=llm_client.SUMMARY_TIMEOUT,
        max_tokens=500,
    )
    if rewrite is None or not _rewrite_is_acceptable(rewrite, source):
        return payload

    blocks = [block.strip() for block in rewrite.split("\n\n") if block.strip()]
    if len(blocks) < 2:
        return payload

    return {
        **payload,
        "headline": " ".join(blocks[0].split()),
        "paragraphs": blocks[1:],
        "source": "assisted",
    }


# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------


class _SummaryCache:
    """15 minutes per patient per window, invalidated by content.

    The TTL alone would keep serving the last quarter-hour's paragraph after a
    nurse records a new reading. Keying on a fingerprint of the deterministic
    text as well makes new data bust the cache immediately, which turns the TTL
    into a cost control rather than a correctness risk.

    Process-global with a lock, and `reset()` exists for the same reason
    `core.ratelimit.limiter.reset()` does: without it, test order decides test
    outcomes.
    """

    def __init__(self, ttl_seconds: float = 900.0) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._entries: dict[tuple[int, str], tuple[str, float, dict[str, Any]]] = {}

    def get(self, key: tuple[int, str], fingerprint: str) -> dict[str, Any] | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            cached_fingerprint, expires_at, payload = entry
            if cached_fingerprint != fingerprint or time.monotonic() >= expires_at:
                del self._entries[key]
                return None
            return payload

    def put(self, key: tuple[int, str], fingerprint: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._entries[key] = (fingerprint, time.monotonic() + self._ttl, payload)

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()


cache = _SummaryCache()


def _fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_source_text(payload).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------


def plain_summary(
    db: Session, patient: Patient, window: str = DEFAULT_WINDOW, *, assist: bool = True
) -> dict[str, Any]:
    """A summary a family member can read.

    The deterministic generator always runs — it is the product, and it is also
    what the cache key and every validation gate are measured against. The
    rewrite is attempted only when a provider is configured, and its failure is
    invisible to the reader by design.
    """
    if window not in WINDOWS:
        window = DEFAULT_WINDOW

    payload = build_deterministic(db, patient, window)
    if not assist or not llm_client.available():
        return payload

    key = (patient.id, window)
    fingerprint = _fingerprint(payload)

    cached = cache.get(key, fingerprint)
    if cached is not None:
        return cached

    assisted = _assist(payload)
    cache.put(key, fingerprint, assisted)
    return assisted
