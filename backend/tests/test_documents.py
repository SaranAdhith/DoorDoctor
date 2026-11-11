"""Phase 12, Stage 1 — uploaded documents in, pages of text out.

What has to be true:

- a born-digital PDF is read from its own text layer, exactly, with no OCR;
- a scanned page goes to OCR, and with no engine (or a dead one) it becomes
  "needs manual entry" rather than a failure;
- a photo is stored upright and without the camera's metadata;
- the strict nurse rule holds, condition by condition;
- unverified machine text reaches admins only;
- erasure covers documents, and nothing here ever needs a GPU or the network.
"""

from __future__ import annotations

import io

import httpx
import pytest
from PIL import Image
from sqlalchemy import select

from app.intelligence.documents import intake, ocr_engine, worker
from app.intelligence.documents.ocr_engine import ChandraEngine, FakeOcrEngine, NullEngine
from app.models import (
    Attachment,
    AuditAction,
    AuditEvent,
    Document,
    DocumentPage,
    DocumentStatus,
    Visit,
)
from app.seed.core import LAKSHMI_HOME
from app.seed.generators import offset_coordinates
from app.services import storage

LAB_TEXT = "Complete Blood Count. Haemoglobin 12.4 g/dL (ref 12.0-15.5). HbA1c 8.1 % (ref 4.0-5.6)."


# --- fixtures ----------------------------------------------------------------


def make_pdf(pages: list[str | None]) -> bytes:
    """A real, minimal PDF. `None` is a page with no text layer — a scan."""
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    pages_ref = len(objects) + 1 + 2 * len(pages)  # reserved below
    page_refs = []
    for text in pages:
        stream = b""
        if text:
            safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream = f"BT /F1 10 Tf 40 760 Td ({safe}) Tj ET".encode("latin-1")
        content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page_refs.append(
            add(
                b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] "
                b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
                % (pages_ref, font, content)
            )
        )
    kids = b" ".join(b"%d 0 R" % ref for ref in page_refs)
    assert add(b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(page_refs))) == pages_ref
    catalog = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_ref)

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, catalog, xref))
    return out.getvalue()


def png_bytes(size=(400, 300), exif_gps: bool = False) -> bytes:
    image = Image.new("RGB", size, "white")
    buffer = io.BytesIO()
    if exif_gps:
        exif = Image.Exif()
        exif[0x010F] = "PhoneMaker"  # Make
        exif[0x0112] = 6  # Orientation: rotate 90° CW to display
        image.save(buffer, format="JPEG", exif=exif.tobytes())
    else:
        image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def no_engine_override():
    ocr_engine.use_engine(None)
    yield
    ocr_engine.use_engine(None)


@pytest.fixture
def patient_id(db, scheduled_visit_id) -> int:
    return db.get(Visit, scheduled_visit_id).patient_id


def upload(client, headers, patient_id, data, name="report.pdf", **form):
    return client.post(
        f"/api/v1/patients/{patient_id}/documents",
        files={"file": (name, data, "application/octet-stream")},
        data=form,
        headers=headers,
    )


def run_worker(db) -> Document:
    document = worker.process_next(db)
    assert document is not None, "a document should have been waiting"
    return document


# --- the pipeline ------------------------------------------------------------


def test_a_text_pdf_is_read_from_its_text_layer_without_ocr(client, db, family_headers, patient_id):
    engine = FakeOcrEngine()
    ocr_engine.use_engine(engine)

    response = upload(client, family_headers, patient_id, make_pdf([LAB_TEXT]), doc_type="lab_report")
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "uploaded" and body["doc_type"] == "lab_report"
    assert body["page_count"] == 1

    document = run_worker(db)
    assert document.status == DocumentStatus.EXTRACTED
    [page] = document.pages
    assert page.method.value == "text_layer" and page.engine == "pypdf"
    assert "HbA1c 8.1" in page.text
    assert engine.calls == 0, "a page with a text layer must never be sent to OCR"


