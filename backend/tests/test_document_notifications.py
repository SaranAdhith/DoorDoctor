"""Phase 12 — everyone who can see a document hears when it moves, and nobody else.

The rule is `notify.py`'s table: recipients follow `access.py`, the person who
caused a change is never told about it, and the message says nothing about
what the document contains.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.intelligence.documents import ocr_engine, worker
from app.intelligence.documents.ocr_engine import FakeOcrEngine
from app.models import Notification, NotificationType, Nurse, Patient, User, UserRole, Visit
from tests.conftest import auth, login
from tests.test_document_facts import CHANDRA_LAB
from tests.test_documents import png_bytes


@pytest.fixture(autouse=True)
def engine():
    ocr_engine.use_engine(FakeOcrEngine(CHANDRA_LAB))
    yield
    ocr_engine.use_engine(None)


@pytest.fixture
def people(db, scheduled_visit_id):
    visit = db.get(Visit, scheduled_visit_id)
    patient = db.get(Patient, visit.patient_id)
    nurse = db.get(Nurse, visit.nurse_id)
    admins = set(db.scalars(select(User.id).where(User.role == UserRole.ADMIN)))
    return {"patient": patient, "family": patient.family_user_id, "nurse": nurse.user_id, "admins": admins}


def _doc_notes(db, user_id):
    db.expire_all()
    return db.scalars(
        select(Notification).where(Notification.user_id == user_id, Notification.type == NotificationType.DOCUMENT)
    ).all()


def _upload(client, headers, patient_id):
    response = client.post(
        f"/api/v1/patients/{patient_id}/documents",
        files={"file": ("cbc.png", png_bytes(), "image/png")},
        data={"title": "CBC report"},
        headers=headers,
    )
    assert response.status_code == 202, response.text
    return response.json()["id"]


def test_a_family_upload_tells_nobody_until_it_is_read(client, db, family_headers, people):
    _upload(client, family_headers, people["patient"].id)
    assert _doc_notes(db, people["family"]) == [], "the uploader is not told about their own upload"
    assert all(_doc_notes(db, a) == [] for a in people["admins"])

    worker.process_next(db)
    family = _doc_notes(db, people["family"])
    assert [n.title for n in family] == ["Document ready for review"]
    for admin in people["admins"]:
        assert [n.title for n in _doc_notes(db, admin)] == ["Document ready for review"]
    assert _doc_notes(db, people["nurse"]) == [], "a nurse can't see an unverified family upload"


def test_an_admin_upload_tells_the_family(client, db, admin_headers, people):
    _upload(client, admin_headers, people["patient"].id)
    [note] = _doc_notes(db, people["family"])
    assert note.title == "New document added"
    assert "CBC report" in note.message and people["patient"].name.split()[0] in note.message


def test_verification_tells_the_family_and_the_nurses_on_the_case(client, db, family_headers, admin_headers, people):
    document_id = _upload(client, family_headers, people["patient"].id)
    document = worker.process_next(db)
    for fact in document.facts:
        client.patch(f"/api/v1/documents/{document_id}/facts/{fact.id}", json={"action": "confirm"}, headers=admin_headers)
    assert client.post(f"/api/v1/documents/{document_id}/verify", json={}, headers=admin_headers).status_code == 200

    family_titles = [n.title for n in _doc_notes(db, people["family"])]
    assert family_titles[-1] == "Document checked by the care team"
    assert "4 details added to the record" in _doc_notes(db, people["family"])[-1].message
    assert [n.title for n in _doc_notes(db, people["nurse"])] == ["Document checked by the care team"]
    # The admin who verified is not told what they just did.
    acting_admin = db.scalar(select(User.id).where(User.email == "admin@doordoctor.in"))
    assert "Document checked by the care team" not in [n.title for n in _doc_notes(db, acting_admin)]


def test_rejection_tells_the_family_without_the_reason(client, db, family_headers, admin_headers, people):
    document_id = _upload(client, family_headers, people["patient"].id)
    worker.process_next(db)
    client.post(f"/api/v1/documents/{document_id}/reject", json={"reason": "Wrong patient"}, headers=admin_headers)
    note = _doc_notes(db, people["family"])[-1]
    assert note.title == "Document not added"
    assert "Wrong patient" not in note.message, "the reason is for the audit log"


def test_a_nurse_hears_about_their_own_upload_moving(client, db, nurse_headers, started_visit_id, people):
    client.post(
        f"/api/v1/visits/{started_visit_id}/documents",
        files={"file": ("rx.png", png_bytes(), "image/png")},
        headers=nurse_headers,
    )
    assert _doc_notes(db, people["nurse"]) == []
    assert [n.title for n in _doc_notes(db, people["family"])] == ["New document added"]
    worker.process_next(db)
    assert [n.title for n in _doc_notes(db, people["nurse"])] == ["Document ready for review"]


def test_a_failed_read_tells_the_family_and_admins(client, db, family_headers, people):
    from app.core.intelligence import EXTRACTION_MAX_ATTEMPTS
    from app.models import Document
    from app.services import storage

    document_id = _upload(client, family_headers, people["patient"].id)
    storage.resolve(db.get(Document, document_id).attachment.path).unlink()
    for _ in range(EXTRACTION_MAX_ATTEMPTS):
        worker.claim(db, document_id)
        worker.process(db, db.get(Document, document_id))
    assert [n.title for n in _doc_notes(db, people["family"])] == ["Document could not be read"]
    assert all([n.title for n in _doc_notes(db, a)] == ["Document could not be read"] for a in people["admins"])


def test_removal_tells_the_family_when_someone_else_removes_it(client, db, admin_headers, people):
    document_id = _upload(client, admin_headers, people["patient"].id)
    assert client.delete(f"/api/v1/documents/{document_id}", headers=admin_headers).status_code == 204
    assert [n.title for n in _doc_notes(db, people["family"])] == ["New document added", "Document removed"]


def test_the_menu_count_and_marking_seen(client, db, family_headers, admin_headers, people):
    _upload(client, admin_headers, people["patient"].id)
    _upload(client, admin_headers, people["patient"].id)
    assert client.get("/api/v1/documents/notifications/unseen", headers=family_headers).json() == {"count": 2}

    assert client.post("/api/v1/documents/notifications/seen", headers=family_headers).json() == {"marked": 2}
    assert client.get("/api/v1/documents/notifications/unseen", headers=family_headers).json() == {"count": 0}
    # The bell reads the same rows, so they are read there too.
    bell = client.get("/api/v1/notifications", headers=family_headers).json()
    assert all(n["read"] for n in bell if n["type"] == "document")


def test_another_family_is_never_told(client, db, admin_headers, people, other_family):
    _upload(client, admin_headers, people["patient"].id)
    worker.process_next(db)
    stranger = auth(login(client, other_family["email"]))
    assert client.get("/api/v1/documents/notifications/unseen", headers=stranger).json() == {"count": 0}
