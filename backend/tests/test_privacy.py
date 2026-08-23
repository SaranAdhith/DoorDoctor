"""Phase 10 — consent, the audit log, export and erasure (§4.14).

The load-bearing test in this file is `test_every_patient_scoped_model_is_accounted_for`.
Export and erasure are only as good as their coverage, and coverage is exactly
the thing that rots silently as a codebase grows — so it is asserted against the
mapper registry rather than against a list somebody remembers to update.
"""

import pytest
from sqlalchemy import select

from app.core.ops import CONSENT_KINDS, CONSENT_POLICY_VERSION, ERASURE_RETAINS
from app.database import Base
from app.models import (
    Alert,
    AuditAction,
    AuditEvent,
    Consent,
    ErasureRequest,
    ErasureStatus,
    Patient,
    Vital,
)
from app.services import privacy_service

API = "/api/v1"


# --- registry coverage ----------------------------------------------------


def test_every_patient_scoped_model_is_accounted_for():
    """A table added in a later phase cannot silently escape export and erasure.

    Walks every mapped class carrying a `patient_id` column and asserts it is
    either covered by a registered dataset or listed as deliberately retained.
    Adding a table is then a registration, not a rewrite — and forgetting is a
    failing test rather than a family's record quietly surviving its erasure.
    """
    import app.models  # noqa: F401  (registers every mapper)

    patient_scoped = {
        mapper.class_.__name__
        for mapper in Base.registry.mappers
        if "patient_id" in {column.name for column in mapper.columns}
    }
    covered = {name for dataset in privacy_service.REGISTRY for name in dataset.covers}
    accounted = covered | set(privacy_service.RETAINED_MODELS)

    missing = patient_scoped - accounted
    assert not missing, (
        f"{sorted(missing)} carry a patient_id but are neither exported nor "
        "listed in privacy_service.RETAINED_MODELS"
    )


def test_every_retained_model_carries_a_reason():
    for name, reason in privacy_service.RETAINED_MODELS.items():
        assert reason and len(reason) > 20, f"{name} is retained without saying why"


def test_the_registry_has_no_duplicate_keys():
    keys = [dataset.key for dataset in privacy_service.REGISTRY]
    assert len(keys) == len(set(keys))


# --- consent --------------------------------------------------------------


def test_the_privacy_page_lists_every_consent_including_undecided_ones(client, family_headers):
    body = client.get(f"{API}/privacy/patients/1", headers=family_headers).json()
    assert {row["kind"] for row in body["consents"]} == {spec.key for spec in CONSENT_KINDS}
    assert body["policy_version"] == CONSENT_POLICY_VERSION


def test_granting_and_withdrawing_are_both_rows(client, family_headers, db):
    client.post(
        f"{API}/privacy/consents",
        json={"kind": "assistant", "granted": True, "patient_id": 1},
        headers=family_headers,
    )
    client.post(
        f"{API}/privacy/consents",
        json={"kind": "assistant", "granted": False, "patient_id": 1},
        headers=family_headers,
    )
    rows = db.scalars(select(Consent).where(Consent.kind == "assistant")).all()
    assert len(rows) == 2
    assert {row.status.value for row in rows} == {"granted", "withdrawn"}


def test_the_current_position_is_the_newest_row(client, family_headers):
    for granted in (True, False, True):
        client.post(
            f"{API}/privacy/consents",
            json={"kind": "notifications", "granted": granted, "patient_id": 1},
            headers=family_headers,
        )
    body = client.get(f"{API}/privacy/patients/1", headers=family_headers).json()
    notifications = next(row for row in body["consents"] if row["kind"] == "notifications")
    assert notifications["granted"] is True
    assert len(body["consent_history"]) >= 3


def test_a_required_consent_cannot_be_withdrawn_by_a_checkbox(client, family_headers):
    """Withdrawing it is leaving the service, and saying so is more honest."""
    response = client.post(
        f"{API}/privacy/consents",
        json={"kind": "care_delivery", "granted": False, "patient_id": 1},
        headers=family_headers,
    )
    assert response.status_code == 400
    assert "close the account" in response.json()["detail"]


def test_an_unknown_consent_is_refused(client, family_headers):
    response = client.post(
        f"{API}/privacy/consents",
        json={"kind": "sell_my_data", "granted": True, "patient_id": 1},
        headers=family_headers,
    )
    assert response.status_code == 400


def test_a_nurse_cannot_give_consent_on_a_familys_behalf(client, nurse_headers):
    response = client.post(
        f"{API}/privacy/consents",
        json={"kind": "assistant", "granted": True, "patient_id": 1},
        headers=nurse_headers,
    )
    assert response.status_code == 403


