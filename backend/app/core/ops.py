"""Every operational constant this platform applies, in one file.

The third sibling of `core/pricing.py` and `core/clinical.py`, built to the same
rule: it **imports nothing from the application**. It may read `core.clinical`,
because that module imports nothing from the application either and the
dependency runs one way only — but it must never *restate* a clinical constant.

Why a third file rather than more `clinical.py`
-----------------------------------------------
A geofence radius, a photo retention window, a quiet-hours window and a
channel-routing table are **operational**, not clinical. `clinical.py` is the
file a clinician reconciles; this is the file an operator reconciles. Keeping
them apart keeps the two conversations apart.

Provenance
----------
§4.10–4.18 was **never supplied**, exactly as §3 (Phase 4), §2.3's intent list
(Phase 7) and §4.2–4.9 (Phase 9) were not. Same treatment, four phases running:

* ``RECORDED`` — stated in the build prompt or the plan file. Enforce as-is.
* ``ASSUMED``  — invented here. Listed in ``docs/build-log/STATE.md``.
                 Reconciling the real §4.10–4.18 is an edit to *this file*.

The one idea underneath all of it: **a promise the platform cannot evidence is a
promise it should not make.** Several constants below exist only so that the
platform can say "we do not know" precisely, rather than guessing confidently.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping

from .clinical import SLA_DURATIONS_MINUTES

# --------------------------------------------------------------------------
# Location verification (§4.11)
#
# RECORDED: the classification is exactly `verified` / `out_of_range` /
# `unavailable`, and the default geofence is 150 m. Everything else is ASSUMED.
# --------------------------------------------------------------------------

GEOFENCE_RADIUS_M: Final = 150.0  # RECORDED

# A fix whose own reported accuracy is worse than the fence cannot verify the
# fence. A +/-500 m position sitting 40 m from the door is not evidence that the
# nurse was at the door — it is evidence that the phone does not know. Classify
# it `unavailable` and say so, because reporting it as `verified` would be the
# platform lying about the one thing this feature exists to prove.
GEOFENCE_ACCURACY_CEILING_M: Final = 150.0  # ASSUMED — equal to the fence

# Browsers that decline to report accuracy send nothing. Treat a missing
# accuracy as usable rather than unavailable: the coordinates are still a fix,
# and refusing every browser that omits the field would classify most desktop
# check-ins as unknown. ASSUMED.
GEOFENCE_ASSUME_ACCURACY_WHEN_MISSING: Final = True

EARTH_RADIUS_M: Final = 6_371_008.8  # IUGG mean earth radius — arithmetic, not a policy

# An out-of-range check-in does NOT block the visit. A nurse in a stairwell with
# a bad fix must still be able to work; refusing the check-in would make the
# honest thing (letting the phone report a real position) the thing that stops
# them working, and turning location off the thing that lets them through.
# It opens a task for the admin instead. ASSUMED.
GEOFENCE_BLOCKS_CHECKIN: Final = False
GEOFENCE_TASK_HOURS: Final = 24  # ASSUMED


# --------------------------------------------------------------------------
# Uploads and dose photos (§4.12)
#
# RECORDED: photos live under `backend/app/uploads/` and are **never served
# statically**. Retention, size caps and formats are ASSUMED.
# --------------------------------------------------------------------------

UPLOAD_DIR_NAME: Final = "uploads"  # RECORDED

PHOTO_MAX_BYTES: Final = 4 * 1024 * 1024  # ASSUMED — 4 MB, a phone photo with room to spare

# Checked by decoding the bytes, never by trusting the declared content type.
# A client-declared `image/jpeg` proves nothing about what is in the file.
PHOTO_ALLOWED_FORMATS: Final[frozenset[str]] = frozenset({"JPEG", "PNG", "WEBP"})
PHOTO_OUTPUT_FORMAT: Final = "JPEG"
PHOTO_OUTPUT_QUALITY: Final = 82
PHOTO_MAX_EDGE_PX: Final = 1600  # ASSUMED — legible evidence, not a print master

# A dose photo taken in the patient's living room carries the patient's home GPS
# in its EXIF. Every upload is re-encoded, which drops EXIF entirely. This is
# not configurable: there is no version of this product where storing that
# metadata is the right call.
PHOTO_STRIP_METADATA: Final = True

PHOTO_RETENTION_DAYS: Final = 180  # ASSUMED


# --------------------------------------------------------------------------
# Medication (§4.12)
# --------------------------------------------------------------------------

# A pill organiser is filled for a week at a time, seven days x four slots.
PILL_ORGANISER_COMPARTMENTS: Final = 28  # ASSUMED
PILL_ORGANISER_DAYS: Final = 7  # ASSUMED
PILL_ORGANISER_LOW_DAYS: Final = 2  # ASSUMED — warn this many days before it runs out


# --------------------------------------------------------------------------
# Care circle (§4.13)
# --------------------------------------------------------------------------

CARE_CIRCLE_MAX_MEMBERS: Final = 8  # ASSUMED

# The relationship vocabulary is a suggestion list, not a constraint — the field
# accepts free text, because "my mother's neighbour who has the spare key" is a
# real and important member of a care circle and no enum was going to hold it.
CARE_CIRCLE_RELATIONSHIPS: Final[tuple[str, ...]] = (
    "Son",
    "Daughter",
    "Spouse",
    "Sibling",
    "Grandchild",
    "Neighbour",
    "Family friend",
    "Other",
)


# --------------------------------------------------------------------------
# Consent and privacy (§4.14)
#
# RECORDED: the audit log is append-only. What is audited, and for how long,
# is ASSUMED.
# --------------------------------------------------------------------------

CONSENT_POLICY_VERSION: Final = "2026-08-1"  # ASSUMED


@dataclass(frozen=True)
class ConsentSpec:
    """One consent decision a family is asked to make.

    `required` consents gate the service; the rest are genuinely optional, and
    a consent screen where everything is required is a consent screen that is
    not asking anything.
    """

    key: str
    label: str
    blurb: str
    required: bool


CONSENT_KINDS: Final[tuple[ConsentSpec, ...]] = (
    ConsentSpec(
        "care_delivery",
        "Home visits and health monitoring",
        "DoorDoctor nurses may visit, record readings and keep a health record for your relative.",
        True,
    ),
    ConsentSpec(
        "data_sharing_family",
        "Sharing with your care circle",
        "The people you add to the care circle may see readings, alerts and visit notes.",
        False,
    ),
    ConsentSpec(
        "notifications",
        "Messages outside the app",
        "We may send alerts and reminders by SMS, WhatsApp or email as well as in the app.",
        False,
    ),
    ConsentSpec(
        "assistant",
        "The DoorDoctor assistant",
        "Your questions may be answered by an assistant that reads your relative's record.",
        False,
    ),
)

CONSENT_KINDS_BY_KEY: Final[Mapping[str, ConsentSpec]] = MappingProxyType(
    {spec.key: spec for spec in CONSENT_KINDS}
)

AUDIT_RETENTION_DAYS: Final = 365 * 7  # ASSUMED

# Written plainly because a family reads it. "We delete everything" followed by
# keeping the invoices would be exactly the unevidenced promise this phase
# exists to stop, so the exceptions are stated up front and each carries its
# reason.
ERASURE_DESTROYS: Final[tuple[str, ...]] = (
    "Your relative's name, address, contact details and home location",
    "Health readings, visit records and visit notes",
    "Medication schedules, dose records and dose photographs",
    "Lab orders and results, mood check answers and safety scores",
    "Wearable device registrations and everything they sent",
    "Alerts, escalations and their contact timelines",
    "Reports, and every message exchanged with the assistant",
    "Care circle members and their contact details",
)

ERASURE_RETAINS: Final[tuple[tuple[str, str], ...]] = (
    (
        "Issued invoices and payments",
        "Financial records of money that was billed. They are kept with the patient's name replaced.",
    ),
    (
        "The audit log",
        "The record of who did what, including this erasure. Deleting it would remove the evidence "
        "that the erasure happened.",
    ),
    (
        "Your own login",
        "Erasure removes a patient's record. Closing the account itself is a separate request.",
    ),
)


# --------------------------------------------------------------------------
# Notification routing, preferences and quiet hours (§4.18)
#
# RECORDED: critical alerts go out on two channels. The windows, the order and
# the per-type defaults are ASSUMED.
# --------------------------------------------------------------------------

# Local wall-clock hours, Asia/Kolkata — which is what `database.now()` already
# produces on this deployment. Phase 11 owns real timezone handling; when it
# lands, these become the *account's* quiet hours rather than the server's.
QUIET_HOURS_START: Final = 21  # ASSUMED — 21:00
QUIET_HOURS_END: Final = 7  # ASSUMED — 07:00

# Not configurable, and deliberately not a preference. A quiet-hours setting
# that can silence a critical alert is a setting that can kill somebody.
QUIET_HOURS_NEVER_SUPPRESS_CRITICAL: Final = True

# RECORDED. The rule is two channels; the resolver picks two that can actually
# reach the person, and records the attempt it could not make. Phase 9 found the
# shape of this bug: push has no address in this build, so a "dual-channel"
# promise made of SMS + push is one channel wearing two names.
CRITICAL_CHANNEL_COUNT: Final = 2

# Preference order per notification type, most-preferred first. The resolver
# walks it and keeps the ones with an address. ASSUMED in full.
CHANNEL_ORDER: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "alert": ("sms", "whatsapp", "email", "push"),
        "visit": ("whatsapp", "sms", "email", "push"),
        "system": ("email", "whatsapp", "sms", "push"),
    }
)

CHANNEL_ORDER_DEFAULT: Final[tuple[str, ...]] = ("email", "sms", "whatsapp", "push")

# Channels a new account has switched on before it has expressed a preference.
# Push is off because it cannot reach anybody in this build; leaving it on would
# put a channel in every routing decision that never delivers. ASSUMED.
CHANNEL_DEFAULT_ENABLED: Final[Mapping[str, bool]] = MappingProxyType(
    {"email": True, "sms": True, "whatsapp": True, "push": False}
)


# --------------------------------------------------------------------------
# Zones and the break-even band (§4.17)
#
# RECORDED: the zone view shows the ~30-45 subscriber break-even. The unit
# economics behind that band were never supplied, so nothing here invents a
# margin — the view says where a zone sits against the band and stops.
# --------------------------------------------------------------------------

BREAK_EVEN_MIN_SUBSCRIBERS: Final = 30  # RECORDED
BREAK_EVEN_MAX_SUBSCRIBERS: Final = 45  # RECORDED

BREAK_EVEN_NOTE: Final = (
    "A zone is expected to cover its own cost somewhere between "
    f"{BREAK_EVEN_MIN_SUBSCRIBERS} and {BREAK_EVEN_MAX_SUBSCRIBERS} subscribers. "
    "DoorDoctor has not published the cost model behind that range, so this view "
    "reports where each zone sits against it and does not estimate a margin."
)


# --------------------------------------------------------------------------
# Operations SLAs (§4.17)
#
# The alert queue reuses the clinical SLA budgets rather than declaring a second
# set. `clinical.py` owns those numbers; this module points at them.
# --------------------------------------------------------------------------

ALERT_SLA_MINUTES: Final[Mapping[str, int]] = SLA_DURATIONS_MINUTES

# How far back the outcome metrics look by default. ASSUMED.
OUTCOME_WINDOW_DAYS: Final = 30

# The visit board's page size. The old `/visits` cap of 250 newest-first rows is
# what this replaces — it led with next week rather than today.
VISIT_BOARD_PAGE_SIZE: Final = 25
VISIT_BOARD_MAX_PAGE_SIZE: Final = 100


# --------------------------------------------------------------------------
# Onboarding (§4.15)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class OnboardingStepSpec:
    key: str
    label: str
    blurb: str
    path: str


# Every step maps to something that already exists, so completing one is a real
# action and not a tick. ASSUMED in full.
ONBOARDING_STEPS: Final[tuple[OnboardingStepSpec, ...]] = (
    OnboardingStepSpec(
        "confirm_patient",
        "Check your relative's details",
        "Their name, age and address are what the nurse sees at the door.",
        "/family/dashboard",
    ),
    OnboardingStepSpec(
        "consent",
        "Agree to how their information is used",
        "What DoorDoctor may record, and who may see it.",
        "/family/privacy",
    ),
    OnboardingStepSpec(
        "thresholds",
        "Set the ranges you want watched",
        "Readings outside these raise an alert. Sensible defaults are already in place.",
        "/family/dashboard",
    ),
    OnboardingStepSpec(
        "care_circle",
        "Add the people who should know",
        "Anyone who should be told when something happens — including whoever lives nearby.",
        "/family/care-circle",
    ),
    OnboardingStepSpec(
        "notifications",
        "Choose how we reach you",
        "Which channels to use, and when to stay quiet.",
        "/family/notifications",
    ),
)

ONBOARDING_STEPS_BY_KEY: Final[Mapping[str, OnboardingStepSpec]] = MappingProxyType(
    {step.key: step for step in ONBOARDING_STEPS}
)
