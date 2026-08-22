"""Referrals (§3).

Second consumer of two Phase 3 abstractions, which is the point of having built
them as abstractions rather than as parts of the password-reset flow: invites go
out through `notification_delivery`, and the invite endpoint is budgeted by
`core/ratelimit`.

A referral reward is not its own currency — it becomes a `Credit`, the same row a
loyalty reward creates, and billing applies both without knowing the difference.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import pricing
from ..core.exceptions import BadRequestError
from ..config import settings
from ..database import now
from ..models import (
    Credit,
    CreditKind,
    DeliveryChannelName,
    Referral,
    ReferralStatus,
    Subscription,
    User,
)
from . import notification_delivery, subscription_service

logger = logging.getLogger("doordoctor.referrals")


def share_url(code: str) -> str:
    return f"{settings.frontend_base_url.rstrip('/')}/?ref={code}"


def invite(db: Session, *, subscription: Subscription, referrer: User, email: str) -> Referral:
    """Record an invitation and send it. One pending invite per address."""
    address = email.strip().lower()
    if not address or "@" not in address:
        raise BadRequestError("Enter a valid email address.")
    if referrer.email.lower() == address:
        raise BadRequestError("You cannot refer your own account.")

    existing_user = db.scalar(select(User.id).where(User.email == address))
    if existing_user is not None:
        # Says nothing about whether the address has an account — the same
        # sentence covers "already invited" and "already a customer", for the
        # same reason `/auth/forgot-password` answers everyone identically.
        raise BadRequestError("That address cannot be invited right now.")

    code = subscription_service.ensure_referral_code(db, subscription)
    already = db.scalar(
        select(Referral).where(
            Referral.referrer_user_id == referrer.id,
            Referral.referred_email == address,
            Referral.status.in_([ReferralStatus.PENDING, ReferralStatus.JOINED]),
        )
    )
    if already is not None:
        raise BadRequestError("That address cannot be invited right now.")

    referral = Referral(
        code=code,
        referrer_user_id=referrer.id,
        referred_email=address,
        status=ReferralStatus.PENDING,
        expires_at=now() + timedelta(days=pricing.REFERRAL_EXPIRY_DAYS),
    )
    db.add(referral)

    link = share_url(code)
    reward = pricing.REFERRED_WELCOME_CREDIT_PAISE // pricing.PAISE_PER_RUPEE
    notification_delivery.deliver(
        db,
        channel=DeliveryChannelName.EMAIL,
        recipient=address,
        subject=f"{referrer.name} thinks DoorDoctor could help your family",
        body=(
            f"Hello,\n\n"
            f"{referrer.name} uses DoorDoctor to look after a parent at home — trained nurses "
            f"visiting on a schedule, and the whole family able to see how the visit went.\n\n"
            f"Their invitation gives you ₹{reward:,} off your first month:\n\n{link}\n\n"
            f"Referral code: {code}\n\n"
            "DoorDoctor"
        ),
    )

    db.commit()
    logger.info("Referral invite recorded for subscription %s", subscription.id)
    return referral


def record_signup(db: Session, *, code: str, user: User) -> Optional[Referral]:
    """Attach a new account to whoever referred it.

    Nothing signs up inside Phase 4 — there is no public signup until Phase 8 —
    so this is called by the seed and by tests today, and by the signup flow when
    it lands. It is written now because the reward rules belong beside the
    referral, not inside a registration form.
    """
    subscription = subscription_service.by_referral_code(db, code)
    if subscription is None or subscription.family_user_id is None:
        return None
    if subscription.family_user_id == user.id:
        return None

    referral = db.scalar(
        select(Referral).where(
            Referral.code == subscription.referral_code,
            Referral.referred_email == user.email.lower(),
            Referral.status == ReferralStatus.PENDING,
        )
    )
    if referral is None:
        referral = Referral(
            code=subscription.referral_code or code,
            referrer_user_id=subscription.family_user_id,
            referred_email=user.email.lower(),
            status=ReferralStatus.PENDING,
            expires_at=now() + timedelta(days=pricing.REFERRAL_EXPIRY_DAYS),
        )
        db.add(referral)

    referral.referred_user_id = user.id
    referral.status = ReferralStatus.JOINED
    referral.joined_at = now()
    db.flush()

    # The new family's welcome credit lands as soon as they have something to
    # apply it to. The referrer is paid on conversion, not on signup.
    referred_subscription = subscription_service.for_user(db, user)
    if referred_subscription is not None:
        subscription_service.grant_credit(
            db,
            referred_subscription,
            kind=CreditKind.REFERRAL,
            amount_paise=pricing.REFERRED_WELCOME_CREDIT_PAISE,
            reason="Welcome credit from a friend's referral",
            referral_id=referral.id,
        )
    return referral


def reward_referrer(db: Session, referral: Referral) -> Optional[Credit]:
    """Pay the referrer once the family they referred is really a customer.

    Called when the referred family's first invoice is paid, so a referral cannot
    be farmed by creating accounts that never pay.
    """
    if referral.status == ReferralStatus.REWARDED:
        return None

    subscription = db.scalar(
        select(Subscription).where(Subscription.family_user_id == referral.referrer_user_id)
    )
    if subscription is None:
        return None

    amount = subscription.plan.monthly_paise * pricing.REFERRAL_REWARD_MONTHS
    credit = subscription_service.grant_credit(
        db,
        subscription,
        kind=CreditKind.REFERRAL,
        amount_paise=amount,
        reason="Referral reward — a family you introduced joined DoorDoctor",
        referral_id=referral.id,
    )
    referral.status = ReferralStatus.REWARDED
    referral.reward_paise = amount
    referral.rewarded_at = now()
    db.flush()
    return credit


def expire_stale(db: Session) -> int:
    """Age out invitations that never converted, so the screen stays honest."""
    stale = db.scalars(
        select(Referral).where(
            Referral.status == ReferralStatus.PENDING,
            Referral.expires_at.is_not(None),
            Referral.expires_at < now(),
        )
    ).all()
    for referral in stale:
        referral.status = ReferralStatus.EXPIRED
    db.flush()
    return len(stale)


def summary(db: Session, *, subscription: Subscription, user: User) -> dict[str, Any]:
    expire_stale(db)
    code = subscription_service.ensure_referral_code(db, subscription)

    referrals = db.scalars(
        select(Referral)
        .where(Referral.referrer_user_id == user.id)
        .order_by(Referral.created_at.desc(), Referral.id.desc())
    ).all()

    credits = db.scalars(
        select(Credit)
        .where(Credit.subscription_id == subscription.id, Credit.kind == CreditKind.REFERRAL)
        .order_by(Credit.created_at.desc())
    ).all()

    earned = sum(credit.amount_paise for credit in credits)
    db.commit()

    return {
        "code": code,
        "share_url": share_url(code),
        "reward_months": pricing.REFERRAL_REWARD_MONTHS,
        "reward_paise": subscription.plan.monthly_paise * pricing.REFERRAL_REWARD_MONTHS,
        "friend_credit_paise": pricing.REFERRED_WELCOME_CREDIT_PAISE,
        "total_earned_paise": earned,
        "joined_count": sum(
            1 for r in referrals if r.status in (ReferralStatus.JOINED, ReferralStatus.REWARDED)
        ),
        "pending_count": sum(1 for r in referrals if r.status == ReferralStatus.PENDING),
        "referrals": [
            {
                "id": r.id,
                "email": _mask_email(r.referred_email),
                "status": r.status.value,
                "reward_paise": r.reward_paise,
                "created_at": r.created_at,
                "joined_at": r.joined_at,
                "rewarded_at": r.rewarded_at,
            }
            for r in referrals
        ],
    }


def _mask_email(address: str | None) -> str:
    """The referrer invited them, so they see enough to recognise the invite.

    Not the full address: this list is also read by admins, and a referral list
    should not become a way to harvest the contacts of every customer.
    """
    if not address:
        return "Shared by link"
    local, _, domain = address.partition("@")
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}{'*' * max(3, len(local) - len(visible))}@{domain}"
