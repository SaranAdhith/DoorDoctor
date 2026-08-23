"""Phase 10 — dose photos, pill organiser fills and the change history (§4.12).

Three features, one idea: a family should be able to see the evidence, not just
the claim. The dose has a photograph, the organiser has a fill record with a
date on it, and "why is she on half the dose now" has an answer.
"""

import io

import pytest
from PIL import Image
from sqlalchemy import select

from app.core.pricing import ADD_ONS_BY_CODE
from app.models import (
    Attachment,
    InvoiceLine,
    MedicationChange,
    MedicationChangeKind,
    PillOrganiserFill,
)
from tests.conftest import NORMAL_VITALS

API = "/api/v1"


def _jpeg(colour: str = "white", size: tuple[int, int] = (80, 60)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
def dose_log_id(client, nurse_headers, started_visit_id) -> int:
    response = client.post(
        f"{API}/visits/{started_visit_id}/medication-logs",
        json={"medication_id": 1, "status": "administered"},
        headers=nurse_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# --- dose photos ----------------------------------------------------------


def test_a_nurse_can_attach_a_dose_photo(client, nurse_headers, dose_log_id):
    response = client.post(
        f"{API}/medications/logs/{dose_log_id}/photo",
        files={"file": ("dose.jpg", _jpeg(), "image/jpeg")},
        headers=nurse_headers,
    )
    assert response.status_code == 200, response.text
    photo = response.json()["photo"]
    assert photo["content_type"] == "image/jpeg"
    assert photo["url"] == f"/attachments/{photo['id']}"


def test_the_photo_is_served_only_to_someone_who_may_see_the_patient(
    client, nurse_headers, family_headers, admin_headers, other_family, dose_log_id
):
    from tests.conftest import DEMO_PASSWORD, auth, login

    photo = client.post(
        f"{API}/medications/logs/{dose_log_id}/photo",
        files={"file": ("dose.jpg", _jpeg(), "image/jpeg")},
        headers=nurse_headers,
    ).json()["photo"]

    for headers in (family_headers, nurse_headers, admin_headers):
        assert client.get(f"{API}/attachments/{photo['id']}", headers=headers).status_code == 200

    stranger = auth(login(client, other_family["email"], DEMO_PASSWORD))
    assert client.get(f"{API}/attachments/{photo['id']}", headers=stranger).status_code == 404
    assert client.get(f"{API}/attachments/{photo['id']}").status_code == 401


def test_the_photo_route_returns_the_bytes_with_safe_headers(client, nurse_headers, dose_log_id):
    photo = client.post(
        f"{API}/medications/logs/{dose_log_id}/photo",
        files={"file": ("dose.jpg", _jpeg(colour="red"), "image/jpeg")},
        headers=nurse_headers,
    ).json()["photo"]

    response = client.get(f"{API}/attachments/{photo['id']}", headers=nurse_headers)
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in response.headers["cache-control"]
    assert Image.open(io.BytesIO(response.content)).format == "JPEG"


def test_a_file_that_is_not_an_image_is_refused(client, nurse_headers, dose_log_id):
    """Validated by decoding the bytes, not by believing the content type."""
    response = client.post(
        f"{API}/medications/logs/{dose_log_id}/photo",
        files={"file": ("payload.jpg", b"#!/bin/sh\necho hello\n", "image/jpeg")},
        headers=nurse_headers,
    )
    assert response.status_code == 400
    assert "not an image" in response.json()["detail"]


def test_replacing_a_photo_does_not_orphan_the_old_one(client, db, nurse_headers, dose_log_id):
    first = client.post(
        f"{API}/medications/logs/{dose_log_id}/photo",
        files={"file": ("a.jpg", _jpeg(colour="red"), "image/jpeg")},
        headers=nurse_headers,
    ).json()["photo"]
    second = client.post(
        f"{API}/medications/logs/{dose_log_id}/photo",
        files={"file": ("b.jpg", _jpeg(colour="blue"), "image/jpeg")},
        headers=nurse_headers,
    ).json()["photo"]

    assert first["id"] != second["id"]
    assert db.get(Attachment, first["id"]) is None
    assert db.get(Attachment, second["id"]) is not None


def test_a_family_cannot_upload_a_dose_photo(client, family_headers, dose_log_id):
    response = client.post(
        f"{API}/medications/logs/{dose_log_id}/photo",
        files={"file": ("dose.jpg", _jpeg(), "image/jpeg")},
        headers=family_headers,
    )
    assert response.status_code == 403


def test_a_photo_cannot_be_added_to_a_completed_visit(
    client, nurse_headers, started_visit_id, dose_log_id
):
    client.post(
        f"{API}/visits/{started_visit_id}/vitals", json=NORMAL_VITALS, headers=nurse_headers
    )
    client.post(f"{API}/visits/{started_visit_id}/complete", headers=nurse_headers)

    response = client.post(
        f"{API}/medications/logs/{dose_log_id}/photo",
        files={"file": ("dose.jpg", _jpeg(), "image/jpeg")},
        headers=nurse_headers,
    )
    assert response.status_code == 400


# --- the change history ---------------------------------------------------


def test_a_dose_change_writes_one_history_row(client, family_headers, db):
    response = client.patch(
        f"{API}/medications/1",
        json={"dosage": "2.5 mg", "reason": "Halved after a run of low readings."},
        headers=family_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "dosage_changed"
    assert body["previous_value"] == "5 mg"
    assert body["new_value"] == "2.5 mg"
    assert body["changed_by_name"] == "Darren D'Souza"


def test_one_edit_touching_two_things_writes_two_rows(client, family_headers, db):
    client.patch(
        f"{API}/medications/1",
        json={"dosage": "2.5 mg", "scheduled_time": "09:00"},
        headers=family_headers,
    )
    changes = db.scalars(
        select(MedicationChange).where(MedicationChange.medication_id == 1)
    ).all()
    kinds = {change.kind for change in changes}
    assert MedicationChangeKind.DOSAGE_CHANGED in kinds
    assert MedicationChangeKind.SCHEDULE_CHANGED in kinds


def test_stopping_a_medication_is_a_row_not_a_missing_row(client, family_headers, db):
    client.patch(f"{API}/medications/1", json={"active": False}, headers=family_headers)
    change = db.scalar(
        select(MedicationChange).where(MedicationChange.kind == MedicationChangeKind.STOPPED)
    )
    assert change is not None
    assert change.new_value == "Stopped"


def test_an_edit_that_changes_nothing_writes_nothing(client, family_headers, db):
    before = len(db.scalars(select(MedicationChange)).all())
    response = client.patch(f"{API}/medications/1", json={"dosage": "5 mg"}, headers=family_headers)
    assert response.status_code == 200
    assert response.json() is None
    assert len(db.scalars(select(MedicationChange)).all()) == before


def test_creating_a_medication_records_that_it_was_started(client, family_headers, db):
    created = client.post(
        f"{API}/patients/1/medications",
        json={"name": "Vitamin D", "dosage": "60000 IU", "scheduled_time": "09:00"},
        headers=family_headers,
    ).json()
    change = db.scalar(
        select(MedicationChange).where(MedicationChange.medication_id == created["id"])
    )
    assert change is not None
    assert change.kind == MedicationChangeKind.STARTED


def test_a_nurse_cannot_change_a_prescription(client, nurse_headers):
    response = client.patch(f"{API}/medications/1", json={"dosage": "10 mg"}, headers=nurse_headers)
    assert response.status_code == 403


def test_a_family_reads_their_own_medication_history_only(client, family_headers, other_family):
    from tests.conftest import DEMO_PASSWORD, auth, login

    client.patch(f"{API}/medications/1", json={"dosage": "2.5 mg"}, headers=family_headers)
    assert client.get(f"{API}/patients/1/medication-history", headers=family_headers).json()

    stranger = auth(login(client, other_family["email"], DEMO_PASSWORD))
    assert (
        client.get(f"{API}/patients/1/medication-history", headers=stranger).status_code == 404
    )


def test_a_medication_change_is_audited(client, family_headers, db):
    from app.models import AuditAction, AuditEvent

    client.patch(f"{API}/medications/1", json={"dosage": "2.5 mg"}, headers=family_headers)
    entry = db.scalar(select(AuditEvent).where(AuditEvent.action == AuditAction.MEDICATION_CHANGED))
    assert entry is not None
    assert entry.patient_id == 1


# --- the pill organiser ---------------------------------------------------


def test_a_nurse_records_a_fill_and_it_bills_the_addon(client, nurse_headers, db):
    response = client.post(
        f"{API}/patients/1/pill-organiser",
        json={"compartments_filled": 28},
        headers=nurse_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "filled"
    assert body["charged"] is True
    assert body["covers_until"] is not None

    fill = db.get(PillOrganiserFill, body["id"])
    line = db.get(InvoiceLine, fill.invoice_line_id)
    assert line.amount_paise == ADD_ONS_BY_CODE["pill_organiser"].price_paise


def test_the_addon_is_billed_once_a_month_not_once_a_fill(client, nurse_headers):
    """Priced per month. Four weekly fills in March are one ₹199 charge."""
    first = client.post(
        f"{API}/patients/1/pill-organiser", json={"compartments_filled": 28}, headers=nurse_headers
    ).json()
    second = client.post(
        f"{API}/patients/1/pill-organiser", json={"compartments_filled": 28}, headers=nurse_headers
    ).json()
    assert first["charged"] is True
    assert second["charged"] is False


def test_a_fill_nobody_managed_to_make_is_not_a_purchase(client, nurse_headers):
    response = client.post(
        f"{API}/patients/1/pill-organiser",
        json={"compartments_filled": 0, "note": "Organiser was not at the house."},
        headers=nurse_headers,
    )
    body = response.json()
    assert body["status"] == "not_filled"
    assert body["charged"] is False


def test_a_partly_filled_organiser_says_so(client, nurse_headers):
    body = client.post(
        f"{API}/patients/1/pill-organiser", json={"compartments_filled": 20}, headers=nurse_headers
    ).json()
    assert body["status"] == "partial"
    assert body["compartments_filled"] == 20
    assert body["compartments_total"] == 28


def test_a_family_cannot_record_their_own_fill(client, family_headers):
    response = client.post(
        f"{API}/patients/1/pill-organiser", json={"compartments_filled": 28}, headers=family_headers
    )
    assert response.status_code == 403


def test_a_family_can_read_the_fills(client, nurse_headers, family_headers):
    client.post(
        f"{API}/patients/1/pill-organiser", json={"compartments_filled": 28}, headers=nurse_headers
    )
    response = client.get(f"{API}/patients/1/pill-organiser", headers=family_headers)
    assert response.status_code == 200
    assert response.json()[0]["filled_by_name"] == "Anitha Kumar"


def test_more_compartments_than_the_organiser_has_is_refused(client, nurse_headers):
    response = client.post(
        f"{API}/patients/1/pill-organiser", json={"compartments_filled": 40}, headers=nurse_headers
    )
    assert response.status_code == 400