def test_a_scanned_page_with_no_engine_needs_manual_entry(client, db, family_headers, patient_id):
    upload(client, family_headers, patient_id, make_pdf([LAB_TEXT, None]))
    document = run_worker(db)
    assert document.status == DocumentStatus.NEEDS_MANUAL
    assert [p.method.value for p in document.pages] == ["text_layer", "none"]


def test_a_scanned_page_goes_to_ocr_when_an_engine_is_configured(client, db, family_headers, patient_id):
    engine = FakeOcrEngine("Rx: Metformin 500 mg 1-0-1")
    ocr_engine.use_engine(engine)
    upload(client, family_headers, patient_id, make_pdf([None]))

    document = run_worker(db)
    assert document.status == DocumentStatus.EXTRACTED
    [page] = document.pages
    assert page.method.value == "ocr" and page.engine == "fake-ocr"
    assert page.text == "Rx: Metformin 500 mg 1-0-1"
    assert engine.calls == 1


def test_an_engine_that_is_down_costs_the_page_not_the_document(client, db, family_headers, patient_id):
    ocr_engine.use_engine(FakeOcrEngine(text=None))
    upload(client, family_headers, patient_id, make_pdf([None, LAB_TEXT]))
    document = run_worker(db)
    assert document.status == DocumentStatus.NEEDS_MANUAL
    assert [p.method.value for p in document.pages] == ["none", "text_layer"]


def test_an_engine_that_raises_is_contained(client, db, family_headers, patient_id):
    class Exploding:
        name = "exploding"

        def extract(self, image, *, content_type):
            raise RuntimeError("boom")

    ocr_engine.use_engine(Exploding())
    upload(client, family_headers, patient_id, png_bytes(), name="rx.png")
    document = run_worker(db)
    assert document.status == DocumentStatus.NEEDS_MANUAL


def test_a_photo_goes_to_ocr_upright_and_without_its_metadata(client, db, family_headers, patient_id):
    ocr_engine.use_engine(FakeOcrEngine("handwritten prescription"))
    response = upload(client, family_headers, patient_id, png_bytes((400, 300), exif_gps=True), name="rx.jpg")
    assert response.status_code == 202, response.text

    document = db.get(Document, response.json()["id"])
    stored = storage.read(document.attachment.path)
    image = Image.open(io.BytesIO(stored))
    assert not image.getexif(), "camera metadata must not survive storage"
    assert image.size == (300, 400), "the EXIF orientation must be applied before it is dropped"
    assert document.attachment.kind.value == "document_image"

    document = run_worker(db)
    assert document.status == DocumentStatus.EXTRACTED
    assert document.pages[0].text == "handwritten prescription"


def test_a_re_run_replaces_pages_rather_than_adding_to_them(client, db, admin_headers, patient_id):
    response = upload(client, admin_headers, patient_id, make_pdf([LAB_TEXT, None]))
    run_worker(db)

    ocr_engine.use_engine(FakeOcrEngine("now readable"))
    again = client.post(f"/api/v1/documents/{response.json()['id']}/reprocess", headers=admin_headers)
    assert again.status_code == 200 and again.json()["status"] == "uploaded"
    document = run_worker(db)
    assert document.status == DocumentStatus.EXTRACTED
    assert len(db.scalars(select(DocumentPage).where(DocumentPage.document_id == document.id)).all()) == 2


def test_claiming_is_exclusive(client, db, family_headers, patient_id):
    document_id = upload(client, family_headers, patient_id, make_pdf([LAB_TEXT])).json()["id"]
    assert worker.claim(db, document_id) is True
    assert worker.claim(db, document_id) is False


def test_an_abandoned_extraction_is_requeued(client, db, family_headers, patient_id):
    from datetime import timedelta

    from app.database import now

    document_id = upload(client, family_headers, patient_id, make_pdf([LAB_TEXT])).json()["id"]
    worker.claim(db, document_id)
    document = db.get(Document, document_id)
    document.processing_started_at = now() - timedelta(hours=1)
    db.commit()

    assert worker.requeue_stale(db) == 1
    db.refresh(document)
    assert document.status == DocumentStatus.UPLOADED


