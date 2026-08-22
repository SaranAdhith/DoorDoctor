"""Escalations, the parallel-notification timeline and hospital coordination
(§4.3, §4.9).

RECORDED and pinned as literals: the ladder is **108 → nurse → admin**. Every
SLA duration is `ASSUMED` and is asserted against `core/clinical.py`.
"""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core import clinical
from app.database import now
from app.models import (
    AlertSeverity,
    DeliveryLog,
    EscalationEvent,
    EscalationStatus,
    EscalationStepStatus,
    EscalationTrigger,
    HospitalBookingStatus,
    Patient,
)
from app.services import escalation_service

from .conftest import auth, login


@pytest.fixture
def event(db):
    patient = db.get(Patient, 1)
    e = escalation_service.open_event(
        db,
        patient=patient,
        trigger=EscalationTrigger.MANUAL,
        severity=AlertSeverity.CRITICAL,
        summary="Manual escalation",
        detail="Family called the team.",
    )
    db.commit()
    return e


# --------------------------------------------------------------------------
# The recorded ladder
# --------------------------------------------------------------------------


def test_the_ladder_is_one_zero_eight_then_nurse_then_admin():
    """RECORDED. Phase 7 pinned this order in the assistant; one source means
    the assistant, the emergency block and the timeline cannot drift apart."""
    assert clinical.EMERGENCY_NUMBER == "108"
    ladder = [rung.lower() for rung in clinical.ESCALATION_LADDER]
    assert "108" in ladder[0]
    assert "nurse" in ladder[1]
    assert "admin" in ladder[2]