def test_a_consent_against_an_older_policy_is_flagged_for_review(client, family_headers, db):
    client.post(
        f"{API}/privacy/consents",
        json={"kind": "assistant", "granted": True, "patient_id": 1},
        headers=family_headers,
    )
    record = db.scalar(select(Consent).where(Consent.kind == "assistant"))
    record.version = "2020-01-1"
    db.commit()

    body = client.get(f"{API}/privacy/patients/1", headers=family_headers).json()
    assistant = next(row for row in body["consents"] if row["kind"] == "assistant")
    assert assistant["needs_review"] is True
    assert assistant["granted"] is True  # still a consent, just to an older document


# --- the privacy page and export -----------------------------------------


def test_the_page_says_what_is_kept_and_why(client, family_headers):
    body = client.get(f"{API}/privacy/patients/1", headers=family_headers).json()
    assert len(body["erasure_retains"]) == len(ERASURE_RETAINS)
    for entry in body["erasure_retains"]:
        assert entry["reason"]
    assert any("invoice" in entry["label"].lower() for entry in body["erasure_retains"])


def test_holdings_count_what_is_actually_stored(client, family_headers, db):
    body = client.get(f"{API}/privacy/patients/1", headers=family_headers).json()
    holdings = {row["key"]: row["count"] for row in body["holdings"]}
    assert holdings["readings"] == len(db.scalars(select(Vital).where(Vital.patient_id == 1)).all())
    assert holdings["visits"] > 0


def test_the_export_contains_this_familys_data_and_nobody_elses(
    client, family_headers, other_family
):
    body = client.get(f"{API}/privacy/patients/1/export", headers=family_headers).json()
    assert body["patient"]["name"] == "Lakshmi D'Souza"
    serialized = str(body)
    assert "Other Patient" not in serialized
    assert "other-family@doordoctor.in" not in serialized


def test_an_export_is_audited(client, family_headers, db):
    client.get(f"{API}/privacy/patients/1/export", headers=family_headers)
    entry = db.scalar(select(AuditEvent).where(AuditEvent.action == AuditAction.RECORD_EXPORTED))
    assert entry is not None
    assert entry.patient_id == 1


def test_another_family_cannot_read_or_export_this_record(client, other_family):
    from tests.conftest import DEMO_PASSWORD, auth, login

    headers = auth(login(client, other_family["email"], DEMO_PASSWORD))
    assert client.get(f"{API}/privacy/patients/1", headers=headers).status_code == 404
    assert client.get(f"{API}/privacy/patients/1/export", headers=headers).status_code == 404


def test_a_nurses_read_of_a_record_appears_in_the_audit_trail(client, nurse_headers, family_headers, db):
    from app.services import audit_service
    from app.models import User

    nurse = db.query(User).filter(User.email == "nurse@doordoctor.in").one()
    audit_service.record_view(db, actor=nurse, patient_id=1, what="the visit detail")
    db.commit()

    body = client.get(f"{API}/privacy/patients/1", headers=family_headers).json()
    assert any(entry["action"] == "record_viewed" for entry in body["audit_trail"])


# --- erasure --------------------------------------------------------------


def test_a_family_requests_and_an_admin_executes(client, family_headers, admin_headers, db):
    """Two steps on purpose: it is irreversible and it destroys a health record."""
    request = client.post(
        f"{API}/privacy/erasure-requests",
        json={"patient_id": 1, "reason": "Moving to another provider."},
        headers=family_headers,
    )
    assert request.status_code == 201
    assert request.json()["status"] == "requested"

    queue = client.get(f"{API}/erasure-requests", headers=admin_headers).json()
    assert queue[0]["patient_name"] == "Lakshmi D'Souza"

    executed = client.post(
        f"{API}/erasure-requests/{request.json()['id']}/execute",
        json={"note": "Confirmed with the family by phone."},
        headers=admin_headers,
    )
    assert executed.status_code == 200
    assert executed.json()["status"] == "executed"
    assert executed.json()["outcome"]


def test_erasure_destroys_the_clinical_record(client, family_headers, admin_headers, db):
    request = client.post(
        f"{API}/privacy/erasure-requests", json={"patient_id": 1}, headers=family_headers
    ).json()
    client.post(
        f"{API}/erasure-requests/{request['id']}/execute", json={}, headers=admin_headers
    )

    assert db.scalars(select(Vital).where(Vital.patient_id == 1)).all() == []
    assert db.scalars(select(Alert).where(Alert.patient_id == 1)).all() == []
    patient = db.get(Patient, 1)
    assert patient.name == privacy_service.ERASED_NAME
    assert patient.home_lat is None


