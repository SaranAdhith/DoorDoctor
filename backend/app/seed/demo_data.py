"""Every fixed roster the seed draws from. Data only — no logic, no database.

Names, addresses and organizations here are fictional. DoorDoctor is pre-launch:
nothing in this file is a real customer, a real nurse or a real facility.

Two rules keep this file honest:

* **Nothing here is random.** Randomness lives in `generators.py` and is always
  drawn from an explicitly seeded `random.Random`, never the global module.
* **Nothing here reads the clock.** Everything is expressed as an offset, so the
  dataset is the same shape on whatever day the demo is opened.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ..core import pricing

DEMO_PASSWORD: Final = "Demo@123"

# One fixed seed for the whole dataset. Generators derive their own streams from
# it (`RANDOM_SEED + slot`) so adding a patient cannot reshuffle the others.
RANDOM_SEED: Final = 20260822


# --------------------------------------------------------------------------
# Profiles
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SeedProfile:
    """How much of the business to build.

    `SMALL` is the Phase-4 dataset exactly, and is what `tests/conftest.py`
    seeds: 183 tests assert against it by hand (`total == 15` doses,
    `paid_months == 14`, `active_subscriptions == 4`). Those tests exercise the
    *application*, not the population, and rewriting them to tolerate 28
    patients would weaken them for nothing.

    `FULL` is `SMALL` plus the wider population — never a second construction of
    the same demo core.
    """

    name: str
    population: bool
    history_days: int = 90
    forward_days: int = 7


SMALL: Final = SeedProfile(name="small", population=False)
FULL: Final = SeedProfile(name="full", population=True)


# --------------------------------------------------------------------------
# Zones
#
# Six Bangalore areas. Patients live in one, nurses are rostered to one, and a
# visit is assigned to a nurse in the patient's zone — which is what makes a
# fourteen-nurse roster look like routed field work rather than a shuffled list.
#
# Phase 10 owns the zone view and the ~30-45 subscriber break-even. When it
# needs to *query* by zone, lift this table into a column on Patient and Nurse;
# it is deliberately not one yet, because a seed-data phase should not be where
# the schema grows a feature the next phase specifies.
# --------------------------------------------------------------------------

ZONES: Final[tuple[tuple[str, str], ...]] = (
    ("Koramangala", "560034"),
    ("Indiranagar", "560038"),
    ("Jayanagar", "560041"),
    ("HSR Layout", "560102"),
    ("Whitefield", "560066"),
    ("Malleshwaram", "560003"),
)

KORAMANGALA: Final = 0  # Lakshmi's zone, and Anitha's


# --------------------------------------------------------------------------
# Staff
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class NurseSpec:
    name: str
    email: str
    phone: str
    credential: str
    zone: int
    verified: bool = True
    active: bool = True


# Nurse 1 is Anitha Kumar and is created by `core.py`, not from this list — the
# suite asserts `nurse_id == 1` and the demo journey is hers.
EXTRA_NURSES: Final[tuple[NurseSpec, ...]] = (
    NurseSpec("Priyanka Rao", "priyanka.rao@doordoctor.in", "+91 90010 00002", "BSc Nursing", 0),
    NurseSpec("Asha Verghese", "asha.verghese@doordoctor.in", "+91 90010 00003", "GNM", 0),
    NurseSpec("Fathima Sheikh", "fathima.sheikh@doordoctor.in", "+91 90010 00004", "GNM", 1),
    NurseSpec("Sujatha Reddy", "sujatha.reddy@doordoctor.in", "+91 90010 00005", "RN", 1),
    NurseSpec("Kavya Nair", "kavya.nair@doordoctor.in", "+91 90010 00006", "BSc Nursing", 2),
    NurseSpec("Deepa Shetty", "deepa.shetty@doordoctor.in", "+91 90010 00007", "GNM", 2),
    NurseSpec("Reshma Pinto", "reshma.pinto@doordoctor.in", "+91 90010 00008", "RN", 3),
    NurseSpec("Nandini Gowda", "nandini.gowda@doordoctor.in", "+91 90010 00009", "ANM", 3),
    NurseSpec("Joseph Thomas", "joseph.thomas@doordoctor.in", "+91 90010 00010", "RN", 4),
    NurseSpec(
        "Shalini Bhat", "shalini.bhat@doordoctor.in", "+91 90010 00011", "BSc Nursing", 4,
        verified=False,  # newest hire, credential check still open
    ),
    NurseSpec("Vinod Kumar", "vinod.kumar@doordoctor.in", "+91 90010 00012", "GNM", 5),
    NurseSpec("Ramya Krishnan", "ramya.krishnan@doordoctor.in", "+91 90010 00013", "RN", 5),
    NurseSpec(
        "Manjula Devi", "manjula.devi@doordoctor.in", "+91 90010 00014", "ANM", 2,
        active=False,  # on extended leave — the directory should show a real roster, not an ideal one
    ),
)

# Admin 1 is Ravi Menon, created by `core.py`.
EXTRA_ADMINS: Final[tuple[tuple[str, str, str], ...]] = (
    ("Sneha Bhaskar", "sneha.bhaskar@doordoctor.in", "+91 90020 00002"),
    ("Arun Pillai", "arun.pillai@doordoctor.in", "+91 90020 00003"),
)


# --------------------------------------------------------------------------
# Families and patients
#
# Eighteen family accounts hold twenty-eight patients: ten families care for
# both parents, eight for one. Addresses are fictional and use the zone above.
#
# Family 1 is Darren D'Souza and patient 1 is Lakshmi D'Souza — both built by
# `core.py`. Family 2 is Meera Raghavan, who already exists to carry the
# referral story; Phase 5 gives her the parent she is subscribed for.
#
# `plan` decides the visit cadence as well as the price, so the schedule and the
# invoice agree with each other.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PatientSpec:
    name: str
    age: int
    gender: str
    street: str
    conditions: tuple[str, ...]


@dataclass(frozen=True)
class FamilySpec:
    name: str
    email: str
    phone: str
    zone: int
    plan_code: str
    tenure_months: int
    patients: tuple[PatientSpec, ...]
    annual: bool = False
    cancelling: bool = False
    lapsed: bool = False


# Meera's patient, attached to the account `core.py` already creates.
MEERA_PATIENT: Final = PatientSpec(
    "Raghavan Iyer", 74, "Male", "12, 5th Cross, Jayanagar 4th Block", ("Hypertension",)
)

EXTRA_FAMILIES: Final[tuple[FamilySpec, ...]] = (
    FamilySpec(
        "Nikhil Sharma", "nikhil.sharma@example.com", "+91 90030 00003", 0, pricing.PREMIUM.code, 15,
        (
            PatientSpec("Sushila Sharma", 79, "Female", "88, 6th Block, Koramangala", ("Type 2 diabetes", "Osteoarthritis")),
            PatientSpec("Mahesh Sharma", 82, "Male", "88, 6th Block, Koramangala", ("Hypertension", "Post-stroke care")),
        ),
    ),
    FamilySpec(
        "Anjali Menon", "anjali.menon@example.com", "+91 90030 00004", 1, pricing.CARE_PLUS.code, 13,
        (
            PatientSpec("Sarojini Menon", 71, "Female", "27, 12th Main, Indiranagar", ("Hypertension",)),
        ),
    ),
    FamilySpec(
        "Rakesh Gupta", "rakesh.gupta@example.com", "+91 90030 00005", 1, pricing.CARE_PLUS.code, 11,
        (
            PatientSpec("Kamla Gupta", 76, "Female", "5, Defence Colony, Indiranagar", ("Type 2 diabetes",)),
            PatientSpec("Om Prakash Gupta", 80, "Male", "5, Defence Colony, Indiranagar", ("COPD",)),
        ),
    ),
    FamilySpec(
        "Vidya Prasad", "vidya.prasad@example.com", "+91 90030 00006", 2, pricing.ESSENTIAL.code, 9,
        (
            PatientSpec("Girija Prasad", 68, "Female", "41, 9th Block, Jayanagar", ("Hypothyroidism",)),
            PatientSpec("Ramachandra Prasad", 75, "Male", "41, 9th Block, Jayanagar", ("Hypertension",)),
        ),
    ),
    FamilySpec(
        "Suresh Bhatt", "suresh.bhatt@example.com", "+91 90030 00007", 2, pricing.PREMIUM.code, 18,
        (
            PatientSpec("Shanta Bhatt", 84, "Female", "16, East End Road, Jayanagar", ("Dementia", "Hypertension")),
            PatientSpec("Ganesh Bhatt", 86, "Male", "16, East End Road, Jayanagar", ("Parkinson's disease",)),
        ),
    ),
    FamilySpec(
        "Farida Khan", "farida.khan@example.com", "+91 90030 00008", 3, pricing.CARE_PLUS.code, 7,
        (
            PatientSpec("Zubeida Khan", 73, "Female", "302, Sector 2, HSR Layout", ("Type 2 diabetes", "Hypertension")),
        ),
    ),
    FamilySpec(
        "Arvind Rao", "arvind.rao@example.com", "+91 90030 00009", 3, pricing.CARE_PLUS.code, 12,
        (
            PatientSpec("Padma Rao", 77, "Female", "19, Sector 6, HSR Layout", ("Chronic kidney disease",)),
            PatientSpec("Krishna Rao", 81, "Male", "19, Sector 6, HSR Layout", ("Hypertension", "Type 2 diabetes")),
        ),
    ),
    FamilySpec(
        "Shalini Iyer", "shalini.iyer@example.com", "+91 90030 00010", 4, pricing.ESSENTIAL.code, 4,
        (
            PatientSpec("Vasanthi Iyer", 70, "Female", "7, Palm Meadows, Whitefield", ("Osteoporosis",)),
        ),
    ),
    FamilySpec(
        "Deepak Nayar", "deepak.nayar@example.com", "+91 90030 00011", 4, pricing.PREMIUM.code, 16,
        (
            PatientSpec("Rukmini Nayar", 83, "Female", "22, Whitefield Main Road", ("Congestive heart failure",)),
            PatientSpec("Balan Nayar", 85, "Male", "22, Whitefield Main Road", ("COPD", "Hypertension")),
        ),
    ),
    FamilySpec(
        # NRI account — the son is in Dubai, which is exactly who §2.6 is written for.
        "Rohit Verma", "rohit.verma@example.com", "+971 50 000 0012", 5, pricing.PREMIUM.code, 10,
        (
            PatientSpec("Sulochana Verma", 78, "Female", "3, Sampige Road, Malleshwaram", ("Hypertension", "Atrial fibrillation")),
        ),
        annual=True,
    ),
    FamilySpec(
        "Latha Srinivasan", "latha.srinivasan@example.com", "+91 90030 00013", 5, pricing.CARE_PLUS.code, 6,
        (
            PatientSpec("Meenakshi Srinivasan", 75, "Female", "48, 8th Cross, Malleshwaram", ("Type 2 diabetes",)),
            PatientSpec("Srinivasan Iyengar", 79, "Male", "48, 8th Cross, Malleshwaram", ("Benign prostatic hyperplasia",)),
        ),
    ),
    FamilySpec(
        "Imran Qureshi", "imran.qureshi@example.com", "+91 90030 00014", 0, pricing.ESSENTIAL.code, 3,
        (
            PatientSpec("Nafisa Qureshi", 69, "Female", "14, 1st Block, Koramangala", ("Anaemia",)),
        ),
    ),
    FamilySpec(
        "Geeta Kulkarni", "geeta.kulkarni@example.com", "+91 90030 00015", 1, pricing.ESSENTIAL.code, 2,
        (
            PatientSpec("Vasudha Kulkarni", 72, "Female", "9, CMH Road, Indiranagar", ("Hypertension",)),
            PatientSpec("Anant Kulkarni", 74, "Male", "9, CMH Road, Indiranagar", ("Type 2 diabetes",)),
        ),
    ),
    FamilySpec(
        # Asked to stop at the end of the paid period. Care runs to the 30th.
        "Prakash Hegde", "prakash.hegde@example.com", "+91 90030 00016", 2, pricing.ESSENTIAL.code, 5,
        (
            PatientSpec("Sharada Hegde", 76, "Female", "33, 4th T Block, Jayanagar", ("Osteoarthritis",)),
        ),
        cancelling=True,
    ),
    FamilySpec(
        # This month's invoice is unpaid — the revenue screen needs a real
        # outstanding balance, not a hypothetical one.
        "Sanjay Dutta", "sanjay.dutta@example.com", "+91 90030 00017", 3, pricing.CARE_PLUS.code, 8,
        (
            PatientSpec("Aparna Dutta", 70, "Female", "57, Sector 7, HSR Layout", ("Hypertension", "Hypothyroidism")),
            PatientSpec("Bimal Dutta", 77, "Male", "57, Sector 7, HSR Layout", ("Type 2 diabetes",)),
        ),
        lapsed=True,
    ),
    FamilySpec(
        "Kiran Joshi", "kiran.joshi@example.com", "+91 90030 00018", 4, pricing.CARE_PLUS.code, 1,
        (
            PatientSpec("Indira Joshi", 67, "Female", "11, Varthur Road, Whitefield", ("Type 2 diabetes",)),
            PatientSpec("Dattatreya Joshi", 73, "Male", "11, Varthur Road, Whitefield", ("Hypertension",)),
        ),
    ),
)


# --------------------------------------------------------------------------
# Medications
#
# Drawn by condition, so a patient with diabetes is on metformin and a patient
# with heart failure is on furosemide. A random draw from one list would put
# levothyroxine on a COPD patient, and a clinician looking at the demo would see
# it immediately.
# --------------------------------------------------------------------------

MEDICATIONS_BY_CONDITION: Final[dict[str, tuple[tuple[str, str, str, str], ...]]] = {
    "Hypertension": (("Amlodipine", "5 mg", "Once daily", "08:00"),),
    "Type 2 diabetes": (
        ("Metformin", "500 mg", "Twice daily", "08:00"),
        ("Glimepiride", "1 mg", "Once daily", "08:00"),
    ),
    "COPD": (("Tiotropium inhaler", "18 mcg", "Once daily", "09:00"),),
    "Hypothyroidism": (("Levothyroxine", "50 mcg", "Once daily", "07:00"),),
    "Osteoarthritis": (("Paracetamol", "500 mg", "Twice daily", "09:00"),),
    "Osteoporosis": (("Cholecalciferol", "1000 IU", "Once daily", "09:00"),),
    "Dementia": (("Donepezil", "5 mg", "Once daily", "20:00"),),
    "Parkinson's disease": (("Levodopa-Carbidopa", "100/25 mg", "Thrice daily", "08:00"),),
    "Congestive heart failure": (("Furosemide", "40 mg", "Once daily", "08:00"),),
    "Atrial fibrillation": (("Apixaban", "5 mg", "Twice daily", "08:00"),),
    "Chronic kidney disease": (("Sodium bicarbonate", "500 mg", "Twice daily", "08:00"),),
    "Post-stroke care": (("Clopidogrel", "75 mg", "Once daily", "20:00"),),
    "Benign prostatic hyperplasia": (("Tamsulosin", "0.4 mg", "Once daily", "20:00"),),
    "Anaemia": (("Ferrous ascorbate", "100 mg", "Once daily", "09:00"),),
}

# Everyone over 65 in this programme is on a statin. Keeps every patient on at
# least two medications, which is what a real adherence chart looks like.
BASELINE_MEDICATION: Final = ("Atorvastatin", "10 mg", "Once daily", "20:00")


# --------------------------------------------------------------------------
# Visit cadence
#
# Per month, by plan. The recorded §2.4 dataset is ~1,400 visits over 90 days
# for 28 patients — 16.7 visits per patient per month — so these cadences follow
# the *recorded volume*, not the Phase-4 entitlements (4 / 8 / 12), which are
# marked ASSUMED in `core/pricing.py`. See STATE.md: the gap between the two is
# evidence about the real §3, and is why quota enforcement stays deferred.
# --------------------------------------------------------------------------

VISITS_PER_WEEK: Final[dict[str, int]] = {
    pricing.ESSENTIAL.code: 2,   # twice weekly
    pricing.CARE_PLUS.code: 4,   # alternate day
    pricing.PREMIUM.code: 6,     # near daily
}

# Visit slot times, cycled per patient so a nurse's day is not eight visits at
# 10:30. Morning-weighted, which is when home care actually happens.
VISIT_SLOTS: Final[tuple[tuple[int, int], ...]] = (
    (7, 30), (8, 15), (9, 0), (9, 45), (10, 30), (11, 15),
    (12, 0), (15, 30), (16, 15), (17, 0), (17, 45),
)

# A visit that did not happen. Roughly 3% of the past window between them, which
# is what an honest operations screen shows.
MISSED_RATE: Final = 0.02
CANCELLED_RATE: Final = 0.015


# --------------------------------------------------------------------------
# Excursions — the entire alert story, as data
#
# Exactly 34 entries: 30 that were resolved and 4 still open. Each names a
# patient slot (an index into the flattened patient list built by
# `population.py`), how many visits back from that patient's most recent one it
# happened, and which excursion kind to apply.
#
# The alerts themselves are raised by `alert_service.create_threshold_alert` —
# the real threshold engine over the real readings. Nothing writes an Alert row
# by hand, so "every breaching reading has an alert" holds in the seed for the
# same reason it holds in production, and `test_seed.py` asserts it.
#
# Slot 0 is Lakshmi. She may appear here only with `resolved=True`: the suite
# asserts her dashboard returns to `Stable` once the alert a test raises is
# resolved, so she must carry no open alert out of the seed.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Excursion:
    patient_slot: int
    visits_back: int  # 0 = the most recent completed visit
    kind: str
    resolved: bool = True


# What each kind does to a reading. Values are chosen to sit clearly outside the
# default thresholds (90-140 / 60-90 / 50-100 / 70-180 / 94-100 / 95-100.4).
EXCURSION_KINDS: Final[dict[str, dict[str, float]]] = {
    "bp_high": {"systolic_bp": 152, "diastolic_bp": 94},
    "bp_very_high": {"systolic_bp": 168, "diastolic_bp": 101},
    "bp_low": {"systolic_bp": 86, "diastolic_bp": 55},
    "glucose_high": {"blood_glucose": 232},
    "glucose_low": {"blood_glucose": 61},
    "fever": {"temperature": 101.4, "heart_rate": 104},
    "spo2_dip": {"spo2": 91},
    "tachycardia": {"heart_rate": 112},
    "bradycardia": {"heart_rate": 46},
}

EXCURSIONS: Final[tuple[Excursion, ...]] = (
    # --- the four still open -------------------------------------------------
    Excursion(3, 0, "bp_very_high", resolved=False),   # Mahesh Sharma - post-stroke, drifting up
    Excursion(6, 0, "spo2_dip", resolved=False),       # Om Prakash Gupta - COPD
    Excursion(13, 0, "glucose_high", resolved=False),  # Krishna Rao - type 2 diabetes
    Excursion(15, 1, "fever", resolved=False),         # Rukmini Nayar - heart failure
    # --- thirty resolved, each matched to what the patient is actually on ----
    Excursion(0, 12, "bp_high"),          # Lakshmi D'Souza - resolved only, never open
    Excursion(0, 30, "glucose_high"),
    Excursion(1, 9, "bp_high"),           # Raghavan Iyer
    Excursion(2, 14, "glucose_high"),     # Sushila Sharma
    Excursion(3, 22, "bp_high"),          # Mahesh Sharma
    Excursion(4, 18, "bp_high"),          # Sarojini Menon
    Excursion(5, 11, "glucose_high"),     # Kamla Gupta
    Excursion(5, 33, "glucose_low"),
    Excursion(6, 25, "spo2_dip"),         # Om Prakash Gupta
    Excursion(7, 7, "bradycardia"),       # Girija Prasad - hypothyroid
    Excursion(8, 15, "bp_high"),          # Ramachandra Prasad
    Excursion(9, 30, "bp_high"),          # Shanta Bhatt
    Excursion(10, 20, "bradycardia"),     # Ganesh Bhatt - Parkinson's
    Excursion(11, 13, "glucose_high"),    # Zubeida Khan
    Excursion(11, 38, "bp_high"),
    Excursion(12, 27, "bp_low"),          # Padma Rao - chronic kidney disease
    Excursion(13, 19, "bp_high"),         # Krishna Rao
    Excursion(14, 10, "bp_low"),          # Vasanthi Iyer - fall risk
    Excursion(15, 24, "spo2_dip"),        # Rukmini Nayar
    Excursion(16, 16, "spo2_dip"),        # Balan Nayar - COPD
    Excursion(16, 44, "bp_high"),
    Excursion(17, 29, "tachycardia"),     # Sulochana Verma - atrial fibrillation
    Excursion(18, 21, "glucose_high"),    # Meenakshi Srinivasan
    Excursion(19, 12, "bp_low"),          # Srinivasan Iyengar - on tamsulosin
    Excursion(20, 8, "tachycardia"),      # Nafisa Qureshi - anaemia
    Excursion(21, 6, "bp_high"),          # Vasudha Kulkarni
    Excursion(22, 11, "glucose_high"),    # Anant Kulkarni
    Excursion(23, 17, "fever"),           # Sharada Hegde
    Excursion(24, 14, "bp_high"),         # Aparna Dutta
    Excursion(25, 9, "glucose_high"),     # Bimal Dutta
)


# --------------------------------------------------------------------------
# Today's board — 6 scheduled / 1 unassigned / 1 in-progress (§2.4)
#
# Built explicitly rather than by the cadence generator, because its shape is
# specified. The seven completed slots fill the day out to the ~15 visits the
# 90-day rate implies, so today does not read as a quiet day.
#
# Lakshmi's 10:30 with Anitha is created by `core.py` and is the only *scheduled*
# visit Anitha holds: `tests/conftest.py::scheduled_visit_id` takes the first
# open visit on her board, and a second one would silently point the alert tests
# at another patient.
# --------------------------------------------------------------------------

TODAY_COMPLETED_TIMES: Final[tuple[tuple[int, int], ...]] = (
    (7, 0), (7, 45), (8, 15), (8, 45), (9, 15), (9, 30), (10, 0),
)
TODAY_IN_PROGRESS_TIME: Final[tuple[int, int]] = (10, 15)
TODAY_UNASSIGNED_TIME: Final[tuple[int, int]] = (11, 0)
# Five more scheduled alongside Lakshmi's 10:30, for six in total.
TODAY_SCHEDULED_TIMES: Final[tuple[tuple[int, int], ...]] = (
    (11, 45), (12, 30), (15, 0), (16, 30), (17, 30),
)


# --------------------------------------------------------------------------
# Alert handling times
#
# An alert queue where everything was resolved instantly is not a demo of an
# SLA. Resolved alerts are acknowledged within minutes and closed within hours,
# with one deliberately slow outlier every few alerts.
# --------------------------------------------------------------------------

ACK_MINUTES: Final[tuple[int, ...]] = (4, 7, 11, 16, 23, 38, 52, 9, 14, 6)
RESOLVE_MINUTES: Final[tuple[int, ...]] = (45, 70, 95, 130, 180, 240, 320, 55, 85, 110)

VISIT_NOTES: Final[tuple[str, ...]] = (
    "Routine home visit completed. Patient comfortable and responsive.",
    "Vitals recorded, doses supervised. Patient in good spirits.",
    "Patient reported mild fatigue. Advised rest and fluids; family informed.",
    "Mobility exercises completed. Appetite and sleep reported as normal.",
    "Wound dressing checked, no signs of infection. Next review at the following visit.",
    "Patient sitting up and conversational. Family present throughout the visit.",
)

SKIP_REASONS: Final[dict[str, str]] = {
    "skipped": "Dose held - patient had not eaten yet",
    "refused": "Patient declined the dose during the visit",
}

MISSED_REASON: Final = "Nobody at the residence. Family contacted; visit rescheduled."
CANCELLED_REASON: Final = "Cancelled by the family - patient travelling."


# --------------------------------------------------------------------------
# Public enquiries (Phase 8)
#
# So that Admin -> Leads is a working queue in the demo rather than an empty
# screen. `FULL` only: `SMALL` seeds no leads, which is what keeps the existing
# suite's counts untouched.
#
# Every enquiry below is fictional, and deliberately mundane. These are not
# testimonials and must never be presented as any — nothing here is quoted on a
# public page. DoorDoctor is pre-launch.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LeadSpec:
    name: str
    email: str
    phone: str
    city: str
    kind: str
    message: str
    source_page: str
    #: How long ago it arrived, in hours. Spread so the queue has an age to it.
    hours_ago: int
    status: str = "new"
    admin_note: str | None = None


LEADS: Final[tuple[LeadSpec, ...]] = (
    LeadSpec(
        name="Vinod Raghavan",
        email="vinod.raghavan@example.com",
        phone="+91 98862 41107",
        city="Bengaluru",
        kind="family",
        message=(
            "My father is 81 and lives in Rajajinagar with a house help. "
            "I would like someone to check on him twice a week."
        ),
        source_page="/pricing",
        hours_ago=3,
    ),
    LeadSpec(
        name="Anjali Menon",
        email="anjali.menon@example.com",
        phone="+1 415 555 0164",
        city="San Francisco",
        kind="nri",
        message=(
            "I am in California and both my parents are in Bengaluru. "
            "I need to know someone is looking in on them and that I will hear about it."
        ),
        source_page="/nri",
        hours_ago=9,
    ),
    LeadSpec(
        name="Priyanka Shetty",
        email="priyanka.shetty@example.com",
        phone="+91 99451 88023",
        city="Bengaluru",
        kind="corporate",
        message=(
            "We are a 300-person engineering office looking at elder care as a benefit. "
            "Could you send details of what the per-employee price covers?"
        ),
        source_page="/pricing/corporate",
        hours_ago=26,
        status="contacted",
        admin_note="Intro call held. Sending a proposal for a 40-employee pilot.",
    ),
    LeadSpec(
        name="Fr. Thomas Mathew",
        email="thomas.mathew@example.com",
        phone="+91 80 2555 0119",
        city="Bengaluru",
        kind="institution",
        message="We run a 30-bed residence in Cooke Town and would like to discuss the per-resident rate.",
        source_page="/pricing/institutions",
        hours_ago=52,
        status="qualified",
        admin_note="Site visit booked. Fits the 25-resident band.",
    ),
    LeadSpec(
        name="Sneha Kulkarni",
        email="sneha.kulkarni@example.com",
        phone="+91 97400 33218",
        city="Mysuru",
        kind="family",
        message="Do you cover Mysuru? My mother is there and I am in Bengaluru.",
        source_page="/contact",
        hours_ago=71,
        status="closed",
        admin_note="Outside the current service area. Asked to keep her posted.",
    ),
    LeadSpec(
        name="Harish Nair",
        email="harish.nair@example.com",
        phone="+91 90350 77412",
        city="Bengaluru",
        kind="family",
        message="What is the difference between the ₹3,500 and ₹4,500 plans?",
        source_page="/pricing",
        hours_ago=14,
    ),
)
