"""The price list itself.

These assert the *arithmetic* the prompt's numbers imply, not the numbers as
typed. A transposed digit in `core/pricing.py` fails here rather than reaching an
invoice.
"""

import pytest

from app.core import pricing


def test_recorded_individual_prices():
    """The three individual monthly prices, verbatim from the build prompt."""
    assert pricing.ESSENTIAL.monthly_paise == pricing.rupees(2_500)
    assert pricing.CARE_PLUS.monthly_paise == pricing.rupees(3_500)
    assert pricing.PREMIUM.monthly_paise == pricing.rupees(4_500)


def test_recorded_annual_prices():
    assert pricing.ESSENTIAL.annual_paise == pricing.rupees(25_000)
    assert pricing.CARE_PLUS.annual_paise == pricing.rupees(35_000)
    assert pricing.PREMIUM.annual_paise == pricing.rupees(45_000)


def test_annual_is_two_months_free():
    """"2 months free" means ten months' money for twelve months of care."""
    for plan in pricing.PLANS:
        if plan.annual_paise is None:
            continue
        assert plan.annual_paise == plan.monthly_paise * pricing.ANNUAL_MONTHS_CHARGED, plan.code
        assert pricing.ANNUAL_MONTHS_FREE == 2


def test_care_plus_is_the_recommended_tier():
    recommended = [p for p in pricing.PLANS if p.recommended]
    assert recommended == [pricing.CARE_PLUS]


def test_corporate_per_employee_price():
    assert pricing.CORPORATE.unit_paise == pricing.rupees(2_800)
    assert pricing.CORPORATE.unit_label == "employee"
    assert pricing.CORPORATE.unit_period == "month"


@pytest.mark.parametrize(
    "plan, residents, per_day_rupees, monthly_rupees, rounded_up_by",
    [
        # ₹84 × 30 × 15 = ₹37,800, published as ₹38,000 — rounded up ₹200
        (pricing.INSTITUTION_15, 15, 84, 38_000, 200),
        # ₹77 × 30 × 25 = ₹57,750, published as ₹58,000 — rounded up ₹250
        (pricing.INSTITUTION_25, 25, 77, 58_000, 250),
        # ₹65 × 30 × 40 = ₹78,000, published as ₹78,000 — exact
        (pricing.INSTITUTION_40, 40, 65, 78_000, 0),
    ],
)
def test_institutional_bands_reconcile(plan, residents, per_day_rupees, monthly_rupees, rounded_up_by):
    """The band size is derived from the two recorded numbers, not invented.

    Each band is the resident count at which the recorded per-resident-per-day
    rate reaches the recorded monthly price. The published figure is that number
    rounded up to something sayable, and the exact gap is asserted here rather
    than hidden behind a tolerance — if a price moves, this says by how much.
    """
    assert plan.unit_included == residents
    assert plan.unit_paise == pricing.rupees(per_day_rupees)
    assert plan.monthly_paise == pricing.rupees(monthly_rupees)

    derived = pricing.rupees(per_day_rupees) * pricing.DAYS_PER_BILLED_MONTH * residents
    assert plan.monthly_paise - derived == pricing.rupees(rounded_up_by)


def test_add_on_prices():
    assert pricing.ADD_ONS_BY_CODE["blood_panel"].price_paise == pricing.rupees(499)
    assert pricing.ADD_ONS_BY_CODE["pill_organiser"].price_paise == pricing.rupees(199)


def test_plan_codes_are_unique():
    codes = [plan.code for plan in pricing.PLANS]
    assert len(codes) == len(set(codes))


def test_every_plan_declares_every_entitlement():
    """A missing key would silently read as "not entitled" at some later phase."""
    keys = {
        pricing.VISITS_PER_MONTH,
        pricing.TELEMEDICINE_PER_MONTH,
        pricing.LAB_PANELS_PER_YEAR,
        pricing.CARE_MANAGER,
        pricing.CARE_MANAGER_RATIO,
        pricing.REPORT_CADENCE,
        pricing.FAMILY_SEATS,
        pricing.PRIORITY_ESCALATION,
        pricing.AI_ASSISTANT,
    }
    for plan in pricing.PLANS:
        assert keys <= set(plan.entitlements), f"{plan.code} is missing {keys - set(plan.entitlements)}"


def test_care_manager_ratios_match_the_recorded_pair():
    """Recorded in STATE.md: 1:20 shared, 1:10 dedicated."""
    assert pricing.RATIO_SHARED == 20
    assert pricing.RATIO_DEDICATED == 10
    for plan in pricing.PLANS:
        kind = plan.entitlements[pricing.CARE_MANAGER]
        ratio = plan.entitlements[pricing.CARE_MANAGER_RATIO]
        assert (kind, ratio) in (("shared", 20), ("dedicated", 10)), plan.code


def test_premium_telemedicine_allowance_is_the_recorded_two():
    assert pricing.PREMIUM.entitlements[pricing.TELEMEDICINE_PER_MONTH] == 2


def test_every_quota_points_at_a_real_entitlement():
    for spec in pricing.QUOTAS:
        assert spec.period in ("month", "year")
        for plan in pricing.PLANS:
            assert spec.entitlement_key in plan.entitlements, (plan.code, spec.name)


def test_loyalty_milestone_is_twelve_paid_months():
    assert pricing.LOYALTY_AFTER_PAID_MONTHS == 12
