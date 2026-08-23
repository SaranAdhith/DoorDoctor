"""Phase 10 — channel routing, preferences and quiet hours (§4.18).

The rule this file exists to hold: **the platform records what it did not do.**
A message held back during quiet hours and a message that could not be sent are
different facts, both written down, and neither is a gap. That is what an admin
needs when a family says "I never got the alert".
"""

from datetime import datetime

import pytest
from sqlalchemy import select

from app.core.ops import CRITICAL_CHANNEL_COUNT
from app.models import (
    AlertSeverity,
    DeliveryChannelName,
    DeliveryLog,
    DeliveryStatus,
    NotificationPreference,
    NotificationType,
    User,
)
from app.services import notification_service
from app.services.notification_service import Recipient

API = "/api/v1"


@pytest.fixture
def family_user(db) -> User:
    return db.query(User).filter(User.email == "family@doordoctor.in").one()


def _plan(db, user, *, critical=False, at=None, type_=NotificationType.ALERT):
    return notification_service.plan_channels(
        db, Recipient(label=user.name, user=user), type_=type_, critical=critical, at=at
    )


def _carrying(plans) -> list[str]:
    return [plan.channel.value for plan in plans if plan.blocked is None]


# --- defaults -------------------------------------------------------------


def test_quiet_hours_are_off_until_somebody_chooses_them(client, family_headers):
    """A platform that silently stops messaging at 21:00 has decided for the family."""
    body = client.get(f"{API}/notifications/preferences", headers=family_headers).json()
    assert body["quiet_hours_enabled"] is False
    assert body["critical_always_delivered"] is True
    assert body["critical_channel_count"] == CRITICAL_CHANNEL_COUNT


def test_push_is_off_by_default_because_it_cannot_reach_anybody(client, family_headers):
    body = client.get(f"{API}/notifications/preferences", headers=family_headers).json()
    assert body["channels"]["push"] is False
    assert body["channels"]["sms"] is True


# --- routing --------------------------------------------------------------


def test_an_ordinary_alert_goes_out_on_one_channel(db, family_user):
    assert len(_carrying(_plan(db, family_user))) == 1


def test_a_critical_alert_goes_out_on_two_channels_that_can_reach_somebody(db, family_user):
    """RECORDED as dual-channel. The correction is 'that can reach somebody'."""
    carrying = _carrying(_plan(db, family_user, critical=True))
    assert len(carrying) == CRITICAL_CHANNEL_COUNT
    assert "push" not in carrying


def test_a_channel_with_no_address_is_recorded_as_an_attempt_that_could_not_be_made(
    db, family_user
):
    plans = {plan.channel: plan for plan in _plan(db, family_user, critical=True)}
    push = plans[DeliveryChannelName.PUSH]
    assert push.blocked == "No address on this channel"
    assert push.status == DeliveryStatus.UNREACHABLE


def test_a_user_with_no_phone_falls_through_to_email(db, family_user):
    family_user.phone = None
    db.flush()
    carrying = _carrying(_plan(db, family_user, critical=True))
    assert carrying == ["email"]


def test_switching_a_channel_off_removes_it_from_routing(client, db, family_headers, family_user):
    client.put(
        f"{API}/notifications/preferences", json={"channels": {"sms": False}}, headers=family_headers
    )
    db.expire_all()
    carrying = _carrying(_plan(db, family_user, critical=True))
    assert "sms" not in carrying
    assert "whatsapp" in carrying


def test_updating_preferences_leaves_the_untouched_channels_alone(client, family_headers):
    client.put(
        f"{API}/notifications/preferences", json={"channels": {"sms": False}}, headers=family_headers
    )
    body = client.put(
        f"{API}/notifications/preferences",
        json={"channels": {"push": True}},
        headers=family_headers,
    ).json()
    assert body["channels"]["sms"] is False
    assert body["channels"]["push"] is True


# --- quiet hours ----------------------------------------------------------


def _quiet(db, user) -> NotificationPreference:
    preference = notification_service.preferences_for(db, user)
    preference.quiet_hours_enabled = True
    preference.quiet_start_hour = 21
    preference.quiet_end_hour = 7
    db.flush()
    return preference


def test_quiet_hours_hold_back_an_ordinary_alert_and_record_it(db, family_user):
    _quiet(db, family_user)
    plans = _plan(db, family_user, at=datetime(2026, 8, 23, 23, 30))
    assert _carrying(plans) == []
    assert any(plan.status == DeliveryStatus.SUPPRESSED for plan in plans)


