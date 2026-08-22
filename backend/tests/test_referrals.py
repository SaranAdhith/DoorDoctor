"""Referrals: codes, invitations, conversion and the reward."""

from app.core import pricing
from app.models import Credit, CreditKind, DeliveryLog, Referral, ReferralStatus, Subscription, User
from app.services import billing_service, referral_service, subscription_service
from sqlalchemy import select


def test_family_gets_a_referral_code_and_share_link(client, family_headers):
    body = client.get("/api/v1/referrals/me", headers=family_headers).json()

    assert body["code"].startswith("DD-")
    assert body["code"] in body["share_url"]
    assert body["reward_paise"] == pricing.rupees(3_500), "one month of their own plan"
    assert body["friend_credit_paise"] == pricing.REFERRED_WELCOME_CREDIT_PAISE


def test_the_code_is_stable_across_reads(client, family_headers):
    first = client.get("/api/v1/referrals/me", headers=family_headers).json()["code"]
    second = client.get("/api/v1/referrals/me", headers=family_headers).json()["code"]
    assert first == second


def test_referral_codes_avoid_characters_that_are_misread_aloud(client, family_headers):
    code = client.get("/api/v1/referrals/me", headers=family_headers).json()["code"]
    assert not set(code.removeprefix("DD-")) & set("IO01")


def test_the_seeded_referral_converted_and_paid_out(client, family_headers):
    body = client.get("/api/v1/referrals/me", headers=family_headers).json()

    assert body["joined_count"] == 1
    assert body["total_earned_paise"] == pricing.rupees(3_500)
    assert body["referrals"][0]["status"] == "rewarded"


def test_the_referred_address_is_masked(client, family_headers):
    """The list is also read by admins; it must not become a contact harvest."""
    body = client.get("/api/v1/referrals/me", headers=family_headers).json()
    shown = body["referrals"][0]["email"]

    assert "meera@doordoctor.in" != shown
    assert shown.startswith("me")
    assert shown.endswith("@doordoctor.in")
    assert "*" in shown


def test_inviting_a_friend_records_and_sends_it(client, family_headers, db):
    response = client.post(
        "/api/v1/referrals/invite", json={"email": "A.Friend@Example.com"}, headers=family_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["summary"]["pending_count"] == 1

    referral = db.scalar(select(Referral).where(Referral.referred_email == "a.friend@example.com"))
    assert referral is not None, "the address is stored lowercased"
    assert referral.status == ReferralStatus.PENDING

    delivery = db.scalar(
        select(DeliveryLog).where(DeliveryLog.recipient == "a.friend@example.com")
    )
    assert delivery is not None, "invitations go through the Phase 3 delivery seam"
    assert referral.code in delivery.body


def test_inviting_an_existing_account_says_nothing_about_it(client, family_headers):
    """The same sentence covers "already a customer" and "already invited"."""
    first = client.post(
        "/api/v1/referrals/invite", json={"email": "meera@doordoctor.in"}, headers=family_headers
    )
    second = client.post(
        "/api/v1/referrals/invite", json={"email": "brand-new@example.com"}, headers=family_headers
    )
    assert first.status_code == 400
    assert second.status_code == 200

    repeat = client.post(
        "/api/v1/referrals/invite", json={"email": "brand-new@example.com"}, headers=family_headers
    )
    assert repeat.status_code == 400
    assert repeat.json()["detail"] == first.json()["detail"]


def test_you_cannot_refer_yourself(client, family_headers):
    response = client.post(
        "/api/v1/referrals/invite", json={"email": "family@doordoctor.in"}, headers=family_headers
    )
    assert response.status_code == 400


def test_invitations_are_rate_limited(client, family_headers):
    """Same limiter as the password-reset link — an invite emails a third party."""
    statuses = [
        client.post(
            "/api/v1/referrals/invite",
            json={"email": f"friend{index}@example.com"},
            headers=family_headers,
        ).status_code
        for index in range(12)
    ]
    assert statuses.count(200) == 10
    assert 429 in statuses


def test_only_a_family_member_holds_referrals(client, nurse_headers, admin_headers):
    assert client.get("/api/v1/referrals/me", headers=nurse_headers).status_code == 403
    assert client.get("/api/v1/referrals/me", headers=admin_headers).status_code == 403


def test_the_referrer_is_paid_only_when_the_referred_family_pays(db):
    """A reward on signup alone would let anyone farm credits with dead accounts."""
    from app.core.security import hash_password
    from app.models import BillingCycle, UserRole

    referrer_subscription = db.scalar(
        select(Subscription).join(User, Subscription.family_user_id == User.id).where(
            User.email == "family@doordoctor.in"
        )
    )
    code = subscription_service.ensure_referral_code(db, referrer_subscription)
    earned_before = db.scalar(
        select(Credit).where(
            Credit.subscription_id == referrer_subscription.id, Credit.kind == CreditKind.REFERRAL
        )
    )

    newcomer = User(
        name="Anand Pillai",
        email="anand@example.com",
        password_hash=hash_password("Demo@123"),
        role=UserRole.FAMILY,
    )
    db.add(newcomer)
    db.flush()
    newcomer_subscription = subscription_service.create(
        db,
        plan=subscription_service.get_plan(db, "essential"),
        family_user_id=newcomer.id,
        cycle=BillingCycle.MONTHLY,
    )

    referral = referral_service.record_signup(db, code=code, user=newcomer)
    assert referral.status == ReferralStatus.JOINED

    # Signing up alone pays the referrer nothing.
    rewards = db.scalars(
        select(Credit).where(
            Credit.subscription_id == referrer_subscription.id,
            Credit.kind == CreditKind.REFERRAL,
            Credit.id != (earned_before.id if earned_before else -1),
        )
    ).all()
    assert rewards == []

    # The newcomer's welcome credit lands immediately, though.
    welcome = db.scalar(
        select(Credit).where(Credit.subscription_id == newcomer_subscription.id)
    )
    assert welcome.amount_paise == pricing.REFERRED_WELCOME_CREDIT_PAISE

    # Paying their first invoice is what converts the referral.
    invoice = billing_service.generate_invoice(db, newcomer_subscription)
    billing_service.mark_paid(db, invoice)

    db.refresh(referral)
    assert referral.status == ReferralStatus.REWARDED
    assert referral.reward_paise == pricing.rupees(3_500)


def test_a_referral_is_rewarded_only_once(db):
    referral = db.scalar(select(Referral).where(Referral.status == ReferralStatus.REWARDED))
    assert referral is not None
    assert referral_service.reward_referrer(db, referral) is None


def test_stale_invitations_expire(db, client, family_headers):
    from datetime import timedelta

    from app.database import now

    client.post(
        "/api/v1/referrals/invite", json={"email": "slow@example.com"}, headers=family_headers
    )
    referral = db.scalar(select(Referral).where(Referral.referred_email == "slow@example.com"))
    referral.expires_at = now() - timedelta(days=1)
    db.flush()

    assert referral_service.expire_stale(db) >= 1
    db.refresh(referral)
    assert referral.status == ReferralStatus.EXPIRED
