"""Referrals (§3)."""

from typing import Any

from fastapi import APIRouter, Request

from ..core.dependencies import DbSession, FamilyUser
from ..core.exceptions import NotFoundError
from ..core.ratelimit import limiter
from ..schemas.referral import ReferralInviteRequest, ReferralInviteResponse, ReferralSummaryOut
from ..services import referral_service, subscription_service

router = APIRouter(prefix="/referrals", tags=["referrals"])

# An invite is an email sent to a third party on a customer's say-so, so it gets
# the same treatment as the password-reset link: a budget per sender and per IP.
INVITES_PER_USER = (10, 3600)
INVITES_PER_IP = (30, 3600)


def _subscription_or_404(db, user):
    subscription = subscription_service.for_user(db, user)
    if subscription is None:
        raise NotFoundError("No subscription is linked to this account.")
    return subscription


@router.get("/me", response_model=ReferralSummaryOut, summary="Referral code and history")
def my_referrals(db: DbSession, current_user: FamilyUser) -> dict[str, Any]:
    subscription = _subscription_or_404(db, current_user)
    return referral_service.summary(db, subscription=subscription, user=current_user)


@router.post("/invite", response_model=ReferralInviteResponse, summary="Invite a family by email")
def invite(
    payload: ReferralInviteRequest,
    request: Request,
    db: DbSession,
    current_user: FamilyUser,
) -> dict[str, Any]:
    ip = request.client.host if request.client else "unknown"
    user_limit, user_window = INVITES_PER_USER
    ip_limit, ip_window = INVITES_PER_IP
    limiter.check("referral-invite:ip", ip, limit=ip_limit, per_seconds=ip_window)
    limiter.check("referral-invite:user", str(current_user.id), limit=user_limit, per_seconds=user_window)

    subscription = _subscription_or_404(db, current_user)
    referral_service.invite(db, subscription=subscription, referrer=current_user, email=payload.email)

    return {
        "message": "Invitation sent. You will be credited when they join and pay their first month.",
        "summary": referral_service.summary(db, subscription=subscription, user=current_user),
    }
