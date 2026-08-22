"""Plans, entitlements, metered quotas, period rollover and loyalty (§3).

The rule this module exists to enforce: **nothing outside it branches on a tier
name.** Callers ask `entitlement(subscription, key)` or `consume_quota(...)`, and
the answer comes from data on the plan row that was generated from
`core/pricing.py`. Phase 9 can add a fourth tier without touching a service.
"""

from __future__ import annotations

import logging
import secrets
from calendar import monthrange
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..core import pricing
from ..core.exceptions import BadRequestError, ConflictError, NotFoundError
from ..database import now
from ..models import (
    BillingCycle,
    Credit,
    CreditKind,
    Plan,
    PlanAudience,
    QuotaUsage,
    Subscription,
    SubscriptionStatus,
    User,
    UserRole,
)

logger = logging.getLogger("doordoctor.subscriptions")

REFERRAL_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I/O/0/1 — these get read aloud
REFERRAL_CODE_LENGTH = 6


# --------------------------------------------------------------------------
# Calendar helpers
# --------------------------------------------------------------------------


def add_months(moment: datetime, months: int) -> datetime:
    """Calendar-correct month arithmetic, clamping to the end of a short month.

    31 January + 1 month is 28 February, not 3 March. Doing this with
    `timedelta(days=30)` drifts a subscription's billing date by five days a year.
    """
    total = moment.month - 1 + months
    year = moment.year + total // 12
    month = total % 12 + 1
    day = min(moment.day, monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def period_end_for(start: datetime, cycle: BillingCycle) -> datetime:
    return add_months(start, 12 if cycle == BillingCycle.ANNUAL else 1)


def _window_containing(anchor: datetime, as_of: datetime, step_months: int) -> tuple[datetime, datetime]:
    """The `step_months`-long window, anchored at `anchor`, that contains `as_of`."""
    if as_of < anchor:
        return anchor, add_months(anchor, step_months)
    # Jump straight to the neighbourhood, then walk the last step or two. The
    # estimate can be off by one when the day-of-month clamps, so it is corrected
    # rather than trusted.
    steps = ((as_of.year - anchor.year) * 12 + (as_of.month - anchor.month)) // step_months
    steps = max(steps, 0)
    while add_months(anchor, steps * step_months) > as_of:
        steps -= 1
    while add_months(anchor, (steps + 1) * step_months) <= as_of:
        steps += 1
    start = add_months(anchor, steps * step_months)
    return start, add_months(anchor, (steps + 1) * step_months)


# --------------------------------------------------------------------------
# Plans
# --------------------------------------------------------------------------


def sync_plans(db: Session) -> list[Plan]:
    """Write `core/pricing.PLANS` into the `plans` table. Idempotent.

    Prices live in the constants module; the table is a projection of it so the
    API can join and filter. Running this twice changes nothing.
    """
    existing = {plan.code: plan for plan in db.scalars(select(Plan)).all()}
    synced: list[Plan] = []

    for spec in pricing.PLANS:
        plan = existing.get(spec.code)
        if plan is None:
            plan = Plan(code=spec.code)
            db.add(plan)
        plan.name = spec.name
        plan.audience = PlanAudience(spec.audience)
        plan.tagline = spec.tagline
        plan.monthly_paise = spec.monthly_paise
        plan.annual_paise = spec.annual_paise
        plan.recommended = spec.recommended
        plan.active = True
        plan.sort_order = spec.sort_order
        plan.unit_label = spec.unit_label
        plan.unit_included = spec.unit_included
        plan.unit_paise = spec.unit_paise
        plan.unit_period = spec.unit_period
        plan.entitlements = dict(spec.entitlements)
        synced.append(plan)

    # A plan removed from the constants module is retired, never deleted —
    # invoices and subscriptions still point at it.
    for code, plan in existing.items():
        if code not in pricing.PLANS_BY_CODE:
            plan.active = False

    db.flush()
    return synced


def list_plans(db: Session, audience: str | None = None) -> list[Plan]:
    query = select(Plan).where(Plan.active.is_(True)).order_by(Plan.sort_order, Plan.id)
    if audience:
        query = query.where(Plan.audience == PlanAudience(audience))
    return list(db.scalars(query).all())


def get_plan(db: Session, code: str) -> Plan:
    plan = db.scalar(select(Plan).where(Plan.code == code, Plan.active.is_(True)))
    if plan is None:
        raise NotFoundError("Plan not found.")
    return plan


# --------------------------------------------------------------------------
# Subscriptions
# --------------------------------------------------------------------------


def _loaded(query):
    return query.options(
        selectinload(Subscription.plan),
        selectinload(Subscription.organization),
        selectinload(Subscription.family_user),
    )


def for_user(db: Session, user: User) -> Optional[Subscription]:
    """The family's subscription, or None. Only family accounts hold one directly."""
    if user.role != UserRole.FAMILY:
        return None
    return db.scalar(
        _loaded(select(Subscription))
        .where(Subscription.family_user_id == user.id)
        .order_by(Subscription.id.desc())
    )


def get(db: Session, subscription_id: int) -> Subscription:
    subscription = db.scalar(
        _loaded(select(Subscription)).where(Subscription.id == subscription_id)
    )
    if subscription is None:
        raise NotFoundError("Subscription not found.")
    return subscription


def list_all(db: Session) -> list[Subscription]:
    return list(
        db.scalars(_loaded(select(Subscription)).order_by(Subscription.id)).all()
    )


def create(
    db: Session,
    *,
    plan: Plan,
    family_user_id: int | None = None,
    organization_id: int | None = None,
    cycle: BillingCycle = BillingCycle.MONTHLY,
    seats: int = 1,
    started_at: datetime | None = None,
) -> Subscription:
    if (family_user_id is None) == (organization_id is None):
        raise BadRequestError("A subscription belongs to exactly one family or one organization.")

    start = started_at or now()
    subscription = Subscription(
        plan_id=plan.id,
        family_user_id=family_user_id,
        organization_id=organization_id,
        billing_cycle=cycle,
        seats=max(1, seats),
        started_at=start,
        current_period_start=start,
        current_period_end=period_end_for(start, cycle),
        status=SubscriptionStatus.ACTIVE,
    )
    db.add(subscription)
    db.flush()
    return subscription


# --------------------------------------------------------------------------
# Entitlements
# --------------------------------------------------------------------------


def entitlement(subscription: Subscription, key: str, default: Any = None) -> Any:
    """Look an entitlement up on the plan. The only way anything should ask."""
    if subscription is None or subscription.plan is None:
        return default
    entitlements = subscription.plan.entitlements or {}
    return entitlements.get(key, default)


def has_entitlement(subscription: Subscription, key: str) -> bool:
    """True when the plan grants the feature at all.

    `None` means unlimited and is therefore true; `0` and `False` are not.
    """
    value = entitlement(subscription, key, default=False)
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    return bool(value)


def price_paise(plan: Plan, cycle: BillingCycle, seats: int = 1) -> int:
    """What one billing period costs.

    Corporate is quoted per employee per month, so seats multiply. An
    institutional band price already covers its residents, so it does not.
    """
    if plan.audience == PlanAudience.CORPORATE and plan.unit_paise:
        return plan.unit_paise * max(1, seats)
    amount = plan.price_paise(cycle)
    if amount is None:
        raise BadRequestError(f"{plan.name} is not sold on a {cycle.value} cycle.")
    return amount


# --------------------------------------------------------------------------
# Quotas
# --------------------------------------------------------------------------


def quota_window(subscription: Subscription, spec: pricing.QuotaSpec, as_of: datetime) -> tuple[datetime, datetime]:
    """A quota resets on its own cadence, anchored to when the subscription began.

    A monthly allowance resets every month even on an annual billing cycle — the
    two are unrelated, and tying them together would give an annual subscriber one
    year's visits to use in January.
    """
    step = 12 if spec.period == "year" else 1
    return _window_containing(subscription.started_at, as_of, step)


def _usage_row(
    db: Session, subscription: Subscription, spec: pricing.QuotaSpec, as_of: datetime
) -> QuotaUsage:
    start, end = quota_window(subscription, spec, as_of)
    row = db.scalar(
        select(QuotaUsage).where(
            QuotaUsage.subscription_id == subscription.id,
            QuotaUsage.quota == spec.name,
            QuotaUsage.period_start == start,
        )
    )
    if row is None:
        row = QuotaUsage(
            subscription_id=subscription.id,
            quota=spec.name,
            period_start=start,
            period_end=end,
            used=0,
        )
        db.add(row)
        db.flush()
    return row


def quota_status(
    db: Session, subscription: Subscription, as_of: datetime | None = None
) -> list[dict[str, Any]]:
    """Every meter on this plan: what it allows, what is spent, what is left."""
    moment = as_of or now()
    statuses: list[dict[str, Any]] = []
    for spec in pricing.QUOTAS:
        limit = entitlement(subscription, spec.entitlement_key, default=0)
        row = _usage_row(db, subscription, spec, moment)
        unlimited = limit is None
        statuses.append(
            {
                "quota": spec.name,
                "label": spec.label,
                "period": spec.period,
                "limit": limit,
                "used": row.used,
                "remaining": None if unlimited else max(0, int(limit) - row.used),
                "unlimited": unlimited,
                "period_start": row.period_start,
                "period_end": row.period_end,
            }
        )
    return statuses


def consume_quota(
    db: Session, subscription: Subscription, quota: str, amount: int = 1, as_of: datetime | None = None
) -> QuotaUsage:
    """Spend part of an allowance, or refuse.

    Raises `ConflictError` (409) rather than 403 — the caller is allowed to do
    this, they have simply used it all up, and the two need different words in
    the UI.
    """
    spec = pricing.QUOTAS_BY_NAME.get(quota)
    if spec is None:
        raise BadRequestError(f"Unknown quota '{quota}'.")

    limit = entitlement(subscription, spec.entitlement_key, default=0)
    row = _usage_row(db, subscription, spec, as_of or now())

    if limit is not None and row.used + amount > int(limit):
        raise ConflictError(
            f"{spec.label} allowance for this {spec.period} is used up "
            f"({row.used} of {int(limit)}). Upgrading the plan adds more."
        )

    row.used += amount
    db.flush()
    return row


def release_quota(
    db: Session, subscription: Subscription, quota: str, amount: int = 1, as_of: datetime | None = None
) -> QuotaUsage:
    """Give part of an allowance back. The exact inverse of `consume_quota`.

    A consult cancelled inside the cancellation window did not happen, so it must
    not count against the month. This lives beside `consume_quota` rather than in
    the consult service so the pair cannot drift — the meter that spends and the
    meter that refunds have to agree about which period a booking belonged to.

    Floors at zero. A refund larger than what was spent is a bug elsewhere, and
    a negative meter would show a family more consults left than their plan
    grants.
    """
    spec = pricing.QUOTAS_BY_NAME.get(quota)
    if spec is None:
        raise BadRequestError(f"Unknown quota '{quota}'.")

    row = _usage_row(db, subscription, spec, as_of or now())
    row.used = max(0, row.used - amount)
    db.flush()
    return row


# --------------------------------------------------------------------------
# Credits — the one mechanism behind both referral and loyalty rewards
# --------------------------------------------------------------------------


def grant_credit(
    db: Session,
    subscription: Subscription,
    *,
    kind: CreditKind,
    amount_paise: int,
    reason: str,
    referral_id: int | None = None,
) -> Credit | None:
    if amount_paise <= 0:
        return None
    credit = Credit(
        subscription_id=subscription.id,
        kind=kind,
        amount_paise=amount_paise,
        reason=reason,
        referral_id=referral_id,
    )
    db.add(credit)
    db.flush()
    logger.info(
        "Credit granted: subscription=%s kind=%s paise=%s", subscription.id, kind.value, amount_paise
    )
    return credit


def unspent_credits(db: Session, subscription: Subscription) -> list[Credit]:
    return list(
        db.scalars(
            select(Credit)
            .where(
                Credit.subscription_id == subscription.id,
                Credit.applied_invoice_id.is_(None),
            )
            .order_by(Credit.created_at, Credit.id)
        ).all()
    )


def unspent_credit_paise(db: Session, subscription: Subscription) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(Credit.amount_paise), 0)).where(
            Credit.subscription_id == subscription.id,
            Credit.applied_invoice_id.is_(None),
        )
    )
    return int(total or 0)


