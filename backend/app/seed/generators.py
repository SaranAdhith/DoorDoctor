"""Deterministic generators: vitals trajectories, visit schedules, adherence.

Pure functions. Nothing here touches the database, the clock or the global
`random` module — every stream is drawn from a `random.Random` handed in by the
caller, seeded from `demo_data.RANDOM_SEED` plus the patient's slot. One library
somewhere else calling `random.seed()` would otherwise change the dataset, and a
"deterministic" seed that quietly is not is worse than an honestly random one.

Because these are pure, `tests/test_seed.py` calls them directly rather than
inferring their behaviour from rows in a database.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterable, Sequence

from . import demo_data

# --------------------------------------------------------------------------
# Vitals
# --------------------------------------------------------------------------

# Arcs, not noise. A ninety-day chart should have a *shape* a clinician can read
# at a glance; a random walk around a mean has none, and is the single thing
# that makes seeded health data look fake.
ARC_STABLE = "stable"
ARC_IMPROVING = "improving"  # started high, came down — a medication change that worked
ARC_DRIFTING = "drifting"  # creeping up across the window
ARC_EPISODIC = "episodic"  # flat, punctuated by discrete events

ARCS = (ARC_STABLE, ARC_IMPROVING, ARC_DRIFTING, ARC_EPISODIC)


@dataclass(frozen=True)
class Baseline:
    """Where a patient sits when nothing is happening to them."""

    systolic: float
    diastolic: float
    heart_rate: float
    glucose: float
    spo2: float
    temperature: float
    weight: float


# How far a metric may travel over the whole window, and how much it wobbles
# visit to visit. The wobble is comparable to the drift, which is true of real
# observations: day-to-day variation is as large as a slow trend, and the trend
# is only visible because it is monotone.
#
# These are sized against the *clamp* below, not chosen freely. A baseline plus
# its maximum swing has to stay inside the safe band, or the clamp truncates the
# top of the trajectory and the chart draws a flat line with the shape sheared
# off. The first version of this file did exactly that to 27% of systolic
# readings — see `test_generated_readings_are_not_pinned_to_the_clamp`.
_DRIFT = {
    "systolic": 10.0, "diastolic": 5.0, "heart_rate": 6.0, "glucose": 20.0,
    "spo2": 1.2, "temperature": 0.5, "weight": 1.8,
}
_WOBBLE = {
    "systolic": 3.5, "diastolic": 2.5, "heart_rate": 3.5, "glucose": 10.0,
    "spo2": 0.7, "temperature": 0.35, "weight": 0.4,
}

# Every generated reading is clamped this far inside the patient's configured
# range. That is what makes the alert count exact: a reading can only breach
# when `demo_data.EXCURSIONS` deliberately puts it out of range, so the seed
# never raises an alert nobody wrote down.
_SAFE_MARGIN = {
    "systolic_bp": 4.0, "diastolic_bp": 3.0, "heart_rate": 4.0, "blood_glucose": 8.0,
    "spo2": 1.0, "temperature": 0.4, "weight": 2.0,
}


def baseline_for(conditions: Sequence[str], age: int, rng: random.Random) -> Baseline:
    """A starting point that agrees with the patient's condition list.

    A patient recorded as diabetic whose glucose sits at 95 for ninety days is
    the kind of detail that tells an evaluator the data was invented.
    """
    systolic, diastolic = 120.0, 75.0
    heart_rate, glucose = 74.0, 102.0
    spo2, temperature = 97.2, 98.2
    weight = 62.0 + rng.uniform(-9, 14)

    # Everyone here is a patient *under treatment* — on amlodipine, on metformin,
    # on an inhaler. So these are controlled numbers that sit near the top of the
    # normal band, not the untreated numbers that would breach every week. A
    # baseline high enough to breach on its own would mean the seed's alert count
    # was decided by the clamp instead of by `demo_data.EXCURSIONS`.
    if "Hypertension" in conditions:
        systolic, diastolic = 126.0, 79.0
    if "Type 2 diabetes" in conditions:
        glucose = 143.0
    if "COPD" in conditions:
        spo2, heart_rate = 96.8, 82.0
    if "Congestive heart failure" in conditions:
        heart_rate, spo2 = 84.0, 96.9
    if "Atrial fibrillation" in conditions:
        heart_rate = 86.0
    if "Chronic kidney disease" in conditions:
        systolic, diastolic = 128.0, 80.0
    if "Anaemia" in conditions:
        heart_rate = 87.0
    if "Hypothyroidism" in conditions:
        heart_rate = 63.0

    # Systolic pressure rises with age; the rest is condition-led.
    systolic += max(0, age - 70) * 0.25

    return Baseline(
        systolic=systolic + rng.uniform(-3, 3),
        diastolic=diastolic + rng.uniform(-2, 2),
        heart_rate=heart_rate + rng.uniform(-4, 4),
        glucose=glucose + rng.uniform(-8, 8),
        spo2=spo2 + rng.uniform(-0.4, 0.4),
        temperature=temperature + rng.uniform(-0.3, 0.3),
        weight=weight,
    )


def arc_for(conditions: Sequence[str], rng: random.Random) -> str:
    """Pick the shape of the ninety days. Chronic conditions drift; the rest don't."""
    if {"COPD", "Congestive heart failure", "Chronic kidney disease"} & set(conditions):
        return rng.choice((ARC_DRIFTING, ARC_EPISODIC))
    if {"Hypertension", "Type 2 diabetes"} & set(conditions):
        return rng.choice((ARC_STABLE, ARC_IMPROVING, ARC_DRIFTING))
    return rng.choice((ARC_STABLE, ARC_STABLE, ARC_EPISODIC))


