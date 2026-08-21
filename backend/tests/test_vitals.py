"""Vitals validation and the threshold engine."""

import pytest

from .conftest import ABNORMAL_VITALS, NORMAL_VITALS, SINGLE_BREACH_VITALS


def test_normal_vitals_are_saved_without_an_alert(client, caregiver_headers, started_visit_id):
    response = client.post(
        f"/api/v1/visits/{started_visit_id}/vitals", json=NORMAL_VITALS, headers=caregiver_headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["threshold_breached"] is False
    assert body["alerts_created"] == []
    assert body["vitals"]["systolic_bp"] == 130


def test_abnormal_vitals_create_one_alert_with_every_breach(client, caregiver_headers, started_visit_id):
    response = client.post(
        f"/api/v1/visits/{started_visit_id}/vitals", json=ABNORMAL_VITALS, headers=caregiver_headers
    )
    assert response.status_code == 201
    body = response.json()

    assert body["threshold_breached"] is True
    assert len(body["alerts_created"]) == 1

    alert = body["alerts_created"][0]
    breached = {item["metric"] for item in alert["breached_parameters"]}
    assert breached == {"systolic_bp", "diastolic_bp"}
    assert alert["severity"] == "critical"  # two or more breaches
    assert alert["status"] == "active"
    assert alert["vitals_id"] == body["vitals"]["id"]


def test_a_single_breach_is_a_warning(client, caregiver_headers, started_visit_id):
    response = client.post(
        f"/api/v1/visits/{started_visit_id}/vitals",
        json=SINGLE_BREACH_VITALS,
        headers=caregiver_headers,
    )
    assert response.status_code == 201
    alert = response.json()["alerts_created"][0]
    assert alert["severity"] == "warning"
    assert len(alert["breached_parameters"]) == 1


def test_low_readings_breach_the_low_threshold(client, caregiver_headers, started_visit_id):
    payload = {**NORMAL_VITALS, "spo2": 91}
    response = client.post(
        f"/api/v1/visits/{started_visit_id}/vitals", json=payload, headers=caregiver_headers
    )
    assert response.status_code == 201
    breach = response.json()["alerts_created"][0]["breached_parameters"][0]
    assert breach["metric"] == "spo2"
    assert breach["direction"] == "below"
    assert breach["threshold"] == 94


def test_alert_message_stays_non_diagnostic(client, caregiver_headers, started_visit_id):
    response = client.post(
        f"/api/v1/visits/{started_visit_id}/vitals", json=ABNORMAL_VITALS, headers=caregiver_headers
    )
    message = response.json()["alerts_created"][0]["message"].lower()
    assert "not a medical diagnosis" in message
    for diagnosis_word in ("hypertension", "hypertensive", "stroke", "diagnos" + "is of"):
        assert diagnosis_word not in message


@pytest.mark.parametrize(
    "field,value",
    [
        ("systolic_bp", -10),
        ("systolic_bp", 400),
        ("diastolic_bp", 0),
        ("heart_rate", 900),
        ("spo2", 140),
        ("temperature", 60),
        ("weight", -5),
        ("blood_glucose", 5000),
    ],
)
def test_impossible_values_are_rejected(client, caregiver_headers, started_visit_id, field, value):
    payload = {**NORMAL_VITALS, field: value}
    response = client.post(
        f"/api/v1/visits/{started_visit_id}/vitals", json=payload, headers=caregiver_headers
    )
    assert response.status_code == 422
    assert field in response.json()["detail"]


def test_missing_values_are_rejected(client, caregiver_headers, started_visit_id):
    payload = {k: v for k, v in NORMAL_VITALS.items() if k != "spo2"}
    response = client.post(
        f"/api/v1/visits/{started_visit_id}/vitals", json=payload, headers=caregiver_headers
    )
    assert response.status_code == 422
    assert "spo2" in response.json()["detail"]


def test_non_numeric_values_are_rejected(client, caregiver_headers, started_visit_id):
    payload = {**NORMAL_VITALS, "heart_rate": "fast"}
    response = client.post(
        f"/api/v1/visits/{started_visit_id}/vitals", json=payload, headers=caregiver_headers
    )
    assert response.status_code == 422


def test_recorded_vitals_reach_the_family_dashboard(client, caregiver_headers, family_headers, started_visit_id):
    client.post(
        f"/api/v1/visits/{started_visit_id}/vitals", json=ABNORMAL_VITALS, headers=caregiver_headers
    )
    dashboard = client.get("/api/v1/patients/1/dashboard", headers=family_headers).json()

    assert dashboard["current_vitals"]["systolic_bp"] == 148
    assert dashboard["current_vitals"]["threshold_breached"] is True
    assert dashboard["overall_status"] == "Critical Alert"
    assert len(dashboard["active_alerts"]) == 1
    assert dashboard["vitals_history"][-1]["systolic_bp"] == 148


def test_thresholds_are_patient_specific(client, family_headers, caregiver_headers, started_visit_id):
    """Raising the configured range removes the breach for the same reading."""
    thresholds = client.get("/api/v1/patients/1/thresholds", headers=family_headers).json()
    payload = [
        {
            "metric": t["metric"],
            "low_threshold": t["low_threshold"],
            "high_threshold": 160 if t["metric"] == "systolic_bp" else t["high_threshold"],
            "enabled": t["enabled"],
        }
        for t in thresholds
    ]
    assert client.put("/api/v1/patients/1/thresholds", json=payload, headers=family_headers).status_code == 200

    response = client.post(
        f"/api/v1/visits/{started_visit_id}/vitals",
        json=SINGLE_BREACH_VITALS,
        headers=caregiver_headers,
    )
    assert response.json()["threshold_breached"] is False