# --------------------------------------------------------------------------
# Period rollover and loyalty
# --------------------------------------------------------------------------


def advance_period(
    db: Session, subscription: Subscription, as_of: datetime | None = None
) -> Subscription:
    """Walk the billing window forward until it contains `as_of`.

    A loop rather than a single step, because nothing guarantees this runs once
    a month. A subscription ignored for a quarter must still land in the right
    period, and a subscription that asked to cancel must stop at the boundary
    where it asked to, not at today.
    """
    moment = as_of or now()
    guard = 0
    while subscription.is_live and subscription.current_period_end <= moment:
        guard += 1
        if guard > 600:  # ~50 years of monthly periods; a runaway loop, not a real account
            logger.error("advance_period ran away on subscription %s", subscription.id)
            break

        if subscription.cancel_at_period_end:
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.cancelled_at = subscription.current_period_end
            break

        subscription.current_period_start = subscription.current_period_end
        subscription.current_period_end = period_end_for(
            subscription.current_period_start, subscription.billing_cycle
        )

    db.flush()
    return subscription


def record_paid_period(db: Session, subscription: Subscription) -> list[Credit]:
    """Count a paid billing period and grant loyalty when it crosses 12.

    Loyalty is measured in months *paid for*, not months elapsed, so an annual
    payment advances the counter by twelve at once and earns its reward
    immediately — which is the correct reading of "12 paid months".
    """
    before = subscription.paid_months
    subscription.paid_months = before + (
        12 if subscription.billing_cycle == BillingCycle.ANNUAL else 1
    )

    milestone = pricing.LOYALTY_AFTER_PAID_MONTHS
    rewards_before = before // milestone
    rewards_after = subscription.paid_months // milestone

    granted: list[Credit] = []
    for _ in range(rewards_after - rewards_before):
        amount = subscription.plan.monthly_paise * pricing.LOYALTY_REWARD_MONTHS
        credit = grant_credit(
            db,
            subscription,
            kind=CreditKind.LOYALTY,
            amount_paise=amount,
            reason=f"Loyalty reward — thank you for {subscription.paid_months} months with DoorDoctor",
        )
        if credit is not None:
            granted.append(credit)

    db.flush()
    return granted


