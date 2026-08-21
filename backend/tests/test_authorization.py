"""Role and ownership enforcement (never delegated to the frontend)."""

from .conftest import ABNORMAL_VITALS, DEMO_PASSWORD, auth, login


def test_family_cannot_read_another_familys_patient(client, family_headers, other_family):
    response = client.get(f"/api/v1/patients/{other_family['patient_id']}", headers=family_headers)
    # 404, not 403: the API never confirms that another family's record exists.
    assert response.status_code == 404


def test_family_cannot_read_another_familys_dashboard(client, family_headers, other_family):
    response = client.get(
        f"/api/v1/patients/{other_family['patient_id']}/dashboard", headers=family_headers
    )
    assert response.status_code == 404


def test_family_only_lists_its_own_patients(client, family_headers, other_family):
    response = client.get("/api/v1/patients", headers=family_headers)
    assert response.status_code == 200
    names = [patient["name"] for patient in response.json()]
    assert names == ["Lakshmi D'Souza"]


def test_other_family_cannot_reach_the_demo_patient(client, other_family):
    headers = auth(login(client, other_family["email"], DEMO_PASSWORD))
    assert client.get("/api/v1/patients/1", headers=headers).status_code == 404


def test_caregiver_cannot_record_vitals_on_an_unassigned_visit(client, db, caregiver_headers):
    from app.models import Caregiver, CaregiverStatus, User, UserRole, VerificationStatus, Visit
    from app.core.security import hash_password
    from app.database import now

    other_user = User(
        name="Other Caregiver",
        email="other-caregiver@doordoc.demo",
        password_hash=hash_password(DEMO_PASSWORD),
        role=UserRole.CAREGIVER,
    )
    db.add(other_user)
    db.flush()
    other_caregiver = Caregiver(
        user_id=other_user.id,
        credential="RN",
        verification_status=VerificationStatus.VERIFIED,
        status=CaregiverStatus.ACTIVE,
    )
    db.add(other_caregiver)
    db.flush()
    visit = Visit(patient_id=1, caregiver_id=other_caregiver.id, scheduled_at=now())
    db.add(visit)
    db.commit()

    assert client.get(f"/api/v1/visits/{visit.id}", headers=caregiver_headers).status_code == 404
    response = client.post(
        f"/api/v1/visits/{visit.id}/vitals", json=ABNORMAL_VITALS, headers=caregiver_headers
    )
    assert response.status_code == 404


def test_caregiver_cannot_schedule_a_visit(client, caregiver_headers):
    response = client.post(
        "/api/v1/visits",
        json={"patient_id": 1, "caregiver_id": 1, "scheduled_at": "2026-08-20T10:30:00"},
        headers=caregiver_headers,
    )
    assert response.status_code == 403


def test_family_cannot_schedule_a_visit(client, family_headers):
    response = client.post(
        "/api/v1/visits",
        json={"patient_id": 1, "caregiver_id": 1, "scheduled_at": "2026-08-20T10:30:00"},
        headers=family_headers,
    )
    assert response.status_code == 403


def test_family_cannot_list_caregivers(client, family_headers):
    assert client.get("/api/v1/caregivers", headers=family_headers).status_code == 403


def test_coordinator_can_read_operational_data(client, coordinator_headers):
    summary = client.get("/api/v1/coordinator/summary", headers=coordinator_headers)
    assert summary.status_code == 200
    assert summary.json()["patients"] >= 1

    caregivers = client.get("/api/v1/caregivers", headers=coordinator_headers)
    assert caregivers.status_code == 200
    assert caregivers.json()[0]["name"] == "Anitha Kumar"

    patients = client.get("/api/v1/patients", headers=coordinator_headers)
    assert patients.status_code == 200
    assert len(patients.json()) >= 1


def test_unauthenticated_requests_are_rejected(client):
    assert client.get("/api/v1/patients").status_code == 401
    assert client.get("/api/v1/visits/today").status_code == 401
    assert client.get("/api/v1/alerts").status_code == 401
