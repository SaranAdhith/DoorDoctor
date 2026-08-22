"""Every clinical constant this platform applies, in one file.

The sibling of `core/pricing.py`, and built to the same rule: it **imports
nothing from the application**, so models, services, routers, the seed and the
frontend's payloads all read *these* values, and nothing can circle back.

Provenance
----------
The build prompt is the source of truth. §4.2–4.9 — the clinical section — was
**never supplied**, exactly as §3 (Phase 4) and §2.3's intent list (Phase 7)
were not. The founder's decision on 2026-08-22 was to proceed and mark what was
invented, so:

* ``RECORDED``   — stated in the build prompt or the plan file. Enforce as-is.
* ``INSTRUMENT`` — comes from a published clinical instrument (PHQ-2). Not mine
                   to change, and **not** an assumption for the founder to
                   reconcile away.
* ``ASSUMED``    — invented here. Listed in ``docs/build-log/STATE.md``.
                   Reconciling the real §4 is an edit to *this file* and nothing
                   else.

Nothing outside this module may restate a weight, a reference range, an SLA or a
threshold. `services/safety_score.py` in particular contains no numbers at all —
it is arithmetic over `SAFETY_WEIGHTS`.

None of this is a clinical decision system. Reference ranges are here so a
flagged result can be *explained*, not so the platform can diagnose anybody.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping

# --------------------------------------------------------------------------
# Senior Safety Score — RECORDED: deterministic, 0–100, a 10+ point drop in
# 30 days raises an alert. Every weight and band below is ASSUMED.
# --------------------------------------------------------------------------

SCORE_MIN: Final = 0
SCORE_MAX: Final = 100


@dataclass(frozen=True)
class ComponentSpec:
    """One weighted input to the score.

    `label` and `blurb` are family-facing. A score nobody can have explained to
    them is worse than no score, so every component ships with the sentence that
    explains it rather than leaving the UI to invent one.
    """

    key: str
    label: str
    weight: int
    blurb: str


# ASSUMED in full. The weights must sum to 100 — `test_safety_score.py` re-runs
# that sum, so an edit here cannot silently produce a 94-point scale.
SAFETY_COMPONENTS: Final[tuple[ComponentSpec, ...]] = (
    ComponentSpec(
        "vital_stability",
        "Readings in range",
        30,
        "How often recorded checks sat inside the range set for this patient.",
    ),
    ComponentSpec(
        "medication_adherence",
        "Medicines taken",
        25,
        "The share of scheduled doses that were taken.",
    ),
    ComponentSpec(
        "care_continuity",
        "Visits completed",
        15,
        "How many planned nurse visits actually happened.",
    ),
    ComponentSpec(
        "alert_burden",
        "Quiet period",
        15,
        "How few things needed the care team's attention.",
    ),
    ComponentSpec(
        "mood",
        "Mood check",
        10,
        "The most recent two-question mood check.",
    ),
    ComponentSpec(
        "connected_monitoring",
        "Home monitoring",
        5,
        "Whether a connected device has been sending readings.",
    ),
)

SAFETY_COMPONENTS_BY_KEY: Final[Mapping[str, ComponentSpec]] = MappingProxyType(
    {c.key: c for c in SAFETY_COMPONENTS}
)

SAFETY_WEIGHTS: Final[Mapping[str, int]] = MappingProxyType(
    {c.key: c.weight for c in SAFETY_COMPONENTS}
)

# The window the score looks back over. ASSUMED.
SAFETY_WINDOW_DAYS: Final = 30

# RECORDED: a drop of this many points inside this many days raises an alert.
SAFETY_DROP_POINTS: Final = 10
SAFETY_DROP_WINDOW_DAYS: Final = 30

# Below this much of the total weight, there is not enough data to publish a
# score at all. ASSUMED — without it, a brand-new patient scores on medication
# adherence alone and the number looks authoritative.
SAFETY_MIN_COVERED_WEIGHT: Final = 40

# A patient must have at least this many readings before vital stability counts.
SAFETY_MIN_READINGS: Final = 3  # ASSUMED

# How far back the mood component will accept a screening. Wider than the
# screening cadence on purpose — one missed month must not blank the
# component and silently reweight the whole score.
SAFETY_MOOD_LOOKBACK_DAYS: Final = 90  # ASSUMED

# How many alerts in the window take the "quiet period" component to zero.
SAFETY_ALERT_SATURATION: Final = 6  # ASSUMED
# A critical alert weighs this much more than a warning when counting burden.
SAFETY_CRITICAL_MULTIPLIER: Final = 2  # ASSUMED


@dataclass(frozen=True)
class BandSpec:
    """A score band. `tone` matches the Phase 2 status tokens exactly."""

    key: str
    label: str
    tone: str  # good | watch | attention | critical
    floor: int
    blurb: str


# ASSUMED in full. Ordered high to low; `band_for` walks it and takes the first
# floor the score clears, so the boundaries cannot disagree with the lookup.
SAFETY_BANDS: Final[tuple[BandSpec, ...]] = (
    BandSpec("steady", "Steady", "good", 80, "Things have been going well."),
    BandSpec("watch", "Worth watching", "watch", 65, "A few things are worth keeping an eye on."),
    BandSpec(
        "attention",
        "Needs attention",
        "attention",
        50,
        "Several things need the care team's attention.",
    ),
    BandSpec(
        "concern",
        "Care team involved",
        "critical",
        SCORE_MIN,
        "The care team is actively involved.",
    ),
)


def band_for(score: int) -> BandSpec:
    """The band a score falls in. The only way anything should ask."""
    for band in SAFETY_BANDS:
        if score >= band.floor:
            return band
    return SAFETY_BANDS[-1]  # pragma: no cover - the last floor is SCORE_MIN


# --------------------------------------------------------------------------
# Lab panels — ASSUMED in full.
#
# RECORDED: a blood panel costs ₹499 (`core/pricing.ADD_ONS`), and an abnormal
# result raises an alert plus a 24-hour follow-up task. What a panel *contains*
# and which values are abnormal were not recorded.
#
# The reference ranges below are ordinary adult reference intervals. They are
# here so a flag can be **explained** — every result stores the range it was
# compared against, so "high" is arithmetic the reader can re-run, not an
# opinion. They are not a diagnostic rule and no treatment decision is derived
# from them anywhere in this codebase.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class AnalyteSpec:
    code: str
    label: str
    unit: str
    ref_low: float | None
    ref_high: float | None
    # Outside this, the result is flagged critical rather than merely abnormal.
    critical_low: float | None = None
    critical_high: float | None = None


@dataclass(frozen=True)
class PanelSpec:
    code: str
    name: str
    description: str
    # Which `core/pricing.ADD_ONS` entry bills this panel when the plan has no
    # allowance left. The price itself stays in pricing.py — this is a pointer.
    addon_code: str
    turnaround_hours: int
    analytes: tuple[AnalyteSpec, ...]


BASIC_PANEL: Final = PanelSpec(
    code="basic_health",
    name="Basic health panel",
    description="Blood sugar, haemoglobin and kidney function.",
    addon_code="blood_panel",
    turnaround_hours=24,  # ASSUMED
    analytes=(
        AnalyteSpec("fasting_glucose", "Fasting blood sugar", "mg/dL", 70, 110, 50, 250),
        AnalyteSpec("hba1c", "HbA1c", "%", None, 5.7, None, 9.0),
        AnalyteSpec("haemoglobin", "Haemoglobin", "g/dL", 12.0, 16.0, 7.0, None),
        AnalyteSpec("creatinine", "Creatinine", "mg/dL", 0.6, 1.3, None, 3.0),
        AnalyteSpec("urea", "Urea", "mg/dL", 15, 45, None, 100),
    ),
)

LIPID_PANEL: Final = PanelSpec(
    code="lipid",
    name="Lipid profile",
    description="Cholesterol and triglycerides.",
    addon_code="blood_panel",
    turnaround_hours=24,  # ASSUMED
    analytes=(
        AnalyteSpec("total_cholesterol", "Total cholesterol", "mg/dL", None, 200, None, 300),
        AnalyteSpec("ldl", "LDL cholesterol", "mg/dL", None, 130, None, 190),
        AnalyteSpec("hdl", "HDL cholesterol", "mg/dL", 40, None, 25, None),
        AnalyteSpec("triglycerides", "Triglycerides", "mg/dL", None, 150, None, 500),
    ),
)

THYROID_PANEL: Final = PanelSpec(
    code="thyroid",
    name="Thyroid panel",
    description="Thyroid stimulating hormone and free T4.",
    addon_code="blood_panel",
    turnaround_hours=48,  # ASSUMED
    analytes=(
        AnalyteSpec("tsh", "TSH", "mIU/L", 0.4, 4.5, 0.1, 10.0),
        AnalyteSpec("free_t4", "Free T4", "ng/dL", 0.8, 1.8, None, None),
    ),
)

LAB_PANELS: Final[tuple[PanelSpec, ...]] = (BASIC_PANEL, LIPID_PANEL, THYROID_PANEL)

LAB_PANELS_BY_CODE: Final[Mapping[str, PanelSpec]] = MappingProxyType(
    {p.code: p for p in LAB_PANELS}
)

# RECORDED: an abnormal lab raises an alert **and a 24-hour follow-up task**.
LAB_FOLLOW_UP_HOURS: Final = 24


# --------------------------------------------------------------------------
# Telemedicine — ASSUMED apart from the allowance itself.
#
# RECORDED (`core/pricing.py`): Premium includes 2 consults per month. Everything
# below — how long one runs, how late it can be cancelled, what a doctor is
# called — was not recorded.
# --------------------------------------------------------------------------

CONSULT_DURATION_MINUTES: Final = 20  # ASSUMED
# Cancel earlier than this and the allowance goes back. Later, it is spent.
CONSULT_CANCELLATION_HOURS: Final = 4  # ASSUMED
# How far ahead a consult may be booked.
CONSULT_MAX_LEAD_DAYS: Final = 30  # ASSUMED
CONSULT_MIN_LEAD_MINUTES: Final = 30  # ASSUMED

# No doctor roster is modelled in this build. A consult records the name it was
# booked under; there is no scheduling against a real person's calendar, and
# pretending otherwise would be inventing staff DoorDoctor does not have.
CONSULT_PLACEHOLDER_DOCTOR: Final = "DoorDoctor duty physician"  # ASSUMED


# --------------------------------------------------------------------------
# PHQ-2 — INSTRUMENT, not ASSUMED.
#
# The Patient Health Questionnaire-2 is a published, validated two-item
# depression screen. The wording, the four-point answer scale, the 0–6 total and
# the cutoff of 3 are the instrument's, not this project's. Reconciling §4 must
# not "correct" them.
#
# A positive screen means *screen further*. It is not a diagnosis and this
# platform never treats it as one — a positive PHQ-2 creates a follow-up task
# for a human, never an alert.
# --------------------------------------------------------------------------

PHQ2_INSTRUMENT: Final = "phq2"

PHQ2_PREAMBLE: Final = "Over the last 2 weeks, how often have you been bothered by the following problems?"

PHQ2_QUESTIONS: Final[tuple[str, ...]] = (
    "Little interest or pleasure in doing things",
    "Feeling down, depressed, or hopeless",
)

# 0–3 per item, so 0–6 in total.
PHQ2_ANSWERS: Final[tuple[tuple[int, str], ...]] = (
    (0, "Not at all"),
    (1, "Several days"),
    (2, "More than half the days"),
    (3, "Nearly every day"),
)

PHQ2_MAX_PER_ITEM: Final = 3
PHQ2_MAX_TOTAL: Final = PHQ2_MAX_PER_ITEM * len(PHQ2_QUESTIONS)
# The instrument's validated cutoff: 3 or more is a positive screen.
PHQ2_POSITIVE_CUTOFF: Final = 3

# How often to screen, and how soon to follow a positive screen up. ASSUMED —
# the instrument says nothing about cadence.
PHQ2_CADENCE_DAYS: Final = 30  # ASSUMED
PHQ2_FOLLOW_UP_HOURS: Final = 48  # ASSUMED


# --------------------------------------------------------------------------
# Wearables — the triggers are RECORDED, the range and the actions are ASSUMED.
#
# RECORDED (plan file §4.8): "SpO2 <90% or HR out of range → the documented
# three actions". The plan names those three actions and **never lists them**;
# §4.8 was not supplied. They are derived below and marked ASSUMED so the
# founder corrects all three in one place.
# --------------------------------------------------------------------------

WEARABLE_SPO2_FLOOR: Final = 90.0  # RECORDED
WEARABLE_HR_LOW: Final = 45.0  # ASSUMED
WEARABLE_HR_HIGH: Final = 120.0  # ASSUMED

# How many readings one ingest call may carry, and how far back one may be
# backdated. A device is the second least-trusted caller in this codebase after
# an anonymous lead form; both caps are ASSUMED.
WEARABLE_MAX_BATCH: Final = 50
WEARABLE_MAX_BACKDATE_HOURS: Final = 24
# A device that has not reported for this long is shown as offline.
WEARABLE_OFFLINE_AFTER_MINUTES: Final = 90  # ASSUMED


@dataclass(frozen=True)
class WearableAction:
    key: str
    label: str
    detail: str


# ASSUMED — all three. Derived from what the platform can actually do and from
# the recorded escalation ladder (108 → nurse → admin), not invented freely.
WEARABLE_ACTIONS: Final[tuple[WearableAction, ...]] = (
    WearableAction(
        "alert",
        "Raise a critical alert",
        "A critical alert is raised on the patient's record and shown to the family and the admin team.",
    ),
    WearableAction(
        "escalate",
        "Open an escalation and notify in parallel",
        "An escalation event opens and the family and the on-call admin are contacted at the same time "
        "on two channels, with every attempt recorded.",
    ),
    WearableAction(
        "task",
        "Task the assigned nurse to check in",
        "A follow-up task is created for the nurse who covers this patient, due inside the critical SLA.",
    ),
)


# --------------------------------------------------------------------------
# Escalation and SLA — the ladder is RECORDED, the durations are ASSUMED.
#
# RECORDED: 108 → nurse → admin. Phase 7 pinned that order in the assistant's
# emergency intent and it is not re-derived here; `ESCALATION_LADDER` states it
# once so the assistant, the UI block and the timeline cannot drift apart.
# --------------------------------------------------------------------------

EMERGENCY_NUMBER: Final = "108"  # RECORDED

ESCALATION_LADDER: Final[tuple[str, ...]] = (
    f"Call {EMERGENCY_NUMBER} for an ambulance",
    "Contact the assigned nurse",
    "Contact the DoorDoctor admin team",
)

# The permanent block every clinical screen carries. One string so the number
# and the wording cannot drift between eight screens.
EMERGENCY_BLOCK_TITLE: Final = f"In an emergency, call {EMERGENCY_NUMBER}"
# What the timeline's first step says. DoorDoctor does **not** dial 108 on
# anyone's behalf, and a timeline that implied it had would be the most
# consequential lie this product could tell — so the wording is fixed here and
# the step is recorded as advisory rather than as an action taken.
EMERGENCY_LADDER_ADVICE: Final = (
    f"call {EMERGENCY_NUMBER} for an ambulance. DoorDoctor does not place this call for you."
)

EMERGENCY_BLOCK_BODY: Final = (
    f"DoorDoctor monitors and coordinates care. It is not an emergency service. "
    f"If something is seriously wrong right now, call {EMERGENCY_NUMBER} for an ambulance first, "
    "then tell the assigned nurse or the DoorDoctor team."
)

# How long an escalation of each severity may sit before it has breached.
# ASSUMED in full — no SLA was recorded anywhere.
SLA_DURATIONS_MINUTES: Final[Mapping[str, int]] = MappingProxyType(
    {
        "critical": 15,  # ASSUMED
        "warning": 60,  # ASSUMED
        "info": 24 * 60,  # ASSUMED
    }
)

SLA_DEFAULT_MINUTES: Final = SLA_DURATIONS_MINUTES["warning"]


def sla_minutes_for(severity: str) -> int:
    """The SLA budget for a severity. Unknown severities get the middle band."""
    return SLA_DURATIONS_MINUTES.get(severity, SLA_DEFAULT_MINUTES)


# --------------------------------------------------------------------------
# Hospital booking — ASSUMED in full. Nothing about hospital coordination was
# recorded beyond that it exists.
# --------------------------------------------------------------------------

# No hospital partnerships exist — DoorDoctor is pre-launch and inventing a
# partner list would be inventing traction. A booking records the hospital the
# family or the admin *named*, and coordination is a human doing it.
HOSPITAL_BOOKING_SLA_MINUTES: Final = 60  # ASSUMED
AMBULANCE_SLA_MINUTES: Final = SLA_DURATIONS_MINUTES["critical"]  # ASSUMED


# --------------------------------------------------------------------------
# Follow-up tasks — ASSUMED in full apart from the lab's recorded 24 hours.
# --------------------------------------------------------------------------

TASK_DEFAULT_HOURS: Final = 24  # ASSUMED
# A task still open this long past due is surfaced as overdue in the queue.
TASK_OVERDUE_GRACE_MINUTES: Final = 0  # ASSUMED — due means due