def _arc_position(arc: str, progress: float) -> float:
    """Where the trend sits at `progress` (0 = oldest reading, 1 = newest), in [-1, 1]."""
    if arc == ARC_IMPROVING:
        return 1.0 - 2.0 * progress
    if arc == ARC_DRIFTING:
        return -1.0 + 2.0 * progress
    if arc == ARC_EPISODIC:
        # Two slow swells across the window rather than a direction.
        return math.sin(progress * math.pi * 2.0) * 0.6
    return 0.0


def reading(
    baseline: Baseline,
    arc: str,
    step: int,
    total: int,
    phase: float,
    rng: random.Random,
) -> dict[str, float]:
    """One visit's readings: baseline + trend + a smooth wobble + a little jitter.

    The wobble is a sine over the visit index, not fresh noise per reading, so
    consecutive visits stay related to each other — which is what makes the line
    on the chart look like a person rather than a random number generator.
    """
    progress = step / max(1, total - 1)
    trend = _arc_position(arc, progress)
    swing = math.sin(step * 0.8 + phase)
    slow = math.sin(step * 0.23 + phase * 1.7)

    def value(name: str, base: float) -> float:
        return (
            base
            + _DRIFT[name] * trend * 0.5
            + _WOBBLE[name] * (swing * 0.6 + slow * 0.4)
            + rng.uniform(-1, 1) * _WOBBLE[name] * 0.18
        )

    return {
        "systolic_bp": value("systolic", baseline.systolic),
        "diastolic_bp": value("diastolic", baseline.diastolic),
        "heart_rate": value("heart_rate", baseline.heart_rate),
        "blood_glucose": value("glucose", baseline.glucose),
        "spo2": value("spo2", baseline.spo2),
        "temperature": value("temperature", baseline.temperature),
        # Weight drifts but does not wobble — a home scale is not that noisy.
        "weight": baseline.weight + _DRIFT["weight"] * _arc_position(arc, progress) * 0.5,
    }


def clamp_inside(values: dict[str, float], thresholds: dict[str, tuple[float, float]]) -> dict[str, float]:
    """Pull every reading safely inside the configured range, then round it.

    Rounding matters: a nurse writes down 128, not 127.6431. Temperature and
    weight keep one decimal because that is how they are actually measured.
    """
    out: dict[str, float] = {}
    for metric, raw in values.items():
        low, high = thresholds[metric]
        margin = _SAFE_MARGIN[metric]
        bounded = min(max(raw, low + margin), high - margin)
        out[metric] = round(bounded, 1) if metric in ("temperature", "weight") else float(round(bounded))
    return out


def apply_excursion(values: dict[str, float], kind: str) -> dict[str, float]:
    """Overwrite the metrics an excursion names. Everything else stays as measured."""
    return {**values, **demo_data.EXCURSION_KINDS[kind]}


# --------------------------------------------------------------------------
# Visit schedules
# --------------------------------------------------------------------------

# Which days of a seven-day cycle a patient is visited on, by weekly cadence.
# Spread rather than clustered, so a twice-weekly patient is seen Monday and
# Thursday and not on two consecutive days.
_WEEK_PATTERNS: dict[int, tuple[int, ...]] = {
    2: (0, 3),
    4: (0, 2, 4, 6),
    6: (0, 1, 2, 3, 4, 5),
}


@dataclass(frozen=True)
class ScheduledVisit:
    days_ago: int  # positive = past, negative = future
    hour: int
    minute: int
    status: str  # "completed" | "missed" | "cancelled" | "scheduled"


