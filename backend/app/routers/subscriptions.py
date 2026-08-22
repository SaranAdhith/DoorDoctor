"""Plans and subscription management (§3)."""

from typing import Any

from fastapi import APIRouter, Query

from ..core.dependencies import (
    AdminUser,
    CurrentUser,
    DbSession,
    FamilyOrAdminUser,
    authorize_subscription,
)
from ..core.exceptions import NotFoundError
from ..models import BillingCycle
from ..schemas.subscription import CancelRequest, ChangePlanRequest, PlanOut, SubscriptionOut
from ..services import subscription_service

router = APIRouter(tags=["subscriptions"])


@router.get("/plans", response_model=list[PlanOut], summary="Published price list")
def plans(
    db: DbSession,
    current_user: CurrentUser,
    audience: str | None = Query(default=None, description="individual | corporate | institution"),
) -> list[dict[str, Any]]:
    """Every sellable plan with its entitlements.

    Readable by any signed-in role — a nurse seeing the price list reveals
    nothing about a patient, and Phase 8 serves the same numbers publicly.
    """
    return [subscription_service.serialize_plan(plan) for plan in subscription_service.list_plans(db, audience)]


@router.get(
    "/subscriptions/me",
    response_model=SubscriptionOut,
    summary="The signed-in family's subscription",
)
def my_subscription(db: DbSession, current_user: FamilyOrAdminUser) -> dict[str, Any]:
    subscription = subscription_service.for_user(db, current_user)
    if subscription is None:
        raise NotFoundError("No subscription is linked to this account.")

    # Reading the page is a fine moment to notice the period has turned over.
    subscription_service.advance_period(db, subscription)
    payload = subscription_service.serialize(db, subscription)
    db.commit()
    return payload


@router.get(
    "/subscriptions",
    response_model=list[SubscriptionOut],
    summary="Every subscription (admin)",
)
def all_subscriptions(db: DbSession, current_user: AdminUser) -> list[dict[str, Any]]:
    subscriptions = subscription_service.list_all(db)
    for subscription in subscriptions:
        subscription_service.advance_period(db, subscription)
    payload = [subscription_service.serialize(db, s) for s in subscriptions]
    db.commit()
    return payload


@router.post(
    "/subscriptions/{subscription_id}/change-plan",
    response_model=SubscriptionOut,
    summary="Move to a different plan or billing cycle",
)
def change_plan(
    subscription_id: int,
    payload: ChangePlanRequest,
    db: DbSession,
    current_user: FamilyOrAdminUser,
) -> dict[str, Any]:
    """Takes effect immediately; the unused remainder of the old plan is credited."""
    subscription = authorize_subscription(db, current_user, subscription_id)
    cycle = BillingCycle(payload.billing_cycle) if payload.billing_cycle else None
    subscription_service.change_plan(db, subscription, plan_code=payload.plan_code, cycle=cycle)
    result = subscription_service.serialize(db, subscription)
    db.commit()
    return result


@router.post(
    "/subscriptions/{subscription_id}/cancel",
    response_model=SubscriptionOut,
    summary="Cancel at the end of the paid period",
)
def cancel(
    subscription_id: int,
    payload: CancelRequest,
    db: DbSession,
    current_user: FamilyOrAdminUser,
) -> dict[str, Any]:
    """A family cancels at the period end — they have paid to that date and keep care until it.

    Ending a subscription mid-period is an admin action, so `immediate` is
    ignored for a family caller rather than trusted from the request body.
    """
    from ..models import UserRole

    subscription = authorize_subscription(db, current_user, subscription_id)
    immediate = payload.immediate and current_user.role == UserRole.ADMIN
    subscription_service.cancel(db, subscription, immediate=immediate, reason=payload.reason)
    result = subscription_service.serialize(db, subscription)
    db.commit()
    return result


@router.post(
    "/subscriptions/{subscription_id}/resume",
    response_model=SubscriptionOut,
    summary="Undo a pending cancellation",
)
def resume(
    subscription_id: int, db: DbSession, current_user: FamilyOrAdminUser
) -> dict[str, Any]:
    subscription = authorize_subscription(db, current_user, subscription_id)
    subscription_service.resume(db, subscription)
    result = subscription_service.serialize(db, subscription)
    db.commit()
    return result