def test_quiet_hours_never_silence_a_critical_alert(db, family_user):
    """A quiet-hours setting that can silence a critical alert can kill somebody."""
    _quiet(db, family_user)
    carrying = _carrying(_plan(db, family_user, critical=True, at=datetime(2026, 8, 23, 3, 0)))
    assert len(carrying) == CRITICAL_CHANNEL_COUNT


def test_the_quiet_window_wraps_midnight(db, family_user):
    preference = _quiet(db, family_user)
    assert preference.in_quiet_hours(datetime(2026, 8, 23, 22, 0)) is True
    assert preference.in_quiet_hours(datetime(2026, 8, 23, 3, 0)) is True
    assert preference.in_quiet_hours(datetime(2026, 8, 23, 12, 0)) is False


def test_a_window_that_starts_and_ends_at_the_same_hour_is_no_window(db, family_user):
    preference = _quiet(db, family_user)
    preference.quiet_start_hour = preference.quiet_end_hour = 9
    assert preference.in_quiet_hours(datetime(2026, 8, 23, 9, 30)) is False


def test_the_in_app_record_is_written_even_during_quiet_hours(db, family_user):
    """Quiet hours govern what leaves the building, never what the family can see."""
    _quiet(db, family_user)
    result = notification_service.dispatch(
        db,
        Recipient(label=family_user.name, user=family_user),
        title="Reading recorded",
        message="A routine check was recorded this morning.",
        at=datetime(2026, 8, 23, 23, 0),
    )
    assert result["notification_id"] is not None
    assert result["channels"] == []


# --- delivery records -----------------------------------------------------


def test_a_suppressed_message_is_a_row_not_a_gap(client, db, family_headers, family_user):
    _quiet(db, family_user)
    notification_service.dispatch(
        db,
        Recipient(label=family_user.name, user=family_user),
        title="Weekly report ready",
        message="Your report for last week is ready to read.",
        type_=NotificationType.SYSTEM,
        at=datetime(2026, 8, 23, 23, 0),
    )
    db.commit()

    rows = client.get(f"{API}/notifications/delivery-log", headers=family_headers).json()
    suppressed = [row for row in rows if row["status"] == "suppressed"]
    assert suppressed
    assert "quiet hours" in suppressed[0]["detail"]


def test_a_suppressed_record_does_not_store_the_message_body(db, family_user):
    _quiet(db, family_user)
    notification_service.dispatch(
        db,
        Recipient(label=family_user.name, user=family_user),
        title="Reading recorded",
        message="Blood pressure 128 over 80.",
        at=datetime(2026, 8, 23, 23, 0),
    )
    db.commit()
    row = db.scalar(
        select(DeliveryLog).where(DeliveryLog.status == DeliveryStatus.SUPPRESSED)
    )
    assert row is not None
    assert row.body == ""  # nothing was sent; storing the reading would be gratuitous


# --- the care circle ------------------------------------------------------


def test_a_circle_member_with_no_login_is_contacted(client, db, family_headers, nurse_headers, started_visit_id):
    """The neighbour with the spare key is the point of the whole feature."""
    from tests.conftest import ABNORMAL_VITALS

    client.post(
        f"{API}/patients/1/care-circle",
        json={
            "name": "Vasanthi Rao",
            "relationship_label": "Neighbour",
            "phone": "+91 90000 20001",
            "role": "emergency_contact",
            "receives_alerts": True,
        },
        headers=family_headers,
    )
    client.post(f"{API}/visits/{started_visit_id}/vitals", json=ABNORMAL_VITALS, headers=nurse_headers)

    row = db.scalar(select(DeliveryLog).where(DeliveryLog.recipient == "+91 90000 20001"))
    assert row is not None, "a reachable circle member who asked for alerts must be contacted"


def test_a_circle_member_is_reached_without_an_in_app_record(db, family_headers, client):
    member = client.post(
        f"{API}/patients/1/care-circle",
        json={
            "name": "Vasanthi Rao",
            "relationship_label": "Neighbour",
            "phone": "+91 90000 20002",
            "receives_alerts": True,
        },
        headers=family_headers,
    ).json()

    from app.models import CareCircleMember

    row = db.get(CareCircleMember, member["id"])
    result = notification_service.dispatch(
        db,
        Recipient(label=row.name, member=row),
        title="Alert",
        message="Something needs attention.",
        severity=AlertSeverity.CRITICAL,
    )
    assert result["notification_id"] is None  # she has no account to show it in
    assert result["channels"], "but she is still contacted"
