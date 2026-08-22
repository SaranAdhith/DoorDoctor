"""Doctor consults (§4.6) — the first enforced quota.

RECORDED and pinned as a literal: Premium includes 2 consults per month.
Everything else is `ASSUMED` and asserted against `core/clinical.py`.
"""

from datetime import timedelta

from sqlalchemy import select

from app.core import clinical, pricing
from app.database import now
from app.models import Consult, ConsultStatus, Patient, QuotaUsage, User
from app.services import consult_service, subscription_service

from .conftest import auth, login


def _slot(hours: int = 48) -> str:
    return (now() + timedelta(hours=hours)).isoformat()


def _book(client, headers, hours: int = 48):
    return client.post(
        "/api/v1/patients/1/consults",
        json={"scheduled_for": _slot(hours), "reason": "Follow-up on blood pressure"},
        headers=headers,
    )


def _remaining(client, headers) -> int:
    return client.get("/api/v1/patients/1/consults/allowance", headers=headers).json()["remaining"]


def _demo_subscription(db):
    user = db.scalar(select(User).where(User.email == "family@doordoctor.in"))
    return user, subscription_service.for_user(db, user)


# --------------------------------------------------------------------------
# The recorded allowance
# --------------------------------------------------------------------------


def test_premium_includes_the_recorded_two_consults_a_month():
    """RECORDED, so a literal — the one entitlement quantity §3 actually gave."""
    assert pricing.PREMIUM.entitlements[pricing.TELEMEDICINE_PER_MONTH] == 2


def test_the_quota_is_resolved_from_the_entitlement_key_not_typed():
    spec = pricing.QUOTAS_BY_NAME[consult_service.CONSULT_QUOTA]
    assert spec.entitlement_key == pricing.TELEMEDICINE_PER_MONTH


def test_the_allowance_screen_reads_the_same_meter_the_refusal_uses(client, family_headers, db):
    body = client.get("/api/v1/patients/1/consults/allowance", headers=family_headers).json()
    _, subscription = _demo_subscription(db)
    status = next(
        q
        for q in subscription_service.quota_status(db, subscription)
        if q["quota"] == consult_service.CONSULT_QUOTA
    )
    assert body["included"] == status["limit"]
    assert body["remaining"] == status["remaining"]


def test_the_allowance_reports_the_assumed_duration_and_window(client, family_headers):
    body = client.get("/api/v1/patients/1/consults/allowance", headers=family_headers).json()
    assert body["duration_minutes"] == clinical.CONSULT_DURATION_MINUTES
    assert body["cancellation_hours"] == clinical.CONSULT_CANCELLATION_HOURS


# --------------------------------------------------------------------------
# Enforcement — the point of the stage
# --------------------------------------------------------------------------


def test_a_consult_can_be_booked_and_spends_the_allowance(client, family_headers):
    before = _remaining(client, family_headers)
    response = _book(client, family_headers)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == ConsultStatus.SCHEDULED.value
    assert _remaining(client, family_headers) == before - 1


def test_booking_past_the_allowance_is_refused_with_409(client, family_headers):
    """409, not 403. The family is entitled to book consults — they have used
    this month's. The client must be able to tell those apart without parsing
    a sentence."""
    for _ in range(_remaining(client, family_headers)):
        assert _book(client, family_headers).status_code == 201

    refused = _book(client, family_headers)
    assert refused.status_code == 409
    assert "allowance" in refused.json()["detail"].lower()


def test_the_refusal_comes_from_the_entitlement_not_a_tier_name(client, family_headers, db):
    """Nothing in this codebase branches on a plan code, and this is the phase
    that would most naturally have broken that."""
    _, subscription = _demo_subscription(db)
    # Take the entitlement to zero without touching the plan's *name*.
    entitlements = dict(subscription.plan.entitlements)
    entitlements[pricing.TELEMEDICINE_PER_MONTH] = 0
    subscription.plan.entitlements = entitlements
    db.commit()

    assert _book(client, family_headers).status_code == 409


def test_a_patient_with_no_plan_cannot_book(client, other_family):
    headers = auth(login(client, other_family["email"]))
    response = client.post(
        f"/api/v1/patients/{other_family['patient_id']}/consults",
        json={"scheduled_for": _slot(), "reason": ""},
        headers=headers,
    )
    assert response.status_code == 409


# --------------------------------------------------------------------------
# Slot validation
# --------------------------------------------------------------------------


def test_a_slot_in_the_past_is_refused(client, family_headers):
    response = _book(client, family_headers, hours=-2)
    assert response.status_code == 400


def test_a_slot_too_far_ahead_is_refused(client, family_headers):
    response = _book(client, family_headers, hours=24 * (clinical.CONSULT_MAX_LEAD_DAYS + 2))
    assert response.status_code == 400
    assert str(clinical.CONSULT_MAX_LEAD_DAYS) in response.json()["detail"]


def test_a_refused_slot_does_not_spend_the_allowance(client, family_headers):
    """The slot is validated before the meter is touched. Getting this backwards
    would charge a family for a booking that never existed."""
    before = _remaining(client, family_headers)
    _book(client, family_headers, hours=-2)
    assert _remaining(client, family_headers) == before


# --------------------------------------------------------------------------
# Cancellation and the refund rule
# --------------------------------------------------------------------------