# --------------------------------------------------------------------------
# Plan changes and cancellation
# --------------------------------------------------------------------------


def change_plan(
    db: Session, subscription: Subscription, *, plan_code: str, cycle: BillingCycle | None = None
) -> Subscription:
    """Switch plan immediately, crediting whatever was paid for and not used.

    One code path for upgrades and downgrades: the unused remainder of the old
    period becomes a credit, and a fresh period starts today on the new plan.
    Branching on "is this bigger or smaller" would be two paths to keep correct
    forever, and would still owe the customer the same money.
    """
    new_plan = get_plan(db, plan_code)
    new_cycle = cycle or subscription.billing_cycle

    if new_plan.price_paise(new_cycle) is None:
        raise BadRequestError(f"{new_plan.name} is not sold on a {new_cycle.value} cycle.")
    if new_plan.id == subscription.plan_id and new_cycle == subscription.billing_cycle:
        raise BadRequestError(f"This account is already on {new_plan.name}.")
    if not subscription.is_live:
        raise BadRequestError("This subscription is no longer active.")

    moment = now()
    old_plan_name = subscription.plan.name
    unused = _unused_paise(subscription, moment)
    if unused > 0:
        grant_credit(
            db,
            subscription,
            kind=CreditKind.ADJUSTMENT,
            amount_paise=unused,
            reason=f"Unused portion of {old_plan_name}",
        )

    subscription.plan_id = new_plan.id
    subscription.plan = new_plan
    subscription.billing_cycle = new_cycle
    subscription.current_period_start = moment
    subscription.current_period_end = period_end_for(moment, new_cycle)
    # A plan change is a decision to stay, so it clears a pending cancellation.
    subscription.cancel_at_period_end = False
    db.flush()

    logger.info(
        "Subscription %s changed %s -> %s (%s)",
        subscription.id,
        old_plan_name,
        new_plan.name,
        new_cycle.value,
    )
    return subscription


