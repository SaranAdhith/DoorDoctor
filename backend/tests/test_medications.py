"""Medication scheduling, dose logging and adherence."""

from .conftest import NORMAL_VITALS


def test_seeded_adherence_is_calculated_from_logged_doses(client, family_headers):
    response = client.get("/api/v1/patients/1/medication-adherence", headers=family_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 15
    assert body["administered"] == 13
    assert body["percentage"] == 87


def test_family_can_add_a_medication(client, family_headers):
    response = client.post(
        "/api/v1/patients/1/medications",
        json={"name": "Vitamin D3", "dosage": "60000 IU", "frequency": "Weekly", "scheduled_time": "09:00"},
        headers=family_headers,
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Vitamin D3"

    listed = client.get("/api/v1/patients/1/medications", headers=family_headers).json()
    assert "Vitamin D3" in [m["name"] for m in listed]


def test_nurse_cannot_change_the_medication_schedule(client, nurse_headers):
    response = client.post(
        "/api/v1/patients/1/medications",
        json={"name": "Aspirin", "dosage": "75 mg", "frequency": "Daily", "scheduled_time": "09:00"},
        headers=nurse_headers,
    )
    assert response.status_code == 403


def test_administered_dose_is_logged(client, nurse_headers, started_visit_id):
    response = client.post(
        f"/api/v1/visits/{started_visit_id}/medication-logs",
        json={"medication_id": 1, "status": "administered", "reason": None},
        headers=nurse_headers,
    )
    assert response.status_code == 201
    assert response.json()["status"] == "administered"


def test_skipped_dose_requires_a_reason(client, nurse_headers, started_visit_id):
    response = client.post(
        f"/api/v1/visits/{started_visit_id}/medication-logs",
        json={"medication_id": 1, "status": "skipped"},
        headers=nurse_headers,
    )
    assert response.status_code == 422
    assert "reason is required" in response.json()["detail"].lower()


def test_refused_dose_requires_a_reason(client, nurse_headers, started_visit_id):
    response = client.post(
        f"/api/v1/visits/{started_visit_id}/medication-logs",
        json={"medication_id": 2, "status": "refused", "reason": "   "},
        headers=nurse_headers,
    )
    assert response.status_code == 422


def test_skipped_dose_with_a_reason_is_accepted(client, nurse_headers, started_visit_id):
    response = client.post(
        f"/api/v1/visits/{started_visit_id}/medication-logs",
        json={"medication_id": 1, "status": "skipped", "reason": "Patient had not eaten"},
        headers=nurse_headers,
    )
    assert response.status_code == 201
    assert response.json()["reason"] == "Patient had not eaten"


def test_logging_updates_adherence(client, nurse_headers, family_headers, started_visit_id):
    before = client.get("/api/v1/patients/1/medication-adherence", headers=family_headers).json()

    for medication_id in (1, 2, 3):
        client.post(
            f"/api/v1/visits/{started_visit_id}/medication-logs",
            json={"medication_id": medication_id, "status": "administered"},
            headers=nurse_headers,
        )

    after = client.get("/api/v1/patients/1/medication-adherence", headers=family_headers).json()
    assert after["total"] == before["total"] + 3
    assert after["administered"] == before["administered"] + 3
    assert after["percentage"] == round(after["administered"] / after["total"] * 100)


def test_relogging_the_same_medication_corrects_the_entry(client, nurse_headers, family_headers, started_visit_id):
    client.post(
        f"/api/v1/visits/{started_visit_id}/medication-logs",
        json={"medication_id": 1, "status": "administered"},
        headers=nurse_headers,
    )
    before = client.get("/api/v1/patients/1/medication-adherence", headers=family_headers).json()

    client.post(
        f"/api/v1/visits/{started_visit_id}/medication-logs",
        json={"medication_id": 1, "status": "refused", "reason": "Patient declined"},
        headers=nurse_headers,
    )
    after = client.get("/api/v1/patients/1/medication-adherence", headers=family_headers).json()

    assert after["total"] == before["total"]  # corrected, not duplicated
    assert after["refused"] == before["refused"] + 1


def test_medication_cannot_be_logged_before_checkin(client, nurse_headers, scheduled_visit_id):
    response = client.post(
        f"/api/v1/visits/{scheduled_visit_id}/medication-logs",
        json={"medication_id": 1, "status": "administered"},
        headers=nurse_headers,
    )
    assert response.status_code == 400


def test_medication_cannot_be_logged_after_completion(client, nurse_headers, started_visit_id):
    client.post(f"/api/v1/visits/{started_visit_id}/vitals", json=NORMAL_VITALS, headers=nurse_headers)
    client.post(f"/api/v1/visits/{started_visit_id}/complete", headers=nurse_headers)

    response = client.post(
        f"/api/v1/visits/{started_visit_id}/medication-logs",
        json={"medication_id": 1, "status": "administered"},
        headers=nurse_headers,
    )
    assert response.status_code == 400


def test_adherence_reports_no_data_when_nothing_is_logged(client, db, admin_headers):
    from app.models import Patient

    patient = Patient(
        name="Fresh Patient", age=70, gender="Male", address="Jayanagar, Bengaluru", family_user_id=1
    )
    db.add(patient)
    db.commit()

    response = client.get(
        f"/api/v1/patients/{patient.id}/medication-adherence", headers=admin_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["percentage"] is None  # rendered as "No data", never 0%
    assert body["total"] == 0