def test_cancelling_early_hands_the_allowance_back(client, family_headers):
    before = _remaining(client, family_headers)
    consult_id = _book(client, family_headers, hours=48).json()["id"]
    assert _remaining(client, family_headers) == before - 1

    response = client.post(f"/api/v1/consults/{consult_id}/cancel", headers=family_headers)
    assert response.status_code == 200, response.text
    assert response.json()["quota_released"] is True
    assert _remaining(client, family_headers) == before


def test_cancelling_inside_the_window_does_not(client, family_headers):
    """The slot is gone whoever cancels. `ASSUMED` window, read from clinical.py."""
    inside = clinical.CONSULT_CANCELLATION_HOURS - 1
    before = _remaining(client, family_headers)
    consult_id = _book(client, family_headers, hours=inside).json()["id"]

    body = client.post(f"/api/v1/consults/{consult_id}/cancel", headers=family_headers).json()
    assert body["quota_released"] is False
    assert _remaining(client, family_headers) == before - 1


def test_a_cancellation_cannot_refund_twice(client, family_headers):
    before = _remaining(client, family_headers)
    consult_id = _book(client, family_headers, hours=48).json()["id"]
    client.post(f"/api/v1/consults/{consult_id}/cancel", headers=family_headers)
    second = client.post(f"/api/v1/consults/{consult_id}/cancel", headers=family_headers)

    assert second.status_code == 400
    assert _remaining(client, family_headers) == before


def test_the_refund_returns_to_the_period_the_booking_was_made_in(db):
    """A consult booked on the 30th and cancelled on the 2nd must give its
    allowance back to the month it was taken from, not to the new one."""
    patient = db.get(Patient, 1)
    user, _ = _demo_subscription(db)
    booked_at = now() - timedelta(days=40)

    consult = consult_service.book(
        db,
        patient=patient,
        user=user,
        scheduled_for=booked_at + timedelta(days=1),
        as_of=booked_at,
    )
    spec = pricing.QUOTAS_BY_NAME[consult_service.CONSULT_QUOTA]
    old_start, _ = subscription_service.quota_window(consult.subscription, spec, booked_at)
    used_then = db.scalar(
        select(QuotaUsage.used).where(
            QuotaUsage.subscription_id == consult.subscription_id,
            QuotaUsage.quota == spec.name,
            QuotaUsage.period_start == old_start,
        )
    )

    consult_service.cancel(db, consult, user, as_of=booked_at)
    after = db.scalar(
        select(QuotaUsage.used).where(
            QuotaUsage.subscription_id == consult.subscription_id,
            QuotaUsage.quota == spec.name,
            QuotaUsage.period_start == old_start,
        )
    )
    assert after == used_then - 1


def test_a_no_show_is_not_refunded(client, family_headers, admin_headers):
    """The doctor's time was held."""
    before = _remaining(client, family_headers)
    consult_id = _book(client, family_headers).json()["id"]
    response = client.post(f"/api/v1/consults/{consult_id}/no-show", headers=admin_headers)
    assert response.status_code == 200, response.text
    assert _remaining(client, family_headers) == before - 1


def test_release_quota_never_goes_negative(db):
    _, subscription = _demo_subscription(db)
    for _ in range(5):
        subscription_service.release_quota(db, subscription, consult_service.CONSULT_QUOTA)
    row = db.scalar(
        select(QuotaUsage).where(
            QuotaUsage.subscription_id == subscription.id,
            QuotaUsage.quota == consult_service.CONSULT_QUOTA,
        )
    )
    assert row.used == 0


# --------------------------------------------------------------------------
# Lifecycle and access
# --------------------------------------------------------------------------


def test_an_admin_completes_a_consult_with_a_summary(client, family_headers, admin_headers):
    consult_id = _book(client, family_headers).json()["id"]
    response = client.post(
        f"/api/v1/consults/{consult_id}/complete",
        json={"summary": "Reviewed medication, no change advised."},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == ConsultStatus.COMPLETED.value


def test_a_family_cannot_complete_a_consult(client, family_headers):
    consult_id = _book(client, family_headers).json()["id"]
    assert (
        client.post(f"/api/v1/consults/{consult_id}/complete", headers=family_headers).status_code
        == 403
    )


def test_a_nurse_cannot_book_a_consult(client, nurse_headers):
    response = client.post(
        "/api/v1/patients/1/consults", json={"scheduled_for": _slot()}, headers=nurse_headers
    )
    assert response.status_code == 403


def test_someone_elses_consult_is_a_404(client, family_headers, other_family):
    consult_id = _book(client, family_headers).json()["id"]
    headers = auth(login(client, other_family["email"]))
    assert client.post(f"/api/v1/consults/{consult_id}/cancel", headers=headers).status_code == 404


def test_the_upcoming_queue_is_admin_only(client, family_headers, admin_headers):
    _book(client, family_headers)
    assert client.get("/api/v1/consults/upcoming", headers=family_headers).status_code == 403
    upcoming = client.get("/api/v1/consults/upcoming", headers=admin_headers)
    assert upcoming.status_code == 200
    assert len(upcoming.json()) == 1


def test_a_cancelled_consult_is_gone_from_the_upcoming_queue(
    client, family_headers, admin_headers
):
    consult_id = _book(client, family_headers).json()["id"]
    client.post(f"/api/v1/consults/{consult_id}/cancel", headers=family_headers)
    assert client.get("/api/v1/consults/upcoming", headers=admin_headers).json() == []