def visit_schedule(
    *,
    slot: int,
    per_week: int,
    history_days: int,
    forward_days: int,
    skip_recent_days: int,
    rng: random.Random,
) -> list[ScheduledVisit]:
    """Every visit for one patient, oldest first.

    `skip_recent_days` exists for exactly one patient: Lakshmi's last eight days
    are the hand-written Phase-4 history the test suite asserts against, so the
    generator fills in the ninety days *behind* them and stops.
    """
    pattern = _WEEK_PATTERNS[per_week]
    offset = slot % 7
    visits: list[ScheduledVisit] = []

    for days_ago in range(history_days, skip_recent_days, -1):
        if (days_ago + offset) % 7 not in pattern:
            continue
        hour, minute = demo_data.VISIT_SLOTS[(slot + len(visits)) % len(demo_data.VISIT_SLOTS)]
        roll = rng.random()
        if roll < demo_data.MISSED_RATE:
            status = "missed"
        elif roll < demo_data.MISSED_RATE + demo_data.CANCELLED_RATE:
            status = "cancelled"
        else:
            status = "completed"
        visits.append(ScheduledVisit(days_ago, hour, minute, status))

    # The forward book. Today is built explicitly elsewhere — its shape is
    # specified in §2.4 — so the generator starts at tomorrow.
    for ahead in range(1, forward_days + 1):
        days_ago = -ahead
        if (days_ago + offset) % 7 not in pattern:
            continue
        hour, minute = demo_data.VISIT_SLOTS[(slot + len(visits)) % len(demo_data.VISIT_SLOTS)]
        visits.append(ScheduledVisit(days_ago, hour, minute, "scheduled"))

    return visits


# --------------------------------------------------------------------------
# Adherence
# --------------------------------------------------------------------------

# §2.4 records a 62-98% spread. Deliberately wide: an operations screen where
# every patient is above 90% gives an admin nothing to act on.
ADHERENCE_MIN = 62
ADHERENCE_MAX = 98


# Slot 0 is Lakshmi, and 87% is the number the demo script and the README
# quote for her. The offset is chosen so the stride below lands her there
# instead of on whichever end of the band it happened to start at.
_ADHERENCE_OFFSET = 25


def adherence_target(slot: int) -> int:
    """A stable target per patient, spread evenly across the recorded range.

    Walked with a stride co-prime to the range rather than drawn randomly, so
    the twenty-eight patients actually cover the band instead of clustering
    wherever the generator happened to land.
    """
    span = ADHERENCE_MAX - ADHERENCE_MIN
    return ADHERENCE_MIN + (slot * 13 + _ADHERENCE_OFFSET) % (span + 1)


def adherence_plan(doses: int, target_percent: int) -> list[str]:
    """Dose outcomes that land on `target_percent`, with the misses spread out.

    Chosen by stride rather than by rolling a die per dose: a random draw hits
    the target only on average, and "on average" is not good enough for a number
    the family dashboard prints.
    """
    if doses <= 0:
        return []
    administered = round(doses * target_percent / 100)
    missed = doses - administered
    if missed <= 0:
        return ["administered"] * doses

    plan = ["administered"] * doses
    stride = doses / missed
    for index in range(missed):
        position = min(doses - 1, int(round(index * stride + stride / 2)))
        while plan[position] != "administered":  # collision on a short list
            position = (position + 1) % doses
        # Two skipped for every refused: a held dose is far more common than a
        # patient actually declining one.
        plan[position] = "refused" if index % 3 == 2 else "skipped"
    return plan


def cycle(values: Sequence, index: int):
    """Deterministic pick from a fixed list. Reads better than `[i % len(...)]` inline."""
    return values[index % len(values)]


def flatten(groups: Iterable[Iterable]) -> list:
    return [item for group in groups for item in group]


# --------------------------------------------------------------------------
# Locations (Phase 10, §4.11)
# --------------------------------------------------------------------------

# Roughly how many metres one degree of latitude covers. Longitude shrinks with
# latitude, and at Bangalore's 13°N the difference is about 2.5% — small enough
# that this is honest jitter for fictional addresses and not a survey.
_METRES_PER_DEGREE = 111_320.0


def home_coordinates(rng: random.Random, zone: int, *, max_offset_m: float = 700.0) -> tuple[float, float]:
    """A home a few hundred metres from its zone centre.

    Twenty-eight patients sharing one doorstep would make every geofence
    measurement identical, and the first out-of-range check-in in the demo would
    be indistinguishable from an arithmetic bug.
    """
    lat, lng = demo_data.ZONE_CENTRES[zone % len(demo_data.ZONE_CENTRES)]
    north = rng.uniform(-max_offset_m, max_offset_m)
    east = rng.uniform(-max_offset_m, max_offset_m)
    return (
        round(lat + north / _METRES_PER_DEGREE, 6),
        round(lng + east / (_METRES_PER_DEGREE * math.cos(math.radians(lat))), 6),
    )


def offset_coordinates(lat: float, lng: float, *, metres: float, bearing_deg: float) -> tuple[float, float]:
    """A point `metres` away from (lat, lng) on the given bearing.

    Used to place a check-in inside or outside the geofence on purpose, so the
    seeded classification is the output of the same arithmetic the live service
    runs rather than a value typed into a column.
    """
    bearing = math.radians(bearing_deg)
    north = metres * math.cos(bearing)
    east = metres * math.sin(bearing)
    return (
        round(lat + north / _METRES_PER_DEGREE, 6),
        round(lng + east / (_METRES_PER_DEGREE * math.cos(math.radians(lat))), 6),
    )