def _unused_paise(subscription: Subscription, moment: datetime) -> int:
    """The paid-for remainder of the current period, in paise."""
    span = (subscription.current_period_end - subscription.current_period_start).total_seconds()
    if span <= 0:
        return 0
    left = (subscription.current_period_end - moment).total_seconds()
    fraction = max(0.0, min(1.0, left / span))
    paid = price_paise(subscription.plan, subscription.billing_cycle, subscription.seats)
    return int(round(paid * fraction))


def cancel(
    db: Session, subscription: Subscription, *, immediate: bool = False, reason: str | None = None
) -> Subscription:
    """Cancel at the end of the paid period by default.

    Someone who has paid to the 30th keeps care until the 30th. Immediate
    cancellation exists for admins and is not what the family-facing button does.
    """
    if subscription.status == SubscriptionStatus.CANCELLED:
        raise BadRequestError("This subscription is already cancelled.")

    if immediate:
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.cancelled_at = now()
        subscription.current_period_end = subscription.cancelled_at
    else:
        subscription.cancel_at_period_end = True

    db.flush()
    logger.info(
        "Subscription %s cancellation requested (immediate=%s) %s",
        subscription.id,
        immediate,
        reason or "",
    )
    return subscription


def resume(db: Session, subscription: Subscription) -> Subscription:
    """Undo a pending cancellation while the period is still running."""
    if subscription.status == SubscriptionStatus.CANCELLED:
        raise BadRequestError("This subscription has already ended. Choose a plan to start again.")
    if not subscription.cancel_at_period_end:
        raise BadRequestError("This subscription is not scheduled to end.")
    subscription.cancel_at_period_end = False
    db.flush()
    return subscription