def test_the_emergency_block_is_served_rather_than_restated(client, family_headers):
    response = client.get("/api/v1/emergency", headers=family_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["number"] == "108"
    assert body["ladder"] == list(clinical.ESCALATION_LADDER)
    assert "108" in body["title"]


def test_the_emergency_block_says_doordoctor_is_not_an_emergency_service(client, family_headers):
    body = client.get("/api/v1/emergency", headers=family_headers).json()
    assert "not an emergency service" in body["body"].lower()


def test_the_ladder_travels_with_every_escalation(client, admin_headers, event):
    body = client.get(f"/api/v1/escalations/{event.id}", headers=admin_headers).json()
    assert body["ladder"] == list(clinical.ESCALATION_LADDER)


# --------------------------------------------------------------------------
# The timeline is data, and it is parallel
# --------------------------------------------------------------------------


def test_the_first_step_is_advisory_and_says_doordoctor_does_not_dial(db, event):
    """DoorDoctor does not call 108 on anyone's behalf. A timeline that implied
    it had would be the most consequential lie this product could tell."""
    first = event.steps[0]
    assert first.sequence == 0
    assert first.target == clinical.EMERGENCY_NUMBER
    assert first.status == EscalationStepStatus.SKIPPED
    assert "does not place this call" in first.detail


def test_the_family_and_the_admin_are_contacted_at_the_same_sequence(db, event):
    """One fan-out, not a queue worked one at a time."""
    contacted = [s for s in event.steps if s.sequence == 1]
    actors = {s.actor for s in contacted}
    assert "Family" in actors
    assert "Admin" in actors
    assert len({s.sequence for s in contacted}) == 1


def test_a_critical_escalation_goes_out_on_two_channels(db, event):
    """A single channel means one silent phone is the whole strategy."""
    channels = {s.channel for s in event.steps if s.sequence == 1}
    assert channels == {c.value for c in escalation_service.CRITICAL_CHANNELS}
    assert len(channels) == 2


def test_each_step_records_who_was_contacted_and_how(db, event):
    for step in event.steps:
        assert step.actor
        assert step.channel
        assert step.target
        assert step.occurred_at is not None


def test_contact_goes_through_the_phase_3_delivery_seam(db, event):
    """One seam, not two. `notification_delivery` is where a real provider
    eventually plugs in, and a second path here would bypass it silently."""
    logs = db.scalars(select(DeliveryLog)).all()
    assert logs
    linked = [s for s in event.steps if s.delivery_log_id is not None]
    assert linked
    assert {s.delivery_log_id for s in linked} <= {log.id for log in logs}


def test_an_admin_can_append_a_call_they_made_by_hand(client, admin_headers, event):
    """A record that only holds what the software did is not a record of what
    happened."""
    response = client.post(
        f"/api/v1/escalations/{event.id}/steps",
        json={"channel": "phone", "target": "Daughter, +91 90000 00001", "detail": "Spoke, on the way."},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    steps = response.json()["steps"]
    assert steps[-1]["detail"] == "Spoke, on the way."
    assert steps[-1]["sequence"] > 1  # after the automated fan-out


# --------------------------------------------------------------------------
# The SLA clock
# --------------------------------------------------------------------------


def test_the_sla_budget_comes_from_the_severity(db):
    patient = db.get(Patient, 1)
    critical = escalation_service.open_event(
        db,
        patient=patient,
        trigger=EscalationTrigger.MANUAL,
        severity=AlertSeverity.CRITICAL,
        summary="Critical",
    )
    warning = escalation_service.open_event(
        db,
        patient=patient,
        trigger=EscalationTrigger.MANUAL,
        severity=AlertSeverity.WARNING,
        summary="Warning",
    )
    assert critical.sla_minutes == clinical.SLA_DURATIONS_MINUTES["critical"]
    assert warning.sla_minutes == clinical.SLA_DURATIONS_MINUTES["warning"]
    assert critical.sla_minutes < warning.sla_minutes


def test_both_the_budget_and_the_deadline_are_stored(db, event):
    """The deadline is what the queue sorts on; the budget is what lets a screen
    say "15 minutes" months later without re-deriving it from constants that may
    since have changed."""
    assert event.sla_minutes > 0
    expected = event.opened_at + timedelta(minutes=event.sla_minutes)
    assert abs((event.sla_due_at - expected).total_seconds()) < 1


def test_a_breach_is_stamped_and_survives_the_constants_changing(db, client, admin_headers):
    patient = db.get(Patient, 1)
    stale = escalation_service.open_event(
        db,
        patient=patient,
        trigger=EscalationTrigger.MANUAL,
        severity=AlertSeverity.CRITICAL,
        summary="Old",
        as_of=now() - timedelta(days=2),
    )
    db.commit()
    assert stale.breached_sla is False  # not yet observed

    listed = client.get("/api/v1/escalations", headers=admin_headers).json()
    breached = next(e for e in listed if e["id"] == stale.id)
    assert breached["breached_sla"] is True

    db.expire_all()
    assert db.get(EscalationEvent, stale.id).breached_sla is True


def test_the_queue_is_ordered_by_deadline_with_open_first(db, client, admin_headers):
    patient = db.get(Patient, 1)
    escalation_service.open_event(
        db, patient=patient, trigger=EscalationTrigger.MANUAL,
        severity=AlertSeverity.WARNING, summary="Later",
    )
    urgent = escalation_service.open_event(
        db, patient=patient, trigger=EscalationTrigger.MANUAL,
        severity=AlertSeverity.CRITICAL, summary="Sooner",
    )
    db.commit()

    listed = client.get("/api/v1/escalations", headers=admin_headers).json()
    assert listed[0]["id"] == urgent.id


# --------------------------------------------------------------------------
# Working an escalation
# --------------------------------------------------------------------------


def test_an_admin_acknowledges_then_resolves_with_a_note(client, admin_headers, event):
    picked = client.post(f"/api/v1/escalations/{event.id}/acknowledge", headers=admin_headers)
    assert picked.status_code == 200, picked.text
    assert picked.json()["status"] == EscalationStatus.ACKNOWLEDGED.value

    closed = client.post(
        f"/api/v1/escalations/{event.id}/resolve",
        json={"note": "Family reached, no ambulance needed."},
        headers=admin_headers,
    )
    assert closed.status_code == 200, closed.text
    body = closed.json()
    assert body["status"] == EscalationStatus.RESOLVED.value
    assert body["resolution_note"] == "Family reached, no ambulance needed."


def test_acknowledging_and_resolving_both_land_on_the_timeline(client, admin_headers, event):
    client.post(f"/api/v1/escalations/{event.id}/acknowledge", headers=admin_headers)
    body = client.post(
        f"/api/v1/escalations/{event.id}/resolve", json={"note": "Closed."}, headers=admin_headers
    ).json()
    details = [s["detail"] for s in body["steps"]]
    assert any("picked this up" in d for d in details)
    assert "Closed." in details


def test_an_escalation_cannot_be_resolved_twice(client, admin_headers, event):
    client.post(f"/api/v1/escalations/{event.id}/resolve", headers=admin_headers)
    assert (
        client.post(f"/api/v1/escalations/{event.id}/resolve", headers=admin_headers).status_code
        == 400
    )


def test_the_queue_is_admin_only(client, family_headers, nurse_headers, admin_headers):
    assert client.get("/api/v1/escalations", headers=family_headers).status_code == 403
    assert client.get("/api/v1/escalations", headers=nurse_headers).status_code == 403
    assert client.get("/api/v1/escalations", headers=admin_headers).status_code == 200


def test_a_family_reads_their_own_patients_escalations(client, family_headers, event):
    response = client.get("/api/v1/patients/1/escalations", headers=family_headers)
    assert response.status_code == 200
    assert [e["id"] for e in response.json()] == [event.id]


def test_another_familys_escalation_is_a_404(client, other_family, event):
    headers = auth(login(client, other_family["email"]))
    assert client.get(f"/api/v1/escalations/{event.id}", headers=headers).status_code == 404


# --------------------------------------------------------------------------
# Hospital coordination
# --------------------------------------------------------------------------


def _request(client, headers, ambulance=False):
    return client.post(
        "/api/v1/patients/1/hospital-bookings",
        json={
            "hospital_name": "Manipal Hospital, Old Airport Road",
            "reason": "Persistent chest discomfort",
            "department": "Cardiology",
            "ambulance_required": ambulance,
        },
        headers=headers,
    )


def test_a_family_requests_hospital_coordination(client, family_headers):
    response = _request(client, family_headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == HospitalBookingStatus.REQUESTED.value
    assert body["sla_minutes"] == clinical.HOSPITAL_BOOKING_SLA_MINUTES
    assert body["escalation_event_id"] is None


def test_an_ambulance_request_runs_on_the_critical_clock_and_opens_an_escalation(
    client, family_headers, db
):
    body = _request(client, family_headers, ambulance=True).json()
    assert body["sla_minutes"] == clinical.AMBULANCE_SLA_MINUTES
    assert body["sla_minutes"] < clinical.HOSPITAL_BOOKING_SLA_MINUTES
    assert body["escalation_event_id"] is not None

    event = db.get(EscalationEvent, body["escalation_event_id"])
    assert event.trigger == EscalationTrigger.HOSPITAL_BOOKING
    assert event.severity == AlertSeverity.CRITICAL
    assert event.trigger_id == body["id"]


def test_the_queue_shows_the_soonest_deadline_first(client, family_headers, admin_headers):
    _request(client, family_headers)
    _request(client, family_headers, ambulance=True)
    queue = client.get("/api/v1/hospital-bookings", headers=admin_headers).json()
    assert queue[0]["ambulance_required"] is True


def test_an_admin_confirms_a_booking(client, family_headers, admin_headers):
    booking_id = _request(client, family_headers).json()["id"]
    response = client.patch(
        f"/api/v1/hospital-bookings/{booking_id}",
        json={"status": "confirmed", "confirmation_detail": "Bed held, 4pm, Dr Rao."},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == HospitalBookingStatus.CONFIRMED.value
    assert body["confirmed_at"] is not None
    assert body["handled_by"] is not None


def test_no_hospital_partner_list_is_invented(client, family_headers):
    """DoorDoctor is pre-launch. The row records the hospital the family named;
    a partner list would be invented traction."""
    body = _request(client, family_headers).json()
    assert body["hospital_name"] == "Manipal Hospital, Old Airport Road"


def test_the_hospital_queue_is_admin_only(client, family_headers, admin_headers):
    assert client.get("/api/v1/hospital-bookings", headers=family_headers).status_code == 403
    assert client.get("/api/v1/hospital-bookings", headers=admin_headers).status_code == 200


def test_a_nurse_cannot_request_a_hospital_booking(client, nurse_headers):
    assert _request(client, nurse_headers).status_code == 403


def test_another_family_sees_none_of_these_bookings(client, family_headers, other_family):
    """Reached through the route the other family *can* call. The admin PATCH is
    a 403 for them before authorization is ever consulted, which proves the role
    guard rather than the disclosure rule."""
    _request(client, family_headers)
    headers = auth(login(client, other_family["email"]))
    assert client.get("/api/v1/patients/1/hospital-bookings", headers=headers).status_code == 404
    own = client.get(
        f"/api/v1/patients/{other_family['patient_id']}/hospital-bookings", headers=headers
    )
    assert own.status_code == 200
    assert own.json() == []
