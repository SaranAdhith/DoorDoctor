"""Connected devices and wearable ingest (§4.8).

RECORDED and pinned as literals: **SpO2 below 90%** triggers, and a breach runs
**three** actions. The heart-rate range and the three actions themselves are
`ASSUMED` and are asserted against `core/clinical.py`.
"""

import logging

import pytest
from sqlalchemy import select

from app.core import clinical
from app.core.exceptions import UnauthorizedError
from app.database import now
from app.models import (
    Alert,
    Device,
    DeviceReading,
    EscalationEvent,
    EscalationTrigger,
    FollowUpTask,
    TaskKind,
    VitalMetric,
)
from app.services import device_service

from .conftest import auth, login

from datetime import timedelta


def _register(client, headers, serial="OX-TEST-1"):
    response = client.post(
        "/api/v1/patients/1/devices",
        json={"kind": "pulse_oximeter", "label": "Bedside oximeter", "serial": serial},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _push(client, key, readings):
    return client.post(
        "/api/v1/ingest/device-readings",
        json={"readings": readings},
        headers={"X-Device-Key": key},
    )


# --------------------------------------------------------------------------
# The recorded triggers — pure arithmetic, re-run rather than round-tripped
# --------------------------------------------------------------------------


def test_spo2_below_ninety_triggers():
    """RECORDED, so a literal."""
    assert clinical.WEARABLE_SPO2_FLOOR == 90.0
    assert device_service.breaches_trigger(VitalMetric.SPO2, 89.9) is not None
    assert device_service.breaches_trigger(VitalMetric.SPO2, 90) is None


@pytest.mark.parametrize("value,triggers", [(30, True), (44, True), (72, False), (200, True)])
def test_heart_rate_outside_the_range_triggers(value, triggers):
    result = device_service.breaches_trigger(VitalMetric.HEART_RATE, value)
    assert (result is not None) is triggers


def test_the_heart_rate_range_is_the_right_way_round():
    assert clinical.WEARABLE_HR_LOW < clinical.WEARABLE_HR_HIGH


def test_a_metric_with_no_recorded_trigger_does_not_fire():
    assert device_service.breaches_trigger(VitalMetric.WEIGHT, 500) is None


def test_the_trigger_reason_is_said_in_the_familys_words():
    """A family reads the alert this reason ends up inside."""
    reason = device_service.breaches_trigger(VitalMetric.SPO2, 85)
    assert "oxygen level" in reason
    assert "spo2" not in reason.lower()


# --------------------------------------------------------------------------
# Keys are stored hashed, never in the clear
# --------------------------------------------------------------------------


def test_the_key_is_returned_once_and_stored_only_as_a_hash(client, family_headers, db):
    body = _register(client, family_headers)
    raw_key = body["api_key"]
    assert raw_key.startswith("dd_dev_")

    device = db.get(Device, body["id"])
    assert device.api_key_hash != raw_key
    assert device.api_key_hash == device_service.hash_key(raw_key)
    assert len(device.api_key_hash) == 64


def test_the_key_never_appears_in_any_later_response(client, family_headers):
    _register(client, family_headers)
    listed = client.get("/api/v1/patients/1/devices", headers=family_headers).json()
    assert "api_key" not in listed[0]


def test_no_device_row_holds_a_usable_credential(client, family_headers, db):
    """A leaked `devices` table must not be a list of working keys."""
    key = _register(client, family_headers)["api_key"]
    for device in db.scalars(select(Device)).all():
        with pytest.raises(UnauthorizedError):
            device_service.authenticate(db, device.api_key_hash)
    # The plaintext, however, still works.
    assert device_service.authenticate(db, key) is not None


def test_rotating_a_key_invalidates_the_old_one(client, family_headers, db):
    body = _register(client, family_headers)
    old_key = body["api_key"]
    new_key = client.post(
        f"/api/v1/devices/{body['id']}/rotate-key", headers=family_headers
    ).json()["api_key"]

    assert new_key != old_key
    assert _push(client, old_key, [{"metric": "spo2", "value": 97}]).status_code == 401
    assert _push(client, new_key, [{"metric": "spo2", "value": 97}]).status_code == 202


def test_an_unknown_key_is_401(client):
    assert _push(client, "dd_dev_nope", [{"metric": "spo2", "value": 97}]).status_code == 401


def test_a_missing_key_is_401(client):
    response = client.post(
        "/api/v1/ingest/device-readings", json={"readings": [{"metric": "spo2", "value": 97}]}
    )
    assert response.status_code == 401


def test_a_deactivated_device_stops_being_accepted(client, family_headers):
    body = _register(client, family_headers)
    key = body["api_key"]
    assert _push(client, key, [{"metric": "spo2", "value": 97}]).status_code == 202
    client.post(f"/api/v1/devices/{body['id']}/deactivate", headers=family_headers)
    assert _push(client, key, [{"metric": "spo2", "value": 96}]).status_code == 401


# --------------------------------------------------------------------------
# Ingest hygiene
# --------------------------------------------------------------------------


def test_normal_readings_are_stored_and_trigger_nothing(client, family_headers, db):
    key = _register(client, family_headers)["api_key"]
    response = _push(
        client,
        key,
        [{"metric": "spo2", "value": 97}, {"metric": "heart_rate", "value": 72}],
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body == {"accepted": 2, "skipped": 0, "triggered": 0, "actions": []}
    assert len(db.scalars(select(DeviceReading)).all()) == 2


def test_the_response_says_nothing_about_the_patient(client, family_headers):
    """A stolen device key must not become a health-record reader."""
    key = _register(client, family_headers)["api_key"]
    body = _push(client, key, [{"metric": "spo2", "value": 97}]).json()
    assert set(body) == {"accepted", "skipped", "triggered", "actions"}
    assert "Lakshmi" not in str(body)


def test_a_replayed_batch_does_not_double_record(client, family_headers, db):
    key = _register(client, family_headers)["api_key"]
    stamp = now().isoformat()
    reading = [{"metric": "spo2", "value": 97, "recorded_at": stamp}]

    assert _push(client, key, reading).json()["accepted"] == 1
    second = _push(client, key, reading).json()
    assert second["accepted"] == 0
    assert second["skipped"] == 1
    assert len(db.scalars(select(DeviceReading)).all()) == 1


def test_a_reading_backdated_beyond_the_cap_is_skipped(client, family_headers):
    key = _register(client, family_headers)["api_key"]
    stale = (now() - timedelta(hours=clinical.WEARABLE_MAX_BACKDATE_HOURS + 2)).isoformat()
    body = _push(client, key, [{"metric": "spo2", "value": 97, "recorded_at": stale}]).json()
    assert body == {"accepted": 0, "skipped": 1, "triggered": 0, "actions": []}


def test_a_reading_from_the_future_is_skipped(client, family_headers):
    key = _register(client, family_headers)["api_key"]
    ahead = (now() + timedelta(days=3)).isoformat()
    assert _push(client, key, [{"metric": "spo2", "value": 97, "recorded_at": ahead}]).json()[
        "skipped"
    ] == 1


def test_a_batch_over_the_cap_is_refused_by_the_schema(client, family_headers):
    key = _register(client, family_headers)["api_key"]
    oversized = [{"metric": "spo2", "value": 97}] * (clinical.WEARABLE_MAX_BATCH + 1)
    assert _push(client, key, oversized).status_code == 422


def test_an_absurd_value_is_refused_by_the_schema(client, family_headers):
    key = _register(client, family_headers)["api_key"]
    assert _push(client, key, [{"metric": "spo2", "value": 99999}]).status_code == 422


def test_a_duplicate_serial_says_nothing_about_who_owns_it(client, family_headers, admin_headers):
    """A serial is guessable. "Already registered to another patient" would be
    a lookup oracle for whether a stranger is a DoorDoctor customer."""
    _register(client, family_headers, serial="OX-DUP")
    response = client.post(
        "/api/v1/patients/1/devices",
        json={"kind": "smartwatch", "label": "Watch", "serial": "OX-DUP"},
        headers=family_headers,
    )
    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "already registered" in detail
    assert "patient" not in detail


def test_no_device_supplied_string_reaches_the_log(client, family_headers, caplog):
    """A device's serial, label and payload are all attacker-controlled text."""
    marker = "ZZ-INJECTED-MARKER"
    body = _register(client, family_headers, serial=marker)
    with caplog.at_level(logging.INFO, logger="doordoctor.devices"):
        _push(client, body["api_key"], [{"metric": "spo2", "value": 97}])
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert marker not in logged
    assert "Bedside oximeter" not in logged
    assert str(body["id"]) in logged


# --------------------------------------------------------------------------
# The three recorded actions
# --------------------------------------------------------------------------


def test_there_are_exactly_three_documented_actions():
    """RECORDED that there are three; §4.8 never lists them, so all three are
    ASSUMED and all three live in one place."""
    assert len(clinical.WEARABLE_ACTIONS) == 3
    assert [a.key for a in clinical.WEARABLE_ACTIONS] == ["alert", "escalate", "task"]


def test_a_low_oxygen_reading_fires_all_three(client, family_headers, db):
    key = _register(client, family_headers)["api_key"]
    response = _push(client, key, [{"metric": "spo2", "value": 88}])
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["triggered"] == 1
    assert body["actions"] == [a.key for a in clinical.WEARABLE_ACTIONS]

    # 1 — a critical alert
    alert = db.scalar(select(Alert).where(Alert.alert_type == "wearable_breach"))
    assert alert is not None
    assert alert.severity.value == "critical"

    # 2 — an escalation, with the family and the admin contacted in parallel
    event = db.scalar(
        select(EscalationEvent).where(EscalationEvent.trigger == EscalationTrigger.WEARABLE_BREACH)
    )
    assert event is not None
    assert event.alert_id == alert.id
    contacted = [s for s in event.steps if s.sequence == 1]
    assert len(contacted) >= 2
    assert len({s.sequence for s in contacted}) == 1  # one fan-out, not a queue

    # 3 — a task for the covering nurse
    task = db.scalar(select(FollowUpTask).where(FollowUpTask.kind == TaskKind.WEARABLE_CHECK))
    assert task is not None
    assert task.assigned_user_id is not None


def test_a_high_heart_rate_fires_the_same_three(client, family_headers, db):
    key = _register(client, family_headers)["api_key"]
    body = _push(client, key, [{"metric": "heart_rate", "value": 165}]).json()
    assert body["triggered"] == 1
    assert db.scalar(select(Alert).where(Alert.alert_type == "wearable_breach")) is not None


def test_a_burst_of_breaches_is_one_clinical_event_not_eight(client, family_headers, db):
    """A wearable reporting eight low values in a minute is one event. Eight
    escalations would bury it — the same rule as one alert per lab order."""
    key = _register(client, family_headers)["api_key"]
    base = now()
    readings = [
        {"metric": "spo2", "value": 86, "recorded_at": (base - timedelta(minutes=i)).isoformat()}
        for i in range(8)
    ]
    body = _push(client, key, readings).json()

    assert body["triggered"] == 8
    assert len(db.scalars(select(Alert).where(Alert.alert_type == "wearable_breach")).all()) == 1
    assert len(db.scalars(select(EscalationEvent)).all()) == 1
    assert len(db.scalars(select(FollowUpTask).where(FollowUpTask.kind == TaskKind.WEARABLE_CHECK)).all()) == 1


def test_the_breaching_reading_is_marked_so_the_timeline_can_point_at_it(
    client, family_headers, db
):
    key = _register(client, family_headers)["api_key"]
    base = now()
    _push(
        client,
        key,
        [
            {"metric": "spo2", "value": 97, "recorded_at": (base - timedelta(minutes=2)).isoformat()},
            {"metric": "spo2", "value": 85, "recorded_at": (base - timedelta(minutes=1)).isoformat()},
        ],
    )
    rows = db.scalars(select(DeviceReading).order_by(DeviceReading.id)).all()
    assert [r.triggered for r in rows] == [False, True]


def test_two_untimestamped_readings_of_one_metric_are_one_reading(
    client, family_headers, db
):
    """Both land on the same instant, and the same device, metric and instant is
    by definition the same reading — `uq_device_reading` says so.

    De-duplication therefore has to cover the batch as well as the database:
    nothing is flushed until the loop ends, so without an in-batch check the
    second row passed the database lookup and then violated the constraint,
    turning a sloppy payload into a 500 for the whole batch.
    """
    key = _register(client, family_headers)["api_key"]
    response = _push(
        client, key, [{"metric": "spo2", "value": 97}, {"metric": "spo2", "value": 96}]
    )
    assert response.status_code == 202, response.text
    assert response.json() == {"accepted": 1, "skipped": 1, "triggered": 0, "actions": []}
    assert len(db.scalars(select(DeviceReading)).all()) == 1


def test_two_different_metrics_at_the_same_instant_are_both_kept(client, family_headers, db):
    """A pulse oximeter reports oxygen and pulse together. The constraint is per
    metric, and the in-batch check must not be coarser than the constraint."""
    key = _register(client, family_headers)["api_key"]
    body = _push(
        client, key, [{"metric": "spo2", "value": 97}, {"metric": "heart_rate", "value": 70}]
    ).json()
    assert body["accepted"] == 2
    assert len(db.scalars(select(DeviceReading)).all()) == 2


def test_the_alert_carries_the_emergency_number(client, family_headers, db):
    key = _register(client, family_headers)["api_key"]
    _push(client, key, [{"metric": "spo2", "value": 85}])
    alert = db.scalar(select(Alert).where(Alert.alert_type == "wearable_breach"))
    assert clinical.EMERGENCY_NUMBER in alert.message


# --------------------------------------------------------------------------
# Access
# --------------------------------------------------------------------------


def test_a_nurse_cannot_register_a_device(client, nurse_headers):
    response = client.post(
        "/api/v1/patients/1/devices",
        json={"kind": "smartwatch", "label": "Watch", "serial": "NURSE-1"},
        headers=nurse_headers,
    )
    assert response.status_code == 403


def test_another_familys_device_is_a_404(client, family_headers, other_family):
    body = _register(client, family_headers)
    headers = auth(login(client, other_family["email"]))
    assert client.post(f"/api/v1/devices/{body['id']}/rotate-key", headers=headers).status_code == 404


def test_a_family_reads_their_own_device_readings(client, family_headers):
    key = _register(client, family_headers)["api_key"]
    _push(client, key, [{"metric": "spo2", "value": 96}])
    response = client.get("/api/v1/patients/1/device-readings", headers=family_headers)
    assert response.status_code == 200
    assert response.json()[0]["label"] == "oxygen level"


def test_readings_feed_the_safety_score_monitoring_component(client, family_headers):
    before = client.get("/api/v1/patients/1/safety-score", headers=family_headers).json()
    assert next(c for c in before["components"] if c["key"] == "connected_monitoring")["has_data"] is False

    key = _register(client, family_headers)["api_key"]
    _push(client, key, [{"metric": "spo2", "value": 97}])

    after = client.get("/api/v1/patients/1/safety-score", headers=family_headers).json()
    monitoring = next(c for c in after["components"] if c["key"] == "connected_monitoring")
    assert monitoring["has_data"] is True
    assert monitoring["value"] == 1.0