def test_an_unreadable_file_is_retried_then_failed_with_a_human_reason(client, db, family_headers, patient_id):
    from app.core.intelligence import EXTRACTION_MAX_ATTEMPTS

    document_id = upload(client, family_headers, patient_id, make_pdf([LAB_TEXT])).json()["id"]
    document = db.get(Document, document_id)
    storage.resolve(document.attachment.path).unlink()  # the bytes are gone

    for _ in range(EXTRACTION_MAX_ATTEMPTS):
        assert worker.claim(db, document_id)
        document = worker.process(db, db.get(Document, document_id))
    assert document.status == DocumentStatus.FAILED
    assert "upload it again" in document.error


# --- what is refused at the door --------------------------------------------


def test_an_encrypted_pdf_is_refused(client, family_headers, patient_id):
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.encrypt("secret")
    buffer = io.BytesIO()
    writer.write(buffer)

    response = upload(client, family_headers, patient_id, buffer.getvalue())
    assert response.status_code == 400
    assert "password" in response.json()["detail"].lower()


def test_a_pdf_with_too_many_pages_is_refused(client, family_headers, patient_id):
    from app.core.intelligence import DOCUMENT_MAX_PAGES

    response = upload(client, family_headers, patient_id, make_pdf([None] * (DOCUMENT_MAX_PAGES + 1)))
    assert response.status_code == 400
    assert str(DOCUMENT_MAX_PAGES) in response.json()["detail"]


def test_a_file_that_is_neither_pdf_nor_image_is_refused(client, family_headers, patient_id):
    response = upload(client, family_headers, patient_id, b"MZ\x90\x00 not a document", name="report.pdf")
    assert response.status_code == 400


def test_an_oversized_upload_is_refused_on_the_bytes_not_the_header(client, family_headers, patient_id, monkeypatch):
    from app.routers import documents as documents_router

    monkeypatch.setattr(documents_router, "DOCUMENT_MAX_BYTES", 1000)
    response = upload(client, family_headers, patient_id, make_pdf([LAB_TEXT * 40]))
    assert response.status_code == 400


def test_an_unknown_document_type_is_refused(client, family_headers, patient_id):
    response = upload(client, family_headers, patient_id, make_pdf([LAB_TEXT]), doc_type="horoscope")
    assert response.status_code == 400


def test_the_filename_is_a_title_never_a_path():
    assert intake.clean_title(None, "C:\\Users\\x\\..\\lab report.pdf") == "lab report.pdf"
    assert intake.clean_title(None, "../../etc/passwd") == "passwd"
    assert intake.clean_title("  ", None) == "Document"
    assert intake.clean_title("a\x00b", None) == "a b"
    assert len(intake.clean_title("x" * 500, None)) == 120


# --- the strict nurse rule ---------------------------------------------------


def nurse_upload(client, headers, visit_id, data=None):
    return client.post(
        f"/api/v1/visits/{visit_id}/documents",
        files={"file": ("rx.png", data or png_bytes(), "image/png")},
        data={"doc_type": "prescription"},
        headers=headers,
    )


def test_a_nurse_can_upload_during_their_visit(client, db, nurse_headers, started_visit_id):
    response = nurse_upload(client, nurse_headers, started_visit_id)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["visit_id"] == started_visit_id and body["uploader_role"] == "nurse"
    assert body["can_delete"] is False, "a nurse's visit photo is part of the visit record"


def test_a_nurse_cannot_upload_before_checking_in(client, nurse_headers, scheduled_visit_id):
    response = nurse_upload(client, nurse_headers, scheduled_visit_id)
    assert response.status_code == 400
    assert "in progress" in response.json()["detail"]


def test_a_nurse_cannot_upload_after_checking_out(client, db, nurse_headers, started_visit_id):
    from app.models import VisitStatus

    visit = db.get(Visit, started_visit_id)
    visit.status = VisitStatus.COMPLETED
    db.commit()
    assert nurse_upload(client, nurse_headers, started_visit_id).status_code == 400


