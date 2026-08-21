"""Alert visibility, notifications and admin resolution."""

from .conftest import ABNORMAL_VITALS


def _raise_alert(client, nurse_headers, visit_id) -> dict:
    response = client.post(
        f"/api/v1/visits/{visit_id}/vitals", json=ABNORMAL_VITALS, headers=nurse_headers
    )
    assert response.status_code == 201
    return response.json()["alerts_created"][0]


def test_new_alert_is_visible_to_the_family(client, nurse_headers, family_headers, started_visit_id):
    alert = _raise_alert(client, nurse_headers, started_visit_id)

    response = client.get("/api/v1/alerts", headers=family_headers)
    assert response.status_code == 200
    assert alert["id"] in [item["id"] for item in response.json()]


def test_new_alert_is_visible_to_the_admin(client, nurse_headers, admin_headers, started_visit_id):
    alert = _raise_alert(client, nurse_headers, started_visit_id)

    response = client.get("/api/v1/alerts?status=active", headers=admin_headers)
    assert response.status_code == 200
    assert alert["id"] in [item["id"] for item in response.json()]


def test_alert_detail_carries_the_reading_and_configured_threshold(
    client, nurse_headers, family_headers, started_visit_id
):
    alert = _raise_alert(client, nurse_headers, started_visit_id)

    response = client.get(f"/api/v1/alerts/{alert['id']}", headers=family_headers)
    assert response.status_code == 200
    body = response.json()

    assert body["patient_name"] == "Lakshmi D'Souza"
    assert body["nurse_name"] == "Anitha Kumar"
    assert body["vitals"]["systolic_bp"] == 148
    systolic = next(t for t in body["thresholds"] if t["metric"] == "systolic_bp")
    assert systolic["high_threshold"] == 140


def test_alert_creates_notifications_for_family_and_admin(
    client, nurse_headers, family_headers, admin_headers, started_visit_id
):
    _raise_alert(client, nurse_headers, started_visit_id)

    family_notifications = client.get("/api/v1/notifications", headers=family_headers).json()
    admin_notifications = client.get("/api/v1/notifications", headers=admin_headers).json()

    assert len(family_notifications) == 1
    assert len(admin_notifications) == 1
    assert family_notifications[0]["read"] is False

    read = client.post(
        f"/api/v1/notifications/{family_notifications[0]['id']}/read", headers=family_headers
    )
    assert read.status_code == 200
    assert read.json()["read"] is True


def test_nurse_does_not_receive_alert_notifications(client, nurse_headers, started_visit_id, family_headers):
    _raise_alert(client, nurse_headers, started_visit_id)
    nurse_notifications = client.get("/api/v1/notifications", headers=nurse_headers).json()
    assert nurse_notifications == []


def test_admin_can_acknowledge_then_resolve(client, nurse_headers, admin_headers, started_visit_id):
    alert = _raise_alert(client, nurse_headers, started_visit_id)

    acknowledged = client.post(f"/api/v1/alerts/{alert['id']}/acknowledge", headers=admin_headers)
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"
    assert acknowledged.json()["acknowledged_at"] is not None

    resolved = client.post(f"/api/v1/alerts/{alert['id']}/resolve", headers=admin_headers)
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolved_at"] is not None


def test_an_alert_cannot_be_resolved_twice(client, nurse_headers, admin_headers, started_visit_id):
    alert = _raise_alert(client, nurse_headers, started_visit_id)
    client.post(f"/api/v1/alerts/{alert['id']}/resolve", headers=admin_headers)

    again = client.post(f"/api/v1/alerts/{alert['id']}/resolve", headers=admin_headers)
    assert again.status_code == 400


def test_family_cannot_resolve_or_acknowledge(client, nurse_headers, family_headers, started_visit_id):
    alert = _raise_alert(client, nurse_headers, started_visit_id)

    assert client.post(f"/api/v1/alerts/{alert['id']}/acknowledge", headers=family_headers).status_code == 403
    assert client.post(f"/api/v1/alerts/{alert['id']}/resolve", headers=family_headers).status_code == 403


def test_resolved_alert_leaves_the_dashboard_but_stays_in_history(
    client, nurse_headers, admin_headers, family_headers, started_visit_id
):
    alert = _raise_alert(client, nurse_headers, started_visit_id)
    client.post(f"/api/v1/alerts/{alert['id']}/resolve", headers=admin_headers)

    dashboard = client.get("/api/v1/patients/1/dashboard", headers=family_headers).json()
    assert dashboard["active_alerts"] == []
    assert dashboard["overall_status"] == "Stable"

    history = client.get("/api/v1/alerts", headers=family_headers).json()
    assert alert["id"] in [item["id"] for item in history]  # history preserved


def test_admin_summary_counts_active_alerts(client, nurse_headers, admin_headers, started_visit_id):
    before = client.get("/api/v1/admin/summary", headers=admin_headers).json()
    alert = _raise_alert(client, nurse_headers, started_visit_id)
    after = client.get("/api/v1/admin/summary", headers=admin_headers).json()

    assert after["active_alerts"] == before["active_alerts"] + 1

    client.post(f"/api/v1/alerts/{alert['id']}/resolve", headers=admin_headers)
    resolved = client.get("/api/v1/admin/summary", headers=admin_headers).json()
    assert resolved["active_alerts"] == before["active_alerts"]
