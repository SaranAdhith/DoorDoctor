"""Plans, entitlements, quotas, plan changes and cancellation."""

import pytest

from app.core import pricing
from app.core.exceptions import ConflictError
from app.models import BillingCycle, CreditKind, SubscriptionStatus
from app.services import subscription_service
from tests.conftest import DEMO_PASSWORD, auth, login


def _subscription(client, headers):
    response = client.get("/api/v1/subscriptions/me", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------
# Plans
# --------------------------------------------------------------------------


def test_plans_are_published_with_entitlements(client, family_headers):
    plans = client.get("/api/v1/plans", headers=family_headers).json()
    codes = {plan["code"] for plan in plans}
    assert {"essential", "care_plus", "premium", "corporate"} <= codes

    care_plus = next(p for p in plans if p["code"] == "care_plus")
    assert care_plus["monthly_paise"] == pricing.rupees(3_500)
    assert care_plus["annual_paise"] == pricing.rupees(35_000)
    assert care_plus["recommended"] is True
    assert care_plus["entitlements"]["visits_per_month"] == 8


def test_plans_can_be_filtered_by_audience(client, admin_headers):
    individual = client.get("/api/v1/plans?audience=individual", headers=admin_headers).json()
    assert {p["code"] for p in individual} == {"essential", "care_plus", "premium"}

    institutional = client.get("/api/v1/plans?audience=institution", headers=admin_headers).json()
    assert len(institutional) == 3
    assert all(p["unit_label"] == "resident" for p in institutional)


def test_syncing_plans_twice_changes_nothing(db):
    first = {p.code: p.id for p in subscription_service.sync_plans(db)}
    second = {p.code: p.id for p in subscription_service.sync_plans(db)}
    assert first == second


# --------------------------------------------------------------------------
# The family's own subscription
# --------------------------------------------------------------------------


def test_family_sees_their_subscription(client, family_headers):
    body = _subscription(client, family_headers)
    assert body["plan"]["code"] == "care_plus"
    assert body["status"] == "active"
    assert body["period_price_paise"] == pricing.rupees(3_500)
    assert body["paid_months"] == 14
    assert body["renews_at"] is not None


def test_seeded_history_earned_exactly_one_loyalty_reward(client, family_headers, db):
    """Fourteen paid months crosses the twelve-month milestone once."""
    from app.models import Credit, Subscription
    from sqlalchemy import select

    subscription = db.scalar(select(Subscription).where(Subscription.family_user_id.is_not(None)))
    loyalty = db.scalars(
        select(Credit).where(
            Credit.subscription_id == subscription.id, Credit.kind == CreditKind.LOYALTY
        )
    ).all()
    assert len(loyalty) == 1
    assert loyalty[0].amount_paise == pricing.rupees(3_500)


def test_a_family_without_a_subscription_gets_404(client, other_family):
    headers = auth(login(client, other_family["email"], DEMO_PASSWORD))
    assert client.get("/api/v1/subscriptions/me", headers=headers).status_code == 404


def test_nurses_have_no_billing_access(client, nurse_headers):
    for path in ("/api/v1/subscriptions/me", "/api/v1/subscriptions", "/api/v1/invoices"):
        assert client.get(path, headers=nurse_headers).status_code == 403, path


def test_admin_sees_every_subscription(client, admin_headers):
    rows = client.get("/api/v1/subscriptions", headers=admin_headers).json()
    assert len(rows) >= 4
    owners = {row["owner_label"] for row in rows}
    assert "Ashwin Technologies Pvt Ltd" in owners
    assert "Sandhya Senior Living" in owners


def test_family_cannot_list_every_subscription(client, family_headers):
    assert client.get("/api/v1/subscriptions", headers=family_headers).status_code == 403


# --------------------------------------------------------------------------
# Entitlements
# --------------------------------------------------------------------------


def test_entitlements_come_from_the_plan_not_from_the_tier_name(db):
    """The point of the design: reading an entitlement never inspects a code."""
    subscription_service.sync_plans(db)
    premium = subscription_service.get_plan(db, "premium")
    essential = subscription_service.get_plan(db, "essential")

    assert premium.entitlements[pricing.TELEMEDICINE_PER_MONTH] == 2
    assert essential.entitlements[pricing.TELEMEDICINE_PER_MONTH] == 0
    assert premium.entitlements[pricing.CARE_MANAGER_RATIO] == 10
    assert essential.entitlements[pricing.CARE_MANAGER_RATIO] == 20


def test_unlimited_entitlement_reads_as_entitled(db):
    """`None` means unlimited and must not read as "none"."""
    from app.models import Plan, Subscription

    subscription_service.sync_plans(db)
    plan = subscription_service.get_plan(db, "institution_25")
    subscription = Subscription(plan=plan)

    assert subscription_service.entitlement(subscription, pricing.VISITS_PER_MONTH) is None
    assert subscription_service.has_entitlement(subscription, pricing.VISITS_PER_MONTH) is True
    assert isinstance(plan, Plan)


def test_zero_entitlement_is_not_entitled(db):
    from app.models import Subscription

    subscription_service.sync_plans(db)
    subscription = Subscription(plan=subscription_service.get_plan(db, "essential"))
    assert subscription_service.has_entitlement(subscription, pricing.TELEMEDICINE_PER_MONTH) is False


# --------------------------------------------------------------------------
# Quotas
# --------------------------------------------------------------------------


def test_quota_reports_what_the_seed_consumed(client, family_headers):
    body = _subscription(client, family_headers)
    visits = next(q for q in body["quotas"] if q["quota"] == "visits")
    assert visits["limit"] == 8
    assert visits["used"] == 2
    assert visits["remaining"] == 6
    assert visits["unlimited"] is False


def test_quota_refuses_once_the_allowance_is_spent(db):
    from app.models import Subscription
    from sqlalchemy import select

    subscription = db.scalar(select(Subscription).where(Subscription.family_user_id.is_not(None)))
    # Care Plus allows 8 a month and the seed spent 2.
    subscription_service.consume_quota(db, subscription, "visits", 6)

    with pytest.raises(ConflictError) as excinfo:
        subscription_service.consume_quota(db, subscription, "visits", 1)
    assert "used up" in str(excinfo.value.detail)


def test_a_monthly_quota_resets_on_its_own_cadence_not_the_billing_cycle(db):
    """An annual subscriber does not get twelve months of visits in January."""
    from app.models import Subscription
    from sqlalchemy import select

    subscription = db.scalar(select(Subscription).where(Subscription.family_user_id.is_not(None)))
    subscription.billing_cycle = BillingCycle.ANNUAL
    db.flush()

    spec = pricing.QUOTAS_BY_NAME["visits"]
    start, end = subscription_service.quota_window(subscription, spec, subscription.started_at)
    assert subscription_service.add_months(start, 1) == end


def test_quota_usage_from_a_previous_period_is_kept_not_reset(db):
    from app.models import QuotaUsage, Subscription
    from sqlalchemy import select

    subscription = db.scalar(select(Subscription).where(Subscription.family_user_id.is_not(None)))
    later = subscription_service.add_months(subscription.current_period_start, 1)
    subscription_service.consume_quota(db, subscription, "visits", 1, as_of=later)

    rows = db.scalars(
        select(QuotaUsage).where(
            QuotaUsage.subscription_id == subscription.id, QuotaUsage.quota == "visits"
        )
    ).all()
    assert len(rows) == 2, "a new period must add a row, not overwrite the old one"
    assert sorted(row.used for row in rows) == [1, 2]


# --------------------------------------------------------------------------
# Changing plan
# --------------------------------------------------------------------------


def test_change_plan_credits_the_unused_remainder(client, family_headers):
    before = _subscription(client, family_headers)
    response = client.post(
        f"/api/v1/subscriptions/{before['id']}/change-plan",
        json={"plan_code": "premium"},
        headers=family_headers,
    )
    assert response.status_code == 200, response.text
    after = response.json()

    assert after["plan"]["code"] == "premium"
    assert after["period_price_paise"] == pricing.rupees(4_500)
    # The seeded period was five days old, so most of the month was unused.
    assert after["credit_balance_paise"] > before["credit_balance_paise"]
    assert after["quotas"][0]["limit"] == 12  # Premium's visit allowance


def test_change_plan_can_switch_billing_cycle(client, family_headers):
    subscription = _subscription(client, family_headers)
    response = client.post(
        f"/api/v1/subscriptions/{subscription['id']}/change-plan",
        json={"plan_code": "care_plus", "billing_cycle": "annual"},
        headers=family_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["period_price_paise"] == pricing.rupees(35_000)


def test_change_to_the_same_plan_is_rejected(client, family_headers):
    subscription = _subscription(client, family_headers)
    response = client.post(
        f"/api/v1/subscriptions/{subscription['id']}/change-plan",
        json={"plan_code": "care_plus"},
        headers=family_headers,
    )
    assert response.status_code == 400
    assert "already on" in response.json()["detail"]


def test_a_plan_with_no_annual_price_cannot_be_bought_annually(client, family_headers):
    subscription = _subscription(client, family_headers)
    response = client.post(
        f"/api/v1/subscriptions/{subscription['id']}/change-plan",
        json={"plan_code": "corporate", "billing_cycle": "annual"},
        headers=family_headers,
    )
    assert response.status_code == 400
    assert "not sold" in response.json()["detail"]


def test_another_family_cannot_touch_this_subscription(client, family_headers, other_family):
    subscription = _subscription(client, family_headers)
    headers = auth(login(client, other_family["email"], DEMO_PASSWORD))

    response = client.post(
        f"/api/v1/subscriptions/{subscription['id']}/change-plan",
        json={"plan_code": "premium"},
        headers=headers,
    )
    # 404 rather than 403 — a 403 would confirm the subscription exists.
    assert response.status_code == 404


# --------------------------------------------------------------------------
# Cancelling
# --------------------------------------------------------------------------


def test_family_cancellation_takes_effect_at_the_period_end(client, family_headers):
    subscription = _subscription(client, family_headers)
    response = client.post(
        f"/api/v1/subscriptions/{subscription['id']}/cancel",
        json={"immediate": False, "reason": "Moving my mother in with us"},
        headers=family_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["cancel_at_period_end"] is True
    assert body["status"] == "active", "paid-for care continues to the end of the period"
    assert body["renews_at"] is None


def test_a_family_cannot_end_their_subscription_mid_period(client, family_headers):
    """`immediate` is an admin power; a family asking for it still gets period-end."""
    subscription = _subscription(client, family_headers)
    response = client.post(
        f"/api/v1/subscriptions/{subscription['id']}/cancel",
        json={"immediate": True},
        headers=family_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert response.json()["cancel_at_period_end"] is True


def test_an_admin_can_end_a_subscription_immediately(client, family_headers, admin_headers):
    subscription = _subscription(client, family_headers)
    response = client.post(
        f"/api/v1/subscriptions/{subscription['id']}/cancel",
        json={"immediate": True, "reason": "Chargeback"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_a_pending_cancellation_can_be_undone(client, family_headers):
    subscription = _subscription(client, family_headers)
    client.post(
        f"/api/v1/subscriptions/{subscription['id']}/cancel",
        json={"immediate": False},
        headers=family_headers,
    )
    response = client.post(
        f"/api/v1/subscriptions/{subscription['id']}/resume", headers=family_headers
    )
    assert response.status_code == 200
    assert response.json()["cancel_at_period_end"] is False
    assert response.json()["renews_at"] is not None


# --------------------------------------------------------------------------
# Rollover
# --------------------------------------------------------------------------


def test_rollover_catches_up_through_several_missed_periods(db):
    from app.models import Subscription
    from sqlalchemy import select

    subscription = db.scalar(select(Subscription).where(Subscription.family_user_id.is_not(None)))
    start = subscription.current_period_start
    far_future = subscription_service.add_months(start, 5)

    subscription_service.advance_period(db, subscription, as_of=far_future)

    assert subscription.current_period_start == subscription_service.add_months(start, 5)
    assert subscription.current_period_end == subscription_service.add_months(start, 6)


def test_rollover_stops_at_a_requested_cancellation(db):
    from app.models import Subscription
    from sqlalchemy import select

    subscription = db.scalar(select(Subscription).where(Subscription.family_user_id.is_not(None)))
    subscription.cancel_at_period_end = True
    period_end = subscription.current_period_end
    db.flush()

    subscription_service.advance_period(
        db, subscription, as_of=subscription_service.add_months(period_end, 3)
    )

    assert subscription.status == SubscriptionStatus.CANCELLED
    assert subscription.cancelled_at == period_end


def test_loyalty_is_granted_once_per_twelve_paid_months(db):
    from app.models import Subscription
    from sqlalchemy import select

    subscription = db.scalar(select(Subscription).where(Subscription.family_user_id.is_not(None)))
    subscription.paid_months = 23
    db.flush()

    granted = subscription_service.record_paid_period(db, subscription)
    assert subscription.paid_months == 24
    assert len(granted) == 1

    granted_again = subscription_service.record_paid_period(db, subscription)
    assert granted_again == []


def test_an_annual_payment_earns_the_loyalty_reward_at_once(db):
    """Twelve months paid for is twelve paid months, however it was paid."""
    from app.models import Subscription
    from sqlalchemy import select

    subscription = db.scalar(select(Subscription).where(Subscription.family_user_id.is_not(None)))
    subscription.paid_months = 0
    subscription.billing_cycle = BillingCycle.ANNUAL
    db.flush()

    granted = subscription_service.record_paid_period(db, subscription)
    assert subscription.paid_months == 12
    assert len(granted) == 1
