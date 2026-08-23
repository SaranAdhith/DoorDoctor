"""The demo core: the three accounts, the one patient and the live demo path.

This is the Phase-4 dataset, carried across unchanged, and it is built by **both**
seed profiles. Everything the test suite asserts by hand lives here — patient 1
is Lakshmi, nurse 1 is Anitha, adherence is 13/15, today's 10:30 visit is
Anitha's and is left `scheduled` so an evaluator can run the 148/92 path live.

`population.py` builds *around* this, never instead of it. That is the whole
reason 183 existing tests pass untouched while the demo grows to 28 patients.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from ..core.security import hash_password
from ..database import now
from ..models import (
    Medication,
    MedicationLog,
    MedicationLogStatus,
    Nurse,
    NurseStatus,
    Patient,
    PatientStatus,
    PatientThreshold,
    User,
    UserRole,
    VerificationStatus,
    Visit,
    VisitStatus,
    Vital,
    VitalMetric,
)
from ..services import vitals_service
from . import demo_data, trust
from .demo_data import DEMO_PASSWORD, SKIP_REASONS

# Lakshmi's front door: the Koramangala zone centre itself. Every seeded
# check-in for her is placed a chosen number of metres from this point and then
# classified by `location_service`, so the demo's `verified` badge is the output
# of the live arithmetic rather than a string in a column.
LAKSHMI_HOME = demo_data.ZONE_CENTRES[demo_data.KORAMANGALA]

DEMO_USERS = [
    {
        "name": "Darren D'Souza",
        "email": "family@doordoctor.in",
        "phone": "+91 90000 00001",
        "role": UserRole.FAMILY,
    },
    {
        "name": "Anitha Kumar",
        "email": "nurse@doordoctor.in",
        "phone": "+91 90000 00002",
        "role": UserRole.NURSE,
    },
    {
        "name": "Ravi Menon",
        "email": "admin@doordoctor.in",
        "phone": "+91 90000 00003",
        "role": UserRole.ADMIN,
    },
]

# Historical readings, all inside the configured thresholds. The live demo
# supplies the out-of-range reading (148/92) through the nurse UI.
HISTORY = [
    # days_ago, systolic, diastolic, hr, glucose, spo2, temp, weight
    (8, 126, 78, 76, 104, 98, 98.0, 64.0),
    (6, 130, 80, 78, 108, 98, 98.1, 64.2),
    (4, 128, 82, 74, 110, 97, 98.2, 64.1),
    (2, 132, 84, 80, 109, 98, 98.0, 64.3),
]

# The generator fills in the ninety days behind HISTORY. Anything inside this
# window is hand-written and asserted, so it must be left alone.
CORE_HISTORY_DAYS = 8

# How far from Lakshmi's door each historical check-in was recorded, in metres.
# All well inside the 150 m geofence — Anitha does turn up. The distances differ
# so the demo shows a measurement rather than a constant, and index 2 has no
# location at all (§4.11's `unavailable`, the honest negative case).
CHECKIN_DISTANCES_M = (11.0, 34.0, 8.0, 62.0)
UNLOCATED_HISTORY_INDEX = 2

MEDICATIONS = [
    {"name": "Amlodipine", "dosage": "5 mg", "frequency": "Once daily", "scheduled_time": "08:00"},
    {"name": "Metformin", "dosage": "500 mg", "frequency": "Twice daily", "scheduled_time": "08:00"},
    {"name": "Atorvastatin", "dosage": "10 mg", "frequency": "Once daily", "scheduled_time": "20:00"},
]

THRESHOLDS = {
    VitalMetric.SYSTOLIC_BP: (90, 140),
    VitalMetric.DIASTOLIC_BP: (60, 90),
    VitalMetric.HEART_RATE: (50, 100),
    VitalMetric.BLOOD_GLUCOSE: (70, 180),
    VitalMetric.SPO2: (94, 100),
    VitalMetric.TEMPERATURE: (95, 100.4),
    VitalMetric.WEIGHT: (35, 120),
}

# Dose outcomes across the historical visits -> ~87% adherence.
# 13 administered / 15 logged doses = 87%.
ADHERENCE_PLAN = [
    ["administered", "administered", "administered"],
    ["administered", "skipped", "administered"],
    ["administered", "administered", "administered"],
    ["administered", "refused", "administered"],
]
EXTRA_ADHERENCE_DOSES = ["administered", "administered", "administered"]

# Lakshmi's demo visit. `tests/conftest.py::scheduled_visit_id` takes the first
# open visit on Anitha's board, so this must stay her only scheduled visit today
# — see `population.py`, which routes every other visit today to another nurse.
DEMO_VISIT_HOUR = 10
DEMO_VISIT_MINUTE = 30


_password_hash_cache: str | None = None


def demo_password_hash() -> str:
    """The bcrypt digest of `Demo@123`, computed once for every demo account.

    bcrypt costs **0.729 s per hash** on this machine. Thirty-five accounts would
    be twenty-five seconds of every seed run, and `tests/conftest.py` seeds a
    template database once per session, so the whole suite would pay it too.

    Every demo account shares the same published password, so the digest is
    computed once and reused. Identical `password_hash` values across accounts
    are acceptable *here* — the password is printed in STATE.md and on the login
    screen — and would not be acceptable in production, where the per-user salt
    is the entire point.
    """
    global _password_hash_cache
    if _password_hash_cache is None:
        _password_hash_cache = hash_password(DEMO_PASSWORD)
    return _password_hash_cache


def at(days_ago: int, hour: int = 10, minute: int = 30) -> datetime:
    """A wall-clock time on a day relative to today. Negative `days_ago` is future."""
    day = (now() - timedelta(days=days_ago)).date()
    return datetime.combine(day, time(hour=hour, minute=minute))


@dataclass
class CoreResult:
    family_user: User
    nurse_user: User
    admin_user: User
    nurse: Nurse
    patient: Patient
    today_visit: Visit


def build_core(db: Session) -> CoreResult:
    """The three accounts, Anitha, Lakshmi and the live demo path."""
    users: dict[UserRole, User] = {}
    for spec in DEMO_USERS:
        user = User(
            name=spec["name"],
            email=spec["email"],
            phone=spec["phone"],
            password_hash=demo_password_hash(),
            role=spec["role"],
            is_active=True,
        )
        db.add(user)
        users[spec["role"]] = user
    db.flush()

    nurse = Nurse(
        user_id=users[UserRole.NURSE].id,
        credential="RN/ANM",
        verification_status=VerificationStatus.VERIFIED,
        status=NurseStatus.ACTIVE,
        # --- Phase 10, the family-facing profile (§4.10) ------------------
        zone=demo_data.ZONES[demo_data.KORAMANGALA][0],
        joined_on=(now() - timedelta(days=980)).date(),
        languages=demo_data.LANGUAGES_BY_ZONE[demo_data.KORAMANGALA],
        years_experience=9,
        bio=(
            "Anitha has worked in home care across south Bengaluru since 2016 and "
            "has looked after Lakshmi since she joined DoorDoctor."
        ),
    )
    db.add(nurse)

    patient = Patient(
        name="Lakshmi D'Souza",
        age=68,
        gender="Female",
        address="4th Block, Koramangala, Bengaluru 560034",
        emergency_contact="Darren D'Souza (son) - +91 90000 00001",
        family_user_id=users[UserRole.FAMILY].id,
        status=PatientStatus.ACTIVE,
        # --- Phase 10, the geofence centre (§4.11) ------------------------
        # Fixed rather than jittered: every visit-location test in the suite
        # measures against these two numbers, and a home that moved between
        # seeds would make those tests measure the generator instead.
        zone=demo_data.ZONES[demo_data.KORAMANGALA][0],
        home_lat=LAKSHMI_HOME[0],
        home_lng=LAKSHMI_HOME[1],
    )
    db.add(patient)
    db.flush()

    # Anitha's licence and police check, verified by Ravi. This lives in the
    # core rather than in `population.py` because the family-facing nurse
    # profile is a demo screen and `SMALL` — which the test suite seeds — has to
    # be able to render it.
    trust.seed_credentials(
        db,
        nurse,
        verifier=users[UserRole.ADMIN],
        verified=True,
        today=now().date(),
        rng=random.Random(demo_data.RANDOM_SEED + 910),
    )

    for metric, (low, high) in THRESHOLDS.items():
        db.add(
            PatientThreshold(
                patient_id=patient.id,
                metric=metric,
                low_threshold=low,
                high_threshold=high,
                enabled=True,
            )
        )

    medications = [
        Medication(
            patient_id=patient.id,
            name=spec["name"],
            dosage=spec["dosage"],
            frequency=spec["frequency"],
            scheduled_time=spec["scheduled_time"],
            active=True,
        )
        for spec in MEDICATIONS
    ]
    db.add_all(medications)
    db.flush()

    # ---- historical completed visits -------------------------------------
    for index, (days_ago, sys_bp, dia_bp, hr, glucose, spo2, temp, weight) in enumerate(HISTORY):
        scheduled_at = at(days_ago)
        visit = Visit(
            patient_id=patient.id,
            nurse_id=nurse.id,
            scheduled_at=scheduled_at,
            status=VisitStatus.COMPLETED,
            checkin_at=scheduled_at,
            checkout_at=scheduled_at + timedelta(minutes=45),
            notes="Routine home visit completed. Patient comfortable and responsive.",
        )
        # One visit in the history has no location at all. A demo where every
        # check-in is verified teaches an evaluator that the badge is decoration;
        # the `unavailable` row is what proves it is a measurement.
        trust.locate_checkin(
            visit,
            home_lat=patient.home_lat,
            home_lng=patient.home_lng,
            metres=None if index == UNLOCATED_HISTORY_INDEX else CHECKIN_DISTANCES_M[index % len(CHECKIN_DISTANCES_M)],
            bearing_deg=(index * 47) % 360,
        )
        db.add(visit)
        db.flush()

        vital = Vital(
            patient_id=patient.id,
            visit_id=visit.id,
            systolic_bp=sys_bp,
            diastolic_bp=dia_bp,
            heart_rate=hr,
            blood_glucose=glucose,
            spo2=spo2,
            temperature=temp,
            weight=weight,
            recorded_at=scheduled_at + timedelta(minutes=12),
        )
        thresholds = list(patient.thresholds)
        vital.threshold_breached = bool(vitals_service.evaluate_thresholds(vital, thresholds))
        db.add(vital)

        for medication, status_value in zip(medications, ADHERENCE_PLAN[index]):
            db.add(
                MedicationLog(
                    medication_id=medication.id,
                    visit_id=visit.id,
                    status=MedicationLogStatus(status_value),
                    reason=SKIP_REASONS.get(status_value),
                    recorded_at=scheduled_at + timedelta(minutes=20),
                    recorded_by=users[UserRole.NURSE].id,
                )
            )

    # Three extra administered doses so adherence lands on 87%.
    for offset, status_value in enumerate(EXTRA_ADHERENCE_DOSES):
        db.add(
            MedicationLog(
                medication_id=medications[offset % len(medications)].id,
                visit_id=None,
                status=MedicationLogStatus(status_value),
                reason=None,
                recorded_at=at(7 - offset, hour=20, minute=0),
                recorded_by=users[UserRole.NURSE].id,
            )
        )

    # ---- today's visit, left scheduled for the live demo ------------------
    today_visit = Visit(
        patient_id=patient.id,
        nurse_id=nurse.id,
        scheduled_at=at(0, hour=DEMO_VISIT_HOUR, minute=DEMO_VISIT_MINUTE),
        status=VisitStatus.SCHEDULED,
    )
    db.add(today_visit)

    # ---- a second scheduled visit for admin screens -----------------
    db.add(
        Visit(
            patient_id=patient.id,
            nurse_id=nurse.id,
            scheduled_at=at(-2, hour=10, minute=30),
            status=VisitStatus.SCHEDULED,
        )
    )
    db.flush()

    return CoreResult(
        family_user=users[UserRole.FAMILY],
        nurse_user=users[UserRole.NURSE],
        admin_user=users[UserRole.ADMIN],
        nurse=nurse,
        patient=patient,
        today_visit=today_visit,
    )
