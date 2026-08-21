"""Visit scheduling and lifecycle transitions."""

from .conftest import NORMAL_VITALS


def test_admin_can_schedule_a_visit(client, admin_headers):
    response = client.post(
        "/api/v1/visits",
        json={"patient_id": 1, "nurse_id": 1, "scheduled_at": "2026-09-01T09:00:00"},
        headers=admin_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "scheduled"
    assert body["nurse_id"] == 1


def test_scheduled_visit_appears_on_the_nurse_worklist(client, nurse_headers, scheduled_visit_id):
    response = client.get("/api/v1/visits/today", headers=nurse_headers)
    assert response.status_code == 200
    assert scheduled_visit_id in [visit["id"] for visit in response.json()]


def test_nurse_only_sees_their_own_visits(client, nurse_headers):
    response = client.get("/api/v1/visits", headers=nurse_headers)
    assert response.status_code == 200
    assert all(visit["nurse_id"] == 1 for visit in response.json())


def test_checkin_moves_the_visit_to_in_progress(client, nurse_headers, scheduled_visit_id):
    response = client.post(f"/api/v1/visits/{scheduled_visit_id}/checkin", headers=nurse_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["checkin_at"] is not None
    assert body["location_source"] == "demo/unverified"


def test_checkin_records_browser_location_when_provided(client, nurse_headers, scheduled_visit_id):
    response = client.post(
        f"/api/v1/visits/{scheduled_visit_id}/checkin",
        json={"lat": 12.9352, "lng": 77.6245},
        headers=nurse_headers,
    )
    assert response.status_code == 200
    assert response.json()["location_source"] == "browser"


def test_a_visit_cannot_be_started_twice(client, nurse_headers, started_visit_id):
    response = client.post(f"/api/v1/visits/{started_visit_id}/checkin", headers=nurse_headers)
    assert response.status_code == 400
    assert "already been started" in response.json()["detail"]


def test_checkout_is_rejected_before_checkin(client, nurse_headers, scheduled_visit_id):
    response = client.post(f"/api/v1/visits/{scheduled_visit_id}/checkout", headers=nurse_headers)
    assert response.status_code == 400
    assert "checked in" in response.json()["detail"]


def test_vitals_are_rejected_before_checkin(client, nurse_headers, scheduled_visit_id):
    response = client.post(
        f"/api/v1/visits/{scheduled_visit_id}/vitals", json=NORMAL_VITALS, headers=nurse_headers
    )
    assert response.status_code == 400
    assert "checked in" in response.json()["detail"]


def test_a_visit_cannot_be_completed_without_vitals(client, nurse_headers, started_visit_id):
    response = client.post(f"/api/v1/visits/{started_visit_id}/complete", headers=nurse_headers)
    assert response.status_code == 400
    assert "Vitals must be recorded" in response.json()["detail"]


def test_a_visit_completes_after_vitals_are_recorded(client, nurse_headers, started_visit_id):
    client.post(f"/api/v1/visits/{started_visit_id}/vitals", json=NORMAL_VITALS, headers=nurse_headers)
    response = client.post(f"/api/v1/visits/{started_visit_id}/complete", headers=nurse_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["checkout_at"] is not None


def test_a_completed_visit_is_immutable(client, nurse_headers, started_visit_id):
    client.post(f"/api/v1/visits/{started_visit_id}/vitals", json=NORMAL_VITALS, headers=nurse_headers)
    client.post(f"/api/v1/visits/{started_visit_id}/complete", headers=nurse_headers)

    again = client.post(f"/api/v1/visits/{started_visit_id}/complete", headers=nurse_headers)
    assert again.status_code == 400

    more_vitals = client.post(
        f"/api/v1/visits/{started_visit_id}/vitals", json=NORMAL_VITALS, headers=nurse_headers
    )
    assert more_vitals.status_code == 400
    assert "no longer be edited" in more_vitals.json()["detail"]

    notes = client.post(
        f"/api/v1/visits/{started_visit_id}/notes",
        json={"notes": "late edit"},
        headers=nurse_headers,
    )
    assert notes.status_code == 400


def test_nurse_can_save_observations_during_a_visit(client, nurse_headers, started_visit_id):
    response = client.post(
        f"/api/v1/visits/{started_visit_id}/notes",
        json={"notes": "Patient alert and comfortable."},
        headers=nurse_headers,
    )
    assert response.status_code == 200
    assert response.json()["notes"] == "Patient alert and comfortable."


def test_admin_can_assign_a_nurse(client, admin_headers):
    created = client.post(
        "/api/v1/visits",
        json={"patient_id": 1, "scheduled_at": "2026-09-02T09:00:00"},
        headers=admin_headers,
    ).json()
    assert created["nurse_id"] is None

    response = client.post(
        f"/api/v1/visits/{created['id']}/assign", json={"nurse_id": 1}, headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["nurse_id"] == 1


def test_scheduling_an_unknown_patient_returns_404(client, admin_headers):
    response = client.post(
        "/api/v1/visits",
        json={"patient_id": 999, "nurse_id": 1, "scheduled_at": "2026-09-01T09:00:00"},
        headers=admin_headers,
    )
    assert response.status_code == 404


def test_family_can_read_visit_history(client, family_headers):
    response = client.get("/api/v1/visits", headers=family_headers)
    assert response.status_code == 200
    assert any(visit["status"] == "completed" for visit in response.json())
