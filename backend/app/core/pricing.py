"""Every price DoorDoctor charges, in one file.

This module imports nothing from the application. Models, services, routers, the
seed and (in Phase 8) the public pricing page all read *these* constants, so a
price cannot be stated in two places and disagree with itself.

Money is **integer paise** everywhere. ₹3,500 is `350000`. No float touches money
at any point in this codebase — `0.1 + 0.2` is not a rounding curiosity when it
is somebody's invoice.

Provenance
----------
The build prompt is the source of truth. The prices below are recorded verbatim
from it. Values the prompt did **not** record are marked `ASSUMED` and are listed
in `docs/build-log/STATE.md`; reconciling them with the real §3 is an edit to
this file and nothing else.

No GST or other tax is modelled. None was specified, and an invented tax rate
would put a wrong number on an invoice that looks authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping

PAISE_PER_RUPEE: Final = 100


def rupees(amount: int) -> int:
    """Rupees as paise. Written out at every call site so the unit is never ambiguous."""
    return amount * PAISE_PER_RUPEE


# --------------------------------------------------------------------------
# Audiences and billing cycles
# --------------------------------------------------------------------------

AUDIENCE_INDIVIDUAL: Final = "individual"
AUDIENCE_CORPORATE: Final = "corporate"
AUDIENCE_INSTITUTION: Final = "institution"

# Recorded: the annual price is "2 months free", i.e. ten months' money for
# twelve months of care. `test_pricing.py` asserts every annual price against
# this rule rather than trusting the table below to have been typed correctly.
ANNUAL_MONTHS_CHARGED: Final = 10
ANNUAL_MONTHS_FREE: Final = 12 - ANNUAL_MONTHS_CHARGED


# --------------------------------------------------------------------------
# Entitlement keys
#
# Entitlements are *data on the plan*, never `if tier == "premium"` in a service.
# Phase 9 reads these for care-manager ratios, telemedicine limits and lab
# panels; a branch on a tier string here would put Phase 9's rules in Phase 4's
# code and make a fourth tier a refactor instead of a row.
# --------------------------------------------------------------------------

VISITS_PER_MONTH: Final = "visits_per_month"
TELEMEDICINE_PER_MONTH: Final = "telemedicine_per_month"
LAB_PANELS_PER_YEAR: Final = "lab_panels_per_year"
CARE_MANAGER: Final = "care_manager"
CARE_MANAGER_RATIO: Final = "care_manager_ratio"
REPORT_CADENCE: Final = "report_cadence"
FAMILY_SEATS: Final = "family_seats"
PRIORITY_ESCALATION: Final = "priority_escalation"
AI_ASSISTANT: Final = "ai_assistant"

# `None` means unlimited. Deliberately not a sentinel like -1, which some caller
# would eventually compare with `<` and silently treat as "none left".
UNLIMITED: Final = None

# Recorded in STATE.md: care managers run 1:20 shared and 1:10 dedicated.
# Which tier gets which is ASSUMED.
RATIO_SHARED: Final = 20
RATIO_DEDICATED: Final = 10


@dataclass(frozen=True)
class QuotaSpec:
    """A metered entitlement: what it is called, what limits it, how often it resets."""

    name: str
    entitlement_key: str
    period: str  # "month" | "year"
    label: str


# The metered allowances. `QuotaUsage.quota` stores `name` as a plain string
# rather than a database enum, so adding a meter stays a one-file change here.
QUOTAS: Final[tuple[QuotaSpec, ...]] = (
    QuotaSpec("visits", VISITS_PER_MONTH, "month", "Home nurse visits"),
    QuotaSpec("telemedicine", TELEMEDICINE_PER_MONTH, "month", "Doctor video consults"),
    QuotaSpec("lab_panels", LAB_PANELS_PER_YEAR, "year", "Lab panels"),
)

QUOTAS_BY_NAME: Final[Mapping[str, QuotaSpec]] = MappingProxyType({q.name: q for q in QUOTAS})


# --------------------------------------------------------------------------
# Plans
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanSpec:
    code: str
    name: str
    audience: str
    tagline: str
    monthly_paise: int
    entitlements: Mapping[str, object]
    annual_paise: int | None = None
    recommended: bool = False
    sort_order: int = 0
    # Corporate and institutional plans quote a per-unit headline alongside the
    # monthly figure. `unit_included` is how many units the monthly price covers.
    unit_label: str | None = None
    unit_included: int | None = None
    unit_paise: int | None = None
    unit_period: str | None = None  # "month" | "day"

    def price_paise(self, cycle: str) -> int:
        """Price for one billing period on the given cycle."""
        if cycle == "annual":
            if self.annual_paise is None:
                raise ValueError(f"Plan {self.code} is not sold annually.")
            return self.annual_paise
        return self.monthly_paise


def _annual(monthly_rupees: int) -> int:
    return rupees(monthly_rupees * ANNUAL_MONTHS_CHARGED)


# --- Individual plans -----------------------------------------------------
#
# Prices RECORDED: ₹2,500 / ₹3,500 (Recommended) / ₹4,500 monthly,
#                  ₹25,000 / ₹35,000 / ₹45,000 annual.
# Tier NAMES ASSUMED, except "Premium", which is attested by the recorded
# telemedicine entitlement of 2 consults per month on Premium.
# Every entitlement quantity below is ASSUMED apart from that one.

ESSENTIAL = PlanSpec(
    code="essential",
    name="Essential",  # ASSUMED
    audience=AUDIENCE_INDIVIDUAL,
    tagline="Regular nurse visits and always-on monitoring for one parent.",  # ASSUMED
    monthly_paise=rupees(2_500),
    annual_paise=_annual(2_500),
    sort_order=10,
    entitlements={
        VISITS_PER_MONTH: 4,  # ASSUMED
        TELEMEDICINE_PER_MONTH: 0,  # ASSUMED
        LAB_PANELS_PER_YEAR: 0,  # ASSUMED
        CARE_MANAGER: "shared",  # ASSUMED
        CARE_MANAGER_RATIO: RATIO_SHARED,
        REPORT_CADENCE: "monthly",  # ASSUMED
        FAMILY_SEATS: 2,  # ASSUMED
        PRIORITY_ESCALATION: False,  # ASSUMED
        AI_ASSISTANT: True,  # ASSUMED
    },
)

CARE_PLUS = PlanSpec(
    code="care_plus",
    name="Care Plus",  # ASSUMED
    audience=AUDIENCE_INDIVIDUAL,
    tagline="Twice-weekly visits, a care manager and weekly reports.",  # ASSUMED
    monthly_paise=rupees(3_500),
    annual_paise=_annual(3_500),
    recommended=True,  # RECORDED — ₹3,500 is the recommended tier
    sort_order=20,
    entitlements={
        VISITS_PER_MONTH: 8,  # ASSUMED
        TELEMEDICINE_PER_MONTH: 1,  # ASSUMED
        LAB_PANELS_PER_YEAR: 2,  # ASSUMED
        CARE_MANAGER: "shared",  # ASSUMED
        CARE_MANAGER_RATIO: RATIO_SHARED,
        REPORT_CADENCE: "weekly",  # ASSUMED
        FAMILY_SEATS: 4,  # ASSUMED
        PRIORITY_ESCALATION: False,  # ASSUMED
        AI_ASSISTANT: True,  # ASSUMED
    },
)

PREMIUM = PlanSpec(
    code="premium",
    name="Premium",  # attested by STATE.md's telemedicine note
    audience=AUDIENCE_INDIVIDUAL,
    tagline="Thrice-weekly visits, a dedicated care manager and priority escalation.",  # ASSUMED
    monthly_paise=rupees(4_500),
    annual_paise=_annual(4_500),
    sort_order=30,
    entitlements={
        VISITS_PER_MONTH: 12,  # ASSUMED
        TELEMEDICINE_PER_MONTH: 2,  # RECORDED
        LAB_PANELS_PER_YEAR: 4,  # ASSUMED
        CARE_MANAGER: "dedicated",  # ASSUMED
        CARE_MANAGER_RATIO: RATIO_DEDICATED,
        REPORT_CADENCE: "weekly",  # ASSUMED
        FAMILY_SEATS: 6,  # ASSUMED
        PRIORITY_ESCALATION: True,  # ASSUMED
        AI_ASSISTANT: True,  # ASSUMED
    },
)

# --- Corporate ------------------------------------------------------------
# RECORDED: ₹2,800 per employee per month. Entitlements ASSUMED.

CORPORATE = PlanSpec(
    code="corporate",
    name="Corporate Elder Care",  # ASSUMED
    audience=AUDIENCE_CORPORATE,
    tagline="Elder care as an employee benefit, billed per enrolled employee.",  # ASSUMED
    monthly_paise=rupees(2_800),
    annual_paise=None,  # not sold annually — no annual corporate price was recorded
    sort_order=40,
    unit_label="employee",
    unit_included=1,
    unit_paise=rupees(2_800),
    unit_period="month",
    entitlements={
        VISITS_PER_MONTH: 4,  # ASSUMED
        TELEMEDICINE_PER_MONTH: 1,  # ASSUMED
        LAB_PANELS_PER_YEAR: 1,  # ASSUMED
        CARE_MANAGER: "shared",  # ASSUMED
        CARE_MANAGER_RATIO: RATIO_SHARED,
        REPORT_CADENCE: "weekly",  # ASSUMED
        FAMILY_SEATS: 4,  # ASSUMED
        PRIORITY_ESCALATION: False,  # ASSUMED
        AI_ASSISTANT: True,  # ASSUMED
    },
)

# --- Institutional --------------------------------------------------------
#
# RECORDED: ₹38,000 / ₹58,000 / ₹78,000 per month, led by
#           ₹84 / ₹77 / ₹65 per resident per day.
#
# The band sizes are DERIVED, not guessed. Each pair of recorded numbers fixes
# the resident count the monthly price covers:
#
#     ₹84/day × 30 days × 15 residents = ₹37,800  ≈ ₹38,000
#     ₹77/day × 30 days × 25 residents = ₹57,750  ≈ ₹58,000
#     ₹65/day × 30 days × 40 residents = ₹78,000  =  ₹78,000  (exact)
#
# `test_pricing.py` re-runs that arithmetic, so the derivation is auditable
# rather than folklore. Plan names are descriptive placeholders, not branding.

DAYS_PER_BILLED_MONTH: Final = 30

_INSTITUTIONAL_ENTITLEMENTS: Final[Mapping[str, object]] = MappingProxyType(
    {
        VISITS_PER_MONTH: UNLIMITED,  # ASSUMED — staffing is on-site, not per-visit
        TELEMEDICINE_PER_MONTH: 4,  # ASSUMED
        LAB_PANELS_PER_YEAR: 0,  # ASSUMED — set per band below
        CARE_MANAGER: "shared",  # ASSUMED
        CARE_MANAGER_RATIO: RATIO_SHARED,
        REPORT_CADENCE: "weekly",  # ASSUMED
        FAMILY_SEATS: 2,  # ASSUMED
        PRIORITY_ESCALATION: True,  # ASSUMED
        AI_ASSISTANT: True,  # ASSUMED
    }
)


def _institutional(
    residents: int, per_day_rupees: int, monthly_rupees: int, sort_order: int, dedicated: bool
) -> PlanSpec:
    entitlements = dict(_INSTITUTIONAL_ENTITLEMENTS)
    entitlements[LAB_PANELS_PER_YEAR] = residents  # ASSUMED — one panel per resident per year
    if dedicated:
        entitlements[CARE_MANAGER] = "dedicated"
        entitlements[CARE_MANAGER_RATIO] = RATIO_DEDICATED
    return PlanSpec(
        code=f"institution_{residents}",
        name=f"Institutional {residents}",  # descriptive, not invented branding
        audience=AUDIENCE_INSTITUTION,
        tagline=f"Up to {residents} residents at ₹{per_day_rupees} per resident per day.",
        monthly_paise=rupees(monthly_rupees),
        annual_paise=None,  # no annual institutional price was recorded
        sort_order=sort_order,
        unit_label="resident",
        unit_included=residents,
        unit_paise=rupees(per_day_rupees),
        unit_period="day",
        entitlements=entitlements,
    )


INSTITUTION_15 = _institutional(15, 84, 38_000, 50, dedicated=False)
INSTITUTION_25 = _institutional(25, 77, 58_000, 60, dedicated=False)
INSTITUTION_40 = _institutional(40, 65, 78_000, 70, dedicated=True)


PLANS: Final[tuple[PlanSpec, ...]] = (
    ESSENTIAL,
    CARE_PLUS,
    PREMIUM,
    CORPORATE,
    INSTITUTION_15,
    INSTITUTION_25,
    INSTITUTION_40,
)

PLANS_BY_CODE: Final[Mapping[str, PlanSpec]] = MappingProxyType({p.code: p for p in PLANS})

DEFAULT_PLAN_CODE: Final = CARE_PLUS.code


# --------------------------------------------------------------------------
# Add-ons — RECORDED
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class AddOnSpec:
    code: str
    name: str
    price_paise: int
    unit: str


ADD_ONS: Final[tuple[AddOnSpec, ...]] = (
    AddOnSpec("blood_panel", "Blood panel", rupees(499), "per panel"),
    AddOnSpec("pill_organiser", "Pill organiser", rupees(199), "per month"),
)

ADD_ONS_BY_CODE: Final[Mapping[str, AddOnSpec]] = MappingProxyType({a.code: a for a in ADD_ONS})


# --------------------------------------------------------------------------
# Referrals and loyalty — ASSUMED in full
#
# Both end in the same place: money off the next invoice. They are therefore one
# mechanism (`Credit`) with two reasons, not two parallel reward systems.
# --------------------------------------------------------------------------

# The referrer earns a credit worth this many months of *their own* plan, so the
# reward scales with what they pay instead of needing a per-tier table.
REFERRAL_REWARD_MONTHS: Final = 1  # ASSUMED
# The family who was referred gets a flat welcome credit on their first invoice.
REFERRED_WELCOME_CREDIT_PAISE: Final = rupees(1_000)  # ASSUMED
# A referral that never converts stops counting after this long.
REFERRAL_EXPIRY_DAYS: Final = 90  # ASSUMED

# RECORDED: loyalty triggers at 12 paid months. What it grants is ASSUMED.
LOYALTY_AFTER_PAID_MONTHS: Final = 12
LOYALTY_REWARD_MONTHS: Final = 1  # ASSUMED — the 13th month is free, and every 12 months after


def months_of(plan: PlanSpec, months: int) -> int:
    """A reward expressed in months of a given plan, as paise."""
    return plan.monthly_paise * months