def test_a_nurse_cannot_upload_from_an_out_of_range_check_in(client, nurse_headers, scheduled_visit_id):
    lat, lng = offset_coordinates(*LAKSHMI_HOME, metres=1200, bearing_deg=45.0)
    checkin = client.post(
        f"/api/v1/visits/{scheduled_visit_id}/checkin",
        json={"lat": lat, "lng": lng, "accuracy_m": 12},
        headers=nurse_headers,
    )
    assert checkin.json()["location_status"] == "out_of_range"

    response = nurse_upload(client, nurse_headers, scheduled_visit_id)
    assert response.status_code == 403
    assert "away from the patient's home" in response.json()["detail"]


def test_a_nurse_without_a_gps_fix_can_still_upload(client, nurse_headers, started_visit_id):
    # `started_visit_id` checks in with no position at all → `unavailable`.
    assert nurse_upload(client, nurse_headers, started_visit_id).status_code == 202


def test_a_nurse_cannot_upload_to_someone_elses_visit(client, db, nurse_headers, started_visit_id):
    # The small seed has one nurse, so "someone else's" is "not this nurse's".
    visit = db.get(Visit, started_visit_id)
    visit.nurse_id = None
    db.commit()
    assert nurse_upload(client, nurse_headers, started_visit_id).status_code == 404


def test_a_nurse_cannot_use_the_patient_upload_route(client, nurse_headers, patient_id):
    response = upload(client, nurse_headers, patient_id, make_pdf([LAB_TEXT]))
    assert response.status_code == 403


def test_family_cannot_use_the_visit_upload_route(client, family_headers, started_visit_id):
    assert nurse_upload(client, family_headers, started_visit_id).status_code == 403


# --- who sees what -----------------------------------------------------------


def test_raw_page_text_reaches_admins_only(client, db, family_headers, admin_headers, patient_id):
    document_id = upload(client, family_headers, patient_id, make_pdf([LAB_TEXT])).json()["id"]
    run_worker(db)

    family_view = client.get(f"/api/v1/documents/{document_id}", headers=family_headers).json()
    assert "pages" not in family_view
    assert family_view["status_label"] == "Waiting for the care team to check"

    admin_view = client.get(f"/api/v1/documents/{document_id}", headers=admin_headers).json()
    assert "HbA1c 8.1" in admin_view["pages"][0]["text"]
    assert admin_view["pages"][0]["method"] == "text_layer"


def test_a_nurse_sees_their_own_uploads_but_not_unverified_family_ones(
    client, db, family_headers, nurse_headers, started_visit_id
):
    patient_id = db.get(Visit, started_visit_id).patient_id
    family_doc = upload(client, family_headers, patient_id, make_pdf([LAB_TEXT])).json()["id"]
    nurse_doc = nurse_upload(client, nurse_headers, started_visit_id).json()["id"]

    listed = {d["id"] for d in client.get(f"/api/v1/patients/{patient_id}/documents", headers=nurse_headers).json()}
    assert nurse_doc in listed and family_doc not in listed
    assert client.get(f"/api/v1/documents/{family_doc}", headers=nurse_headers).status_code == 404

    document = db.get(Document, family_doc)
    document.status = DocumentStatus.VERIFIED
    db.commit()
    assert client.get(f"/api/v1/documents/{family_doc}", headers=nurse_headers).status_code == 200


def test_another_family_sees_nothing_and_learns_nothing(client, family_headers, patient_id, other_family):
    from tests.conftest import auth, login

    document_id = upload(client, family_headers, patient_id, make_pdf([LAB_TEXT])).json()["id"]
    stranger = auth(login(client, other_family["email"]))

    assert client.get(f"/api/v1/documents/{document_id}", headers=stranger).status_code == 404
    assert client.get(f"/api/v1/documents/99999", headers=stranger).status_code == 404
    assert client.get(f"/api/v1/patients/{patient_id}/documents", headers=stranger).status_code == 404
    assert upload(client, stranger, patient_id, make_pdf([LAB_TEXT])).status_code == 404


