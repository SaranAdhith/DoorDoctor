"""Phase 10 — nurse credential transparency and the family-facing profile (§4.10).

The point of the feature is that the family can check the person at the door.
The point of these tests is that checking them does not hand the family the
nurse's private details, or the other households the nurse covers.
"""

from sqlalchemy import select

from app.models import CredentialKind, Nurse, NurseCredential, VerificationStatus
from app.services import nurse_service

API = "/api/v1"


def _credential_id(db, nurse_id: int = 1, kind=CredentialKind.NURSING_REGISTRATION) -> int:
    credential = db.scalar(
        select(NurseCredential).where(
            NurseCredential.nurse_id == nurse_id, NurseCredential.kind == kind
        )
    )
    assert credential is not None
    return credential.id


# --- what a family sees ---------------------------------------------------


def test_a_family_sees_their_nurses_verified_credentials(client, family_headers):
    response = client.get(f"{API}/patients/1/nurses/1", headers=family_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Anitha Kumar"
    assert body["credentials"], "the demo nurse must have a verified credential on file"
    first = body["credentials"][0]
    assert first["issuing_body"]
    assert first["verified_at"] is not None
    assert first["verified_by_name"], "a verified credential names who verified it"


def test_a_family_never_sees_a_registration_number(client, family_headers):
    body = client.get(f"{API}/patients/1/nurses/1", headers=family_headers).json()
    assert "registration_number" not in body["credentials"][0]
    assert "email" not in body
    assert "phone" not in body


def test_a_family_sees_visit_counts_for_their_patient_only(client, family_headers, db):
    """240 visits this quarter is a fact about twenty other households."""
    body = client.get(f"{API}/patients/1/nurses/1", headers=family_headers).json()
    from app.models import Visit, VisitStatus

    for_this_patient = db.scalar(
        select(Visit)
        .where(Visit.nurse_id == 1, Visit.patient_id == 1, Visit.status == VisitStatus.COMPLETED)
        .limit(1)
    )
    assert for_this_patient is not None
    assert body["visits_to_this_patient"] > 0
    assert "patients_covered" not in body
    assert "completed_visits" not in body


def test_a_family_cannot_read_a_nurse_who_has_never_visited_their_patient(
    client, family_headers, db
):
    other = db.scalar(select(Nurse).where(Nurse.id != 1))
    if other is None:  # SMALL seeds one nurse
        return
    assert client.get(f"{API}/patients/1/nurses/{other.id}", headers=family_headers).status_code == 404


def test_a_family_cannot_read_another_familys_nurses(client, other_family, db):
    from tests.conftest import DEMO_PASSWORD, auth, login

    headers = auth(login(client, other_family["email"], DEMO_PASSWORD))
    assert client.get(f"{API}/patients/1/nurses", headers=headers).status_code == 404


def test_there_is_no_nurse_endpoint_a_family_can_browse(client, family_headers):
    """The directory is admin-only. A family knows their own nurses, not the roster."""
    assert client.get(f"{API}/nurses", headers=family_headers).status_code == 403
    assert client.get(f"{API}/nurses/1", headers=family_headers).status_code == 403


def test_the_patient_nurse_list_is_the_people_who_came_to_this_house(client, family_headers):
    body = client.get(f"{API}/patients/1/nurses", headers=family_headers).json()
    assert [nurse["id"] for nurse in body] == [1]


# --- what an admin sees ---------------------------------------------------


def test_an_admin_sees_the_registration_number_and_the_workload(client, admin_headers):
    body = client.get(f"{API}/nurses/1", headers=admin_headers).json()
    registration = next(
        c for c in body["credentials"] if c["kind"] == "nursing_registration"
    )
    assert registration["registration_number"]
    assert registration["verification_status"] == "verified"
    assert body["patients_covered"] >= 1
    assert body["email"].endswith("@doordoctor.in")


def test_the_directory_still_answers_on_its_old_path(client, admin_headers):
    """`GET /nurses` moved routers this phase. The path and its keys did not."""
    response = client.get(f"{API}/nurses", headers=admin_headers)
    assert response.status_code == 200
    first = response.json()[0]
    for key in ("id", "user_id", "name", "email", "phone", "credential", "status", "open_visits"):
        assert key in first


# --- verification ---------------------------------------------------------


def test_recording_a_credential_does_not_verify_it(client, admin_headers, db):
    response = client.post(
        f"{API}/nurses/1/credentials",
        json={
            "kind": "training",
            "title": "Dementia care refresher",
            "issuing_body": "DoorDoctor training",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    assert response.json()["verification_status"] == "pending"
    assert response.json()["verified_by_name"] is None


def test_verifying_a_credential_leaves_the_verifiers_name_on_it(client, admin_headers, db):
    created = client.post(
        f"{API}/nurses/1/credentials",
        json={"kind": "training", "title": "Wound care", "issuing_body": "DoorDoctor training"},
        headers=admin_headers,
    ).json()

    response = client.post(
        f"{API}/nurse-credentials/{created['id']}/verify",
        json={"note": "Certificate seen."},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["verification_status"] == "verified"
    assert body["verified_by_name"] == "Ravi Menon"
    assert body["verified_at"] is not None


def test_a_verified_status_without_a_verifier_is_not_treated_as_verified(db):
    """The model's own definition of verified, not the column's.

    Somebody hand-editing the enum to `verified` must not produce a badge the
    family reads as checked.
    """
    credential = db.get(NurseCredential, _credential_id(db))
    credential.verified_at = None
    credential.verified_by_name = None
    assert credential.verification_status == VerificationStatus.VERIFIED
    assert credential.is_verified is False

    profile = nurse_service.family_profile(db, db.get(Nurse, 1), patient_id=1)
    assert all(c["id"] != credential.id for c in profile["credentials"])


def test_a_pending_credential_never_reaches_the_family(client, admin_headers, family_headers):
    client.post(
        f"{API}/nurses/1/credentials",
        json={"kind": "training", "title": "Unchecked course", "issuing_body": "Somewhere"},
        headers=admin_headers,
    )
    body = client.get(f"{API}/patients/1/nurses/1", headers=family_headers).json()
    assert all(c["title"] != "Unchecked course" for c in body["credentials"])


def test_rejecting_a_registration_marks_the_nurse_unverified(client, admin_headers, db):
    credential_id = _credential_id(db)
    client.post(
        f"{API}/nurse-credentials/{credential_id}/reject",
        json={"note": "Number did not match the council register."},
        headers=admin_headers,
    )
    assert db.get(Nurse, 1).verification_status == VerificationStatus.REJECTED


def test_verification_is_audited(client, admin_headers, db):
    from app.models import AuditAction, AuditEvent

    created = client.post(
        f"{API}/nurses/1/credentials",
        json={"kind": "training", "title": "Falls prevention", "issuing_body": "DoorDoctor"},
        headers=admin_headers,
    ).json()
    client.post(
        f"{API}/nurse-credentials/{created['id']}/verify", json={}, headers=admin_headers
    )
    entry = db.scalar(
        select(AuditEvent).where(AuditEvent.action == AuditAction.CREDENTIAL_VERIFIED)
    )
    assert entry is not None
    assert entry.actor_label == "Ravi Menon"


def test_an_expired_credential_cannot_be_verified(client, admin_headers):
    created = client.post(
        f"{API}/nurses/1/credentials",
        json={
            "kind": "training",
            "title": "Lapsed certificate",
            "issuing_body": "Somewhere",
            "expires_on": "2020-01-01",
        },
        headers=admin_headers,
    ).json()
    response = client.post(
        f"{API}/nurse-credentials/{created['id']}/verify", json={}, headers=admin_headers
    )
    assert response.status_code == 400
    assert "expired" in response.json()["detail"]


def test_a_nurse_cannot_verify_their_own_credentials(client, nurse_headers, db):
    credential_id = _credential_id(db)
    assert (
        client.post(
            f"{API}/nurse-credentials/{credential_id}/verify", json={}, headers=nurse_headers
        ).status_code
        == 403
    )
