"""Visit scheduling and lifecycle transitions."""

from .conftest import NORMAL_VITALS


def test_coordinator_can_schedule_a_visit(client, coordinator_headers):
    response = client.post(
        "/api/v1/visits",
        json={"patient_id": 1, "caregiver_id": 1, "scheduled_at": "2026-09-01T09:00:00"},
        headers=coordinator_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "scheduled"
    assert body["caregiver_id"] == 1


def test_scheduled_visit_appears_on_the_caregiver_worklist(client, caregiver_headers, scheduled_visit_id):
    response = client.get("/api/v1/visits/today", headers=caregiver_headers)
    assert response.status_code == 200
    assert scheduled_visit_id in [visit["id"] for visit in response.json()]


def test_caregiver_only_sees_their_own_visits(client, caregiver_headers):
    response = client.get("/api/v1/visits", headers=caregiver_headers)
    assert response.status_code == 200
    assert all(visit["caregiver_id"] == 1 for visit in response.json())


def test_checkin_moves_the_visit_to_in_progress(client, caregiver_headers, scheduled_visit_id):
    response = client.post(f"/api/v1/visits/{scheduled_visit_id}/checkin", headers=caregiver_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["checkin_at"] is not None
    assert body["location_source"] == "demo/unverified"


def test_checkin_records_browser_location_when_provided(client, caregiver_headers, scheduled_visit_id):
    response = client.post(
        f"/api/v1/visits/{scheduled_visit_id}/checkin",
        json={"lat": 12.9352, "lng": 77.6245},
        headers=caregiver_headers,
    )
    assert response.status_code == 200
    assert response.json()["location_source"] == "browser"


def test_a_visit_cannot_be_started_twice(client, caregiver_headers, started_visit_id):
    response = client.post(f"/api/v1/visits/{started_visit_id}/checkin", headers=caregiver_headers)
    assert response.status_code == 400
    assert "already been started" in response.json()["detail"]


def test_checkout_is_rejected_before_checkin(client, caregiver_headers, scheduled_visit_id):
    response = client.post(f"/api/v1/visits/{scheduled_visit_id}/checkout", headers=caregiver_headers)
    assert response.status_code == 400
    assert "checked in" in response.json()["detail"]


def test_vitals_are_rejected_before_checkin(client, caregiver_headers, scheduled_visit_id):
    response = client.post(
        f"/api/v1/visits/{scheduled_visit_id}/vitals", json=NORMAL_VITALS, headers=caregiver_headers
    )
    assert response.status_code == 400
    assert "checked in" in response.json()["detail"]


def test_a_visit_cannot_be_completed_without_vitals(client, caregiver_headers, started_visit_id):
    response = client.post(f"/api/v1/visits/{started_visit_id}/complete", headers=caregiver_headers)
    assert response.status_code == 400
    assert "Vitals must be recorded" in response.json()["detail"]


def test_a_visit_completes_after_vitals_are_recorded(client, caregiver_headers, started_visit_id):
    client.post(f"/api/v1/visits/{started_visit_id}/vitals", json=NORMAL_VITALS, headers=caregiver_headers)
    response = client.post(f"/api/v1/visits/{started_visit_id}/complete", headers=caregiver_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["checkout_at"] is not None


def test_a_completed_visit_is_immutable(client, caregiver_headers, started_visit_id):
    client.post(f"/api/v1/visits/{started_visit_id}/vitals", json=NORMAL_VITALS, headers=caregiver_headers)
    client.post(f"/api/v1/visits/{started_visit_id}/complete", headers=caregiver_headers)

    again = client.post(f"/api/v1/visits/{started_visit_id}/complete", headers=caregiver_headers)
    assert again.status_code == 400

    more_vitals = client.post(
        f"/api/v1/visits/{started_visit_id}/vitals", json=NORMAL_VITALS, headers=caregiver_headers
    )
    assert more_vitals.status_code == 400
    assert "no longer be edited" in more_vitals.json()["detail"]

    notes = client.post(
        f"/api/v1/visits/{started_visit_id}/notes",
        json={"notes": "late edit"},
        headers=caregiver_headers,
    )
    assert notes.status_code == 400


def test_caregiver_can_save_observations_during_a_visit(client, caregiver_headers, started_visit_id):
    response = client.post(
        f"/api/v1/visits/{started_visit_id}/notes",
        json={"notes": "Patient alert and comfortable."},
        headers=caregiver_headers,
    )
    assert response.status_code == 200
    assert response.json()["notes"] == "Patient alert and comfortable."


def test_coordinator_can_assign_a_caregiver(client, coordinator_headers):
    created = client.post(
        "/api/v1/visits",
        json={"patient_id": 1, "scheduled_at": "2026-09-02T09:00:00"},
        headers=coordinator_headers,
    ).json()
    assert created["caregiver_id"] is None

    response = client.post(
        f"/api/v1/visits/{created['id']}/assign", json={"caregiver_id": 1}, headers=coordinator_headers
    )
    assert response.status_code == 200
    assert response.json()["caregiver_id"] == 1


def test_scheduling_an_unknown_patient_returns_404(client, coordinator_headers):
    response = client.post(
        "/api/v1/visits",
        json={"patient_id": 999, "caregiver_id": 1, "scheduled_at": "2026-09-01T09:00:00"},
        headers=coordinator_headers,
    )
    assert response.status_code == 404


def test_family_can_read_visit_history(client, family_headers):
    response = client.get("/api/v1/visits", headers=family_headers)
    assert response.status_code == 200
    assert any(visit["status"] == "completed" for visit in response.json())