# --------------------------------------------------------------------------
# Referral codes live on the subscription
# --------------------------------------------------------------------------


def ensure_referral_code(db: Session, subscription: Subscription) -> str:
    """Mint a code on first use. Retries on collision rather than trusting entropy."""
    if subscription.referral_code:
        return subscription.referral_code

    for _ in range(10):
        candidate = "DD-" + "".join(
            secrets.choice(REFERRAL_CODE_ALPHABET) for _ in range(REFERRAL_CODE_LENGTH)
        )
        clash = db.scalar(select(Subscription.id).where(Subscription.referral_code == candidate))
        if clash is None:
            subscription.referral_code = candidate
            db.flush()
            return candidate

    raise ConflictError("Could not allocate a referral code. Please try again.")  # pragma: no cover


def by_referral_code(db: Session, code: str) -> Optional[Subscription]:
    if not code:
        return None
    return db.scalar(
        _loaded(select(Subscription)).where(Subscription.referral_code == code.strip().upper())
    )


def serialize(db: Session, subscription: Subscription, *, include_quotas: bool = True) -> dict[str, Any]:
    """One shape for the API, so family and admin screens read the same fields."""
    plan = subscription.plan
    payload: dict[str, Any] = {
        "id": subscription.id,
        "status": subscription.status.value,
        "billing_cycle": subscription.billing_cycle.value,
        "seats": subscription.seats,
        "started_at": subscription.started_at,
        "current_period_start": subscription.current_period_start,
        "current_period_end": subscription.current_period_end,
        "paid_months": subscription.paid_months,
        "cancel_at_period_end": subscription.cancel_at_period_end,
        "cancelled_at": subscription.cancelled_at,
        "owner_label": subscription.owner_label,
        "organization_id": subscription.organization_id,
        "family_user_id": subscription.family_user_id,
        "renews_at": None if subscription.cancel_at_period_end else subscription.current_period_end,
        "period_price_paise": price_paise(plan, subscription.billing_cycle, subscription.seats),
        "credit_balance_paise": unspent_credit_paise(db, subscription),
        "months_to_loyalty_reward": _months_to_loyalty(subscription),
        "plan": serialize_plan(plan),
    }
    if include_quotas:
        payload["quotas"] = quota_status(db, subscription)
    return payload


def _months_to_loyalty(subscription: Subscription) -> int:
    milestone = pricing.LOYALTY_AFTER_PAID_MONTHS
    return milestone - (subscription.paid_months % milestone)


def serialize_plan(plan: Plan) -> dict[str, Any]:
    return {
        "id": plan.id,
        "code": plan.code,
        "name": plan.name,
        "audience": plan.audience.value,
        "tagline": plan.tagline,
        "monthly_paise": plan.monthly_paise,
        "annual_paise": plan.annual_paise,
        "recommended": plan.recommended,
        "unit_label": plan.unit_label,
        "unit_included": plan.unit_included,
        "unit_paise": plan.unit_paise,
        "unit_period": plan.unit_period,
        "entitlements": plan.entitlements or {},
    }
