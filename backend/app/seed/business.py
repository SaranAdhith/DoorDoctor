"""The commercial side of the demo: price list, subscriptions, invoices, orgs.

**Carried across from Phase 4 intact.** STATE.md is explicit about why: this
module builds its billing history by *calling* `billing_service` and
`subscription_service` rather than by writing invoice rows. If the loyalty rule
or the credit arithmetic breaks, the demo data is visibly wrong on the next seed
instead of being quietly fabricated around the bug. Replacing these calls with
literal rows would silently stop testing the thing they exist to test.

Phase 5 extends it in three ways and changes nothing else:

* `_bill_history` steps by the subscription's own cycle, so an annual
  subscription is billed once a year instead of twelve times a year.
* Seeded payments pass an explicit `reference=`, because
  `payment_gateway.charge()` mints `MAN-<random>` through `secrets` and a
  deterministic seed cannot contain a random reference.
* `seed_population_billing` gives the wider family roster a *spread* of tenures.
  Fourteen months each would be both slower and a worse demo than a real book of
  business where some accounts signed up last month.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from ..core import pricing
from ..database import now
from ..models import (
    BillingCycle,
    InvoiceStatus,
    Organization,
    OrganizationType,
    Subscription,
    SubscriptionStatus,
    User,
)
from ..services import billing_service, referral_service, subscription_service

# How much billing history the demo family opens with. Fourteen months is the
# shortest span that shows a loyalty reward already earned at month twelve *and*
# the free month it bought at thirteen.
SUBSCRIPTION_HISTORY_MONTHS = 14
# Where the current billing period starts, relative to whenever the demo is run.
# Five days back means the period is genuinely in progress — some of the visit
# allowance spent, the invoice raised and inside its payment terms, the renewal
# date still ahead — on any day someone opens the demo.
PERIOD_START_DAYS_AGO = 5


def billing_anchor() -> datetime:
    """The start of the period the demo subscriptions are currently in."""
    return datetime.combine(
        (now() - timedelta(days=PERIOD_START_DAYS_AGO)).date(), time(hour=9, minute=0)
    )


def _seed_reference(subscription: Subscription, index: int) -> str:
    """A stable payment reference for a seeded settlement.

    The gateway boundary mints `MAN-<random>`, which is right in production and
    wrong in a fixed-seed dataset. Passing a reference also keeps the seed off
    the charge path entirely, which is the honest thing for money that never
    moved.
    """
    return f"SEED-{subscription.id:04d}-{index:03d}"


def _bill_history(
    db: Session, subscription: Subscription, periods: int, *, settle_current: bool = True
) -> None:
    """Invoice and settle every *ended* period, then issue the current one.

    The `period_end` guard matters for annual subscribers. Ten months into a
    twelve-month term there is nothing to settle but the one payment already
    made, and billing a period that has not ended would try to pay the invoice
    for the period still running — which is the invoice the next few lines are
    about to raise.
    """
    start = subscription.started_at
    step = 12 if subscription.billing_cycle == BillingCycle.ANNUAL else 1
    today = now()

    for index in range(periods):
        period_start = subscription_service.add_months(start, index * step)
        period_end = subscription_service.add_months(start, (index + 1) * step)
        if period_end > today:
            break
        invoice = billing_service.generate_invoice(
            db,
            subscription,
            period_start=period_start,
            period_end=period_end,
            issued_at=period_start,
        )
        billing_service.mark_paid(db, invoice, reference=_seed_reference(subscription, index))
        # Backdated to the day after it was raised. `mark_paid` stamps `paid_at`
        # with the real clock, which is right in production and wrong here — it
        # would report fourteen months of revenue as collected this morning.
        invoice.paid_at = period_start + timedelta(days=1)

    subscription_service.advance_period(db, subscription)

    current = billing_service.generate_invoice(db, subscription)
    if settle_current and current.status != InvoiceStatus.PAID:
        billing_service.mark_paid(db, current, reference=_seed_reference(subscription, periods))
        current.paid_at = current.issued_at + timedelta(days=1)
    db.flush()


def seed_business(db: Session, family_user: User) -> dict[str, object]:
    """The commercial side: price list, subscriptions, invoices, referral, orgs."""
    subscription_service.sync_plans(db)

    anchor = billing_anchor()
    started = subscription_service.add_months(anchor, -SUBSCRIPTION_HISTORY_MONTHS)

    subscription = subscription_service.create(
        db,
        plan=subscription_service.get_plan(db, pricing.CARE_PLUS.code),
        family_user_id=family_user.id,
        cycle=BillingCycle.MONTHLY,
        started_at=started,
    )
    _bill_history(db, subscription, SUBSCRIPTION_HISTORY_MONTHS, settle_current=False)

    # Part of this period's allowance is spent, so the meters read like a month
    # in progress rather than an untouched plan.
    subscription_service.consume_quota(db, subscription, "visits", 2)
    subscription_service.consume_quota(db, subscription, "lab_panels", 1)

    # ---- a referral that converted ---------------------------------------
    referred_user = User(
        name="Meera Raghavan",
        email="meera@doordoctor.in",
        phone="+91 90000 00004",
        password_hash=family_user.password_hash,  # every demo account shares Demo@123
        role=family_user.role,
        is_active=True,
    )
    db.add(referred_user)
    db.flush()

    referred_subscription = subscription_service.create(
        db,
        plan=subscription_service.get_plan(db, pricing.ESSENTIAL.code),
        family_user_id=referred_user.id,
        cycle=BillingCycle.MONTHLY,
        started_at=subscription_service.add_months(anchor, -3),
    )
    referral_service.record_signup(
        db,
        code=subscription_service.ensure_referral_code(db, subscription),
        user=referred_user,
    )
    # Their first settled invoice is what pays the referrer, so the reward lands
    # here rather than being written in by hand.
    _bill_history(db, referred_subscription, 3)

    # ---- organization accounts -------------------------------------------
    corporate = Organization(
        name="Ashwin Technologies Pvt Ltd",
        org_type=OrganizationType.CORPORATE,
        seats=40,
        contact_name="Priya Nair",
        contact_email="benefits@ashwintech.example",
        contact_phone="+91 90000 00005",
        city="Bengaluru",
    )
    institution = Organization(
        name="Sandhya Senior Living",
        org_type=OrganizationType.INSTITUTION,
        seats=25,
        contact_name="Colonel R. Iyer (Retd)",
        contact_email="care@sandhyaliving.example",
        contact_phone="+91 90000 00006",
        city="Mysuru",
    )
    db.add_all([corporate, institution])
    db.flush()

    corporate_subscription = subscription_service.create(
        db,
        plan=subscription_service.get_plan(db, pricing.CORPORATE.code),
        organization_id=corporate.id,
        cycle=BillingCycle.MONTHLY,
        seats=corporate.seats,
        started_at=subscription_service.add_months(anchor, -6),
    )
    _bill_history(db, corporate_subscription, 6)

    institution_subscription = subscription_service.create(
        db,
        plan=subscription_service.get_plan(db, pricing.INSTITUTION_25.code),
        organization_id=institution.id,
        cycle=BillingCycle.MONTHLY,
        seats=institution.seats,
        started_at=subscription_service.add_months(anchor, -9),
    )
    _bill_history(db, institution_subscription, 9)

    db.flush()
    return {
        "subscription_id": subscription.id,
        "referral_code": subscription.referral_code,
        "paid_months": subscription.paid_months,
    }


# --------------------------------------------------------------------------
# Phase 5 — the wider book of business
# --------------------------------------------------------------------------


def subscribe_family(db: Session, user: User, spec) -> Subscription:
    """One family's subscription and its whole invoice history.

    `spec` is a `demo_data.FamilySpec`. The tenure spread is deliberate: giving
    all eighteen families fourteen months would be ~250 invoices of identical
    history, which is slower to build and a *worse* demo than a book of business
    where some accounts are three years old and some signed up last month.
    """
    anchor = billing_anchor()
    cycle = BillingCycle.ANNUAL if spec.annual else BillingCycle.MONTHLY
    # An annual subscriber's tenure is quoted in months like everyone else's;
    # the number of billing *periods* is what differs.
    periods = max(1, spec.tenure_months // 12) if spec.annual else spec.tenure_months
    started = subscription_service.add_months(anchor, -spec.tenure_months)

    subscription = subscription_service.create(
        db,
        plan=subscription_service.get_plan(db, spec.plan_code),
        family_user_id=user.id,
        cycle=cycle,
        started_at=started,
    )

    # A lapsed account has paid every period except the one in flight — which is
    # what an outstanding balance on the revenue screen actually is.
    _bill_history(db, subscription, periods, settle_current=not spec.lapsed)

    if spec.lapsed:
        subscription.status = SubscriptionStatus.PAST_DUE
    if spec.cancelling:
        subscription_service.cancel(db, subscription)

    db.flush()
    return subscription