def test_the_file_is_served_by_the_existing_attachment_route(client, family_headers, patient_id):
    body = upload(client, family_headers, patient_id, make_pdf([LAB_TEXT])).json()
    response = client.get(f"/api/v1{body['file']['url']}", headers=family_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


def test_the_admin_list_filters_by_status(client, db, family_headers, admin_headers, patient_id):
    upload(client, family_headers, patient_id, make_pdf([None]))
    run_worker(db)
    listed = client.get("/api/v1/admin/documents?status=needs_manual", headers=admin_headers).json()
    assert listed and all(d["status"] == "needs_manual" for d in listed)
    assert listed[0]["pages_needing_manual_entry"] == [1]
    assert client.get("/api/v1/admin/documents", headers=family_headers).status_code == 403


# --- removal, audit, erasure -------------------------------------------------


def test_the_family_uploader_can_remove_it_before_it_is_checked(client, db, family_headers, patient_id):
    document_id = upload(client, family_headers, patient_id, make_pdf([LAB_TEXT])).json()["id"]
    path = db.get(Document, document_id).attachment.path

    assert client.delete(f"/api/v1/documents/{document_id}", headers=family_headers).status_code == 204
    db.expire_all()
    assert db.get(Document, document_id) is None
    assert not storage.exists(path)


def test_nobody_but_an_admin_removes_a_verified_document(client, db, family_headers, admin_headers, patient_id):
    document_id = upload(client, family_headers, patient_id, make_pdf([LAB_TEXT])).json()["id"]
    document = db.get(Document, document_id)
    document.status = DocumentStatus.VERIFIED
    db.commit()

    assert client.delete(f"/api/v1/documents/{document_id}", headers=family_headers).status_code == 403
    assert client.delete(f"/api/v1/documents/{document_id}", headers=admin_headers).status_code == 204


def test_a_nurse_cannot_remove_their_visit_upload(client, nurse_headers, started_visit_id):
    document_id = nurse_upload(client, nurse_headers, started_visit_id).json()["id"]
    assert client.delete(f"/api/v1/documents/{document_id}", headers=nurse_headers).status_code == 403


def test_reprocessing_is_admin_only(client, family_headers, patient_id):
    document_id = upload(client, family_headers, patient_id, make_pdf([LAB_TEXT])).json()["id"]
    assert client.post(f"/api/v1/documents/{document_id}/reprocess", headers=family_headers).status_code == 403


def test_uploads_and_removals_are_audited(client, db, family_headers, patient_id):
    document_id = upload(client, family_headers, patient_id, make_pdf([LAB_TEXT])).json()["id"]
    client.delete(f"/api/v1/documents/{document_id}", headers=family_headers)
    actions = set(
        db.scalars(
            select(AuditEvent.action).where(
                AuditEvent.subject_type == "document", AuditEvent.subject_id == document_id
            )
        )
    )
    assert actions == {AuditAction.DOCUMENT_UPLOADED, AuditAction.DOCUMENT_DELETED}


def test_erasure_removes_documents_their_pages_and_their_files(client, db, family_headers, patient_id):
    from app.services import privacy_service

    upload(client, family_headers, patient_id, make_pdf([LAB_TEXT]))
    run_worker(db)
    paths = [a.path for a in db.scalars(select(Attachment).where(Attachment.patient_id == patient_id))]

    exported = privacy_service.REGISTRY_BY_KEY["documents"].export(db, patient_id)
    assert exported and exported[0]["status"] == "extracted"

    for key in ("documents", "attachments"):
        privacy_service.REGISTRY_BY_KEY[key].erase(db, patient_id)
    db.commit()

    assert not db.scalars(select(Document).where(Document.patient_id == patient_id)).all()
    assert not db.scalars(select(DocumentPage)).all()
    assert not any(storage.exists(p) for p in paths)


def test_the_documents_dataset_erases_before_the_files_it_points_at():
    from app.services import privacy_service

    keys = [d.key for d in privacy_service.REGISTRY]
    assert keys.index("documents") < keys.index("attachments")
    assert keys.index("documents") < keys.index("visits")


def test_documents_switched_off_are_not_there(client, family_headers, patient_id, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "documents_enabled", False)
    assert upload(client, family_headers, patient_id, make_pdf([LAB_TEXT])).status_code == 404
    assert client.get(f"/api/v1/patients/{patient_id}/documents", headers=family_headers).status_code == 404


# --- the OCR engine boundary -------------------------------------------------


class _Response:
    def __init__(self, status_code=200, body=None, raises=False):
        self.status_code = status_code
        self._body = body
        self._raises = raises

    def json(self):
        if self._raises:
            raise ValueError("not json")
        return self._body


def test_chandra_sends_the_image_and_reads_the_answer(monkeypatch):
    seen = {}

    def fake_post(url, json, headers, timeout):
        seen.update(url=url, json=json, headers=headers, timeout=timeout)
        return _Response(body={"choices": [{"message": {"content": "  | Test | Value |  "}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    engine = ChandraEngine(base_url="http://127.0.0.1:8080/v1/", model="chandra-ocr-2", timeout=5)
    result = engine.extract(b"\x89PNG fake", content_type="image/png")

    assert result.text == "| Test | Value |" and result.engine == "chandra-ocr-2"
    assert seen["url"] == "http://127.0.0.1:8080/v1/chat/completions"
    parts = seen["json"]["messages"][0]["content"]
    assert parts[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert seen["json"]["temperature"] == 0
    assert "Authorization" not in seen["headers"], "no key configured, no header sent"


def test_chandra_reads_the_reasoning_slot_when_the_answer_slot_is_empty(monkeypatch):
    """LM Studio can file Chandra's whole transcription as 'thinking'. Seen on a
    real handwritten prescription: `content` was "" and the text was all in
    `reasoning_content`, so the page was wrongly marked for manual entry."""
    body = {"choices": [{"message": {"content": "", "reasoning_content": "<p>Rx: 5% Dextrose stat</p>"}}]}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Response(body=body))
    engine = ChandraEngine(base_url="http://127.0.0.1:1234/v1", model="chandra-ocr-2")
    assert engine.extract(b"img", content_type="image/jpeg").text == "<p>Rx: 5% Dextrose stat</p>"


def test_chandra_prefers_the_answer_slot_when_both_are_filled(monkeypatch):
    body = {"choices": [{"message": {"content": "the page", "reasoning_content": "I will transcribe… the page"}}]}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Response(body=body))
    engine = ChandraEngine(base_url="http://127.0.0.1:1234/v1", model="chandra-ocr-2")
    assert engine.extract(b"img", content_type="image/jpeg").text == "the page"


@pytest.mark.parametrize(
    "behaviour",
    [
        lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("refused")),
        lambda *a, **k: (_ for _ in ()).throw(httpx.ReadTimeout("slow")),
        lambda *a, **k: _Response(status_code=500),
        lambda *a, **k: _Response(raises=True),
        lambda *a, **k: _Response(body={"choices": []}),
        lambda *a, **k: _Response(body={"choices": [{"message": {"content": "   "}}]}),
    ],
    ids=["refused", "timeout", "http-500", "not-json", "no-choices", "empty-text"],
)
def test_chandra_never_raises(monkeypatch, behaviour):
    monkeypatch.setattr(httpx, "post", behaviour)
    engine = ChandraEngine(base_url="http://127.0.0.1:8080/v1", model="chandra-ocr-2")
    assert engine.extract(b"img", content_type="image/png") is None


def test_the_engine_follows_configuration(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ocr_engine", "none")
    assert isinstance(ocr_engine.get_engine(), NullEngine)
    monkeypatch.setattr(settings, "ocr_engine", "chandra_local")
    assert isinstance(ocr_engine.get_engine(), ChandraEngine)
    monkeypatch.setattr(settings, "ocr_engine", "tesseract-please")
    assert isinstance(ocr_engine.get_engine(), NullEngine)

    fake = FakeOcrEngine()
    ocr_engine.use_engine(fake)
    assert ocr_engine.get_engine() is fake


def test_the_test_pdf_helper_really_has_a_text_layer():
    """Guards the fixture: if this fails, the pipeline tests prove nothing."""
    from app.intelligence.documents import pdf_text

    pdf = make_pdf([LAB_TEXT, None])
    assert pdf_text.inspect(pdf).page_count == 2
    texts = pdf_text.page_texts(pdf)
    assert "HbA1c" in texts[0] and texts[1] == ""