def test_erasure_keeps_the_audit_log_and_records_itself(client, family_headers, admin_headers, db):
    request = client.post(
        f"{API}/privacy/erasure-requests", json={"patient_id": 1}, headers=family_headers
    ).json()
    client.post(f"{API}/erasure-requests/{request['id']}/execute", json={}, headers=admin_headers)

    entries = db.scalars(select(AuditEvent).where(AuditEvent.patient_id == 1)).all()
    assert entries, "deleting the log would remove the evidence that the erasure happened"
    assert any(entry.action == AuditAction.ERASURE_EXECUTED for entry in entries)


def test_erasure_keeps_the_invoices(client, family_headers, admin_headers, db):
    from app.models import Invoice

    before = len(db.scalars(select(Invoice)).all())
    request = client.post(
        f"{API}/privacy/erasure-requests", json={"patient_id": 1}, headers=family_headers
    ).json()
    client.post(f"{API}/erasure-requests/{request['id']}/execute", json={}, headers=admin_headers)
    assert len(db.scalars(select(Invoice)).all()) == before


def test_erasure_removes_the_stored_photographs(
    client, family_headers, admin_headers, nurse_headers, started_visit_id, db
):
    import io

    from PIL import Image

    from app.models import Attachment
    from app.services import storage

    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), "green").save(buffer, format="JPEG")
    log = client.post(
        f"{API}/visits/{started_visit_id}/medication-logs",
        json={"medication_id": 1, "status": "administered"},
        headers=nurse_headers,
    ).json()
    photo = client.post(
        f"{API}/medications/logs/{log['id']}/photo",
        files={"file": ("dose.jpg", buffer.getvalue(), "image/jpeg")},
        headers=nurse_headers,
    ).json()["photo"]
    path = db.get(Attachment, photo["id"]).path
    assert storage.exists(path)

    request = client.post(
        f"{API}/privacy/erasure-requests", json={"patient_id": 1}, headers=family_headers
    ).json()
    client.post(f"{API}/erasure-requests/{request['id']}/execute", json={}, headers=admin_headers)

    assert db.get(Attachment, photo["id"]) is None
    assert not storage.exists(path)


def test_a_second_request_is_refused_while_one_is_waiting(client, family_headers):
    client.post(f"{API}/privacy/erasure-requests", json={"patient_id": 1}, headers=family_headers)
    second = client.post(
        f"{API}/privacy/erasure-requests", json={"patient_id": 1}, headers=family_headers
    )
    assert second.status_code == 409


def test_a_family_cannot_execute_their_own_erasure(client, family_headers):
    request = client.post(
        f"{API}/privacy/erasure-requests", json={"patient_id": 1}, headers=family_headers
    ).json()
    response = client.post(
        f"{API}/erasure-requests/{request['id']}/execute", json={}, headers=family_headers
    )
    assert response.status_code == 403


def test_declining_requires_a_reason(client, family_headers, admin_headers):
    request = client.post(
        f"{API}/privacy/erasure-requests", json={"patient_id": 1}, headers=family_headers
    ).json()
    assert (
        client.post(
            f"{API}/erasure-requests/{request['id']}/decline", json={}, headers=admin_headers
        ).status_code
        == 400
    )
    declined = client.post(
        f"{API}/erasure-requests/{request['id']}/decline",
        json={"note": "The account is in dispute between two family members."},
        headers=admin_headers,
    )
    assert declined.json()["status"] == "declined"


def test_a_decided_request_cannot_be_decided_again(client, family_headers, admin_headers, db):
    request = client.post(
        f"{API}/privacy/erasure-requests", json={"patient_id": 1}, headers=family_headers
    ).json()
    client.post(f"{API}/erasure-requests/{request['id']}/execute", json={}, headers=admin_headers)
    again = client.post(
        f"{API}/erasure-requests/{request['id']}/execute", json={}, headers=admin_headers
    )
    assert again.status_code == 400


def test_the_erasure_queue_is_admin_only(client, family_headers, nurse_headers):
    assert client.get(f"{API}/erasure-requests", headers=family_headers).status_code == 403
    assert client.get(f"{API}/erasure-requests", headers=nurse_headers).status_code == 403


def test_the_audit_log_is_admin_only(client, family_headers, nurse_headers, admin_headers):
    assert client.get(f"{API}/audit", headers=family_headers).status_code == 403
    assert client.get(f"{API}/audit", headers=nurse_headers).status_code == 403
    assert client.get(f"{API}/audit", headers=admin_headers).status_code == 200
