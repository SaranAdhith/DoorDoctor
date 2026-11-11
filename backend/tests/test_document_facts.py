"""Phase 12, Stage 2 — facts proposed from a page, and an admin's decisions on them.

What has to be true:

- a lab table is read column by column with no model, exactly as printed;
- an LLM fact whose numbers aren't on the page never reaches the admin;
- nothing is in the record until a person decides, and a document can't be
  verified past an undecided fact;
- an admin's correction keeps what software first proposed;
- nurses and families see only decided facts, and only on verified documents;
- erasure covers facts.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.intelligence.documents import extraction, ocr_engine, worker
from app.intelligence.documents import text as page_text
from app.intelligence.documents.ocr_engine import FakeOcrEngine
from app.models import AuditAction, AuditEvent, Document, DocumentStatus, ExtractedFact, FactStatus, Visit
from tests.test_documents import make_pdf, png_bytes

# What Chandra OCR 2 actually returned for a printed lab report on the
# founder's laptop (2026-11-07), trimmed.
CHANDRA_LAB = (
    '<div data-bbox="45 58 639 117" data-label="Section-Header"><h1>CITY DIAGNOSTICS LAB - Bengaluru</h1></div>'
    '<div data-bbox="45 197 854 652" data-label="Table"><table border="1"><thead><tr><th>Test</th>'
    "<th>Result</th><th>Unit</th><th>Reference</th></tr></thead><tbody>"
    "<tr><td>Haemoglobin</td><td>12.4</td><td>g/dL</td><td>12.0 - 15.5</td></tr>"
    "<tr><td>HbA1c</td><td>8.1</td><td>%</td><td>4.0 - 5.6</td></tr>"
    "<tr><td>Fasting Glucose</td><td>142</td><td>mg/dL</td><td>70 - 100</td></tr>"
    "<tr><td>Creatinine</td><td>0.9</td><td>mg/dL</td><td>0.6 - 1.1</td></tr>"
    "</tbody></table></div>"
    '<div data-bbox="45 798 539 847" data-label="Text"><p>Patient: Lakshmi R. Date: 02-11-2026</p></div>'
)

CHANDRA_RX = (
    '<div data-label="Text"><p>Emp: hypoglycemia (R/S - 5 days)</p></div>'
    '<div data-label="Text"><p>ctE - BP - <u>110/70</u><br/>PR - <u>60 bpm</u></p></div>'
    '<div data-label="Text"><p>→ DRS 2 sachets.</p></div>'
)


@pytest.fixture(autouse=True)
def no_engine_override():
    ocr_engine.use_engine(None)
    yield
    ocr_engine.use_engine(None)


@pytest.fixture
def patient_id(db, scheduled_visit_id) -> int:
    return db.get(Visit, scheduled_visit_id).patient_id


def _upload_and_read(client, db, headers, patient_id, ocr_text: str) -> Document:
    ocr_engine.use_engine(FakeOcrEngine(ocr_text))
    response = client.post(
        f"/api/v1/patients/{patient_id}/documents",
        files={"file": ("page.png", png_bytes(), "image/png")},
        data={"doc_type": "lab_report"},
        headers=headers,
    )
    assert response.status_code == 202, response.text
    document = worker.process_next(db)
    assert document is not None
    return document


def _llm(monkeypatch, answer: str | None):
    calls = []

    def fake(**kwargs):
        calls.append(kwargs)
        return answer

    monkeypatch.setattr(extraction.llm_client, "available", lambda: True)
    monkeypatch.setattr(extraction.llm_client, "complete", fake)
    return calls


# --- reading Chandra's HTML ---------------------------------------------------


def test_chandra_html_becomes_plain_text_with_table_rows():
    plain = page_text.to_text(CHANDRA_LAB)
    assert "data-bbox" not in plain and "<td>" not in plain
    assert "HbA1c | 8.1 | % | 4.0 - 5.6" in plain
    assert "Patient: Lakshmi R. Date: 02-11-2026" in plain


def test_plain_text_passes_through_untouched():
    assert page_text.to_text("Haemoglobin 12.4 g/dL") == "Haemoglobin 12.4 g/dL"
    assert page_text.tables("Haemoglobin 12.4 g/dL") == []


def test_script_content_never_reaches_the_text():
    assert "pwned" not in page_text.to_text('<p>Rx<script>pwned()</script></p>')


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("12.0 - 15.5", (12.0, 15.5)),
        ("4.0-5.6", (4.0, 5.6)),
        ("70 to 100", (70.0, 100.0)),
        ("< 5.7", (None, 5.7)),
        ("Up to 1.2", (None, 1.2)),
        ("> 40", (40.0, None)),
        ("", (None, None)),
        ("Negative", (None, None)),
    ],
)
def test_reference_ranges_are_read_as_printed(text, expected):
    assert extraction.parse_range(text) == expected


def test_a_lab_table_is_read_column_by_column_without_a_model():
    facts = extraction.table_facts(CHANDRA_LAB, page_no=1)
    by_label = {f.label: f for f in facts}
    assert set(by_label) == {"Haemoglobin", "HbA1c", "Fasting Glucose", "Creatinine"}
    hba1c = by_label["HbA1c"]
    assert (hba1c.value_num, hba1c.unit, hba1c.ref_low, hba1c.ref_high) == (8.1, "%", 4.0, 5.6)
    assert hba1c.source.value == "table" and hba1c.page_no == 1
    assert hba1c.source_quote == "HbA1c | 8.1 | % | 4.0 - 5.6"


def test_a_unit_in_the_result_cell_is_split_off():
    html = "<table><tr><th>Investigation</th><th>Observed Value</th><th>Biological Ref. Interval</th></tr>" \
           "<tr><td>TSH</td><td>6.2 uIU/mL</td><td>0.4 - 4.0</td></tr></table>"
    [fact] = extraction.table_facts(html)
    assert (fact.label, fact.value_num, fact.unit, fact.ref_high) == ("TSH", 6.2, "uIU/mL", 4.0)


def test_a_table_without_a_result_column_is_left_alone():
    html = "<table><tr><th>Medicine</th><th>Dose</th></tr><tr><td>Metformin</td><td>500 mg</td></tr></table>"
    assert extraction.table_facts(html) == []


# --- the LLM, and its grounding check -------------------------------------------


def test_llm_facts_are_proposed_when_grounded(monkeypatch):
    answer = json.dumps(
        [
            {"kind": "vital_sign", "label": "Blood pressure", "value_text": "110/70", "value_num": None,
             "unit": "", "source_quote": "BP - 110/70"},
            {"kind": "instruction", "label": "DRS", "value_text": "2 sachets", "value_num": 2, "unit": "sachets",
             "source_quote": "DRS 2 sachets"},
        ]
    )
    calls = _llm(monkeypatch, answer)
    facts = extraction.llm_facts(CHANDRA_RX, page_no=1)
    assert [f.label for f in facts] == ["Blood pressure", "DRS"]
    assert all(f.source.value == "llm" for f in facts)
    # The model is sent clean text, not layout markup.
    assert "data-label" not in calls[0]["user"] and "110/70" in calls[0]["user"]


def test_an_llm_number_that_is_not_on_the_page_drops_the_fact(monkeypatch):
    answer = json.dumps(
        [
            {"kind": "vital_sign", "label": "Pulse", "value_text": "60 bpm", "value_num": 60, "unit": "bpm"},
            {"kind": "vital_sign", "label": "Pulse", "value_text": "66 bpm", "value_num": 66, "unit": "bpm"},
            {"kind": "lab_value", "label": "Glucose", "value_text": "3.3", "value_num": 3.3, "unit": "mmol/L"},
        ]
    )
    _llm(monkeypatch, answer)
    facts = extraction.llm_facts(CHANDRA_RX)
    assert [(f.label, f.value_num) for f in facts] == [("Pulse", 60.0)]


def test_a_paraphrased_quote_is_dropped_but_the_fact_kept(monkeypatch):
    _llm(monkeypatch, json.dumps([{"kind": "diagnosis", "label": "Impression", "value_text": "hypoglycemia",
                                   "source_quote": "the doctor thinks low sugar"}]))
    [fact] = extraction.llm_facts(CHANDRA_RX)
    assert fact.source_quote == ""


@pytest.mark.parametrize("answer", [None, "", "not json", '{"a": 1}', "[1, 2, 3]", '[{"label": ""}]'])
def test_a_bad_llm_answer_proposes_nothing(monkeypatch, answer):
    _llm(monkeypatch, answer)
    assert extraction.llm_facts(CHANDRA_RX) == []


def test_an_answer_wrapped_in_prose_and_fences_is_still_read(monkeypatch):
    _llm(monkeypatch, 'Here you go:\n```json\n[{"kind": "vital_sign", "label": "Pulse", "value_text": "60 bpm"}]\n```')
    assert [f.label for f in extraction.llm_facts(CHANDRA_RX)] == ["Pulse"]


def test_an_unknown_kind_becomes_other(monkeypatch):
    _llm(monkeypatch, '[{"kind": "horoscope", "label": "Pulse", "value_text": "60 bpm"}]')
    assert extraction.llm_facts(CHANDRA_RX)[0].kind.value == "other"


def test_no_llm_configured_means_table_facts_only(monkeypatch):
    monkeypatch.setattr(extraction.llm_client, "available", lambda: False)
    assert extraction.llm_facts(CHANDRA_RX) == []
    assert len(extraction.propose_for_page(CHANDRA_LAB)) == 4


def test_an_llm_fact_repeating_a_table_row_is_not_proposed_twice(monkeypatch):
    _llm(monkeypatch, '[{"kind": "lab_value", "label": "HbA1c", "value_text": "8.1", "value_num": 8.1}]')
    facts = extraction.propose_for_page(CHANDRA_LAB)
    assert sum(f.label == "HbA1c" for f in facts) == 1


# --- the pipeline -------------------------------------------------------------


def test_reading_a_page_proposes_its_facts(client, db, family_headers, patient_id):
    document = _upload_and_read(client, db, family_headers, patient_id, CHANDRA_LAB)
    assert document.status == DocumentStatus.EXTRACTED
    assert len(document.facts) == 4
    assert all(f.status == FactStatus.PROPOSED for f in document.facts)
    assert all(f.patient_id == patient_id for f in document.facts)


def test_a_text_layer_pdf_is_read_too(client, db, family_headers, patient_id, monkeypatch):
    _llm(monkeypatch, '[{"kind": "lab_value", "label": "HbA1c", "value_text": "8.1 %", "value_num": 8.1}]')
    client.post(
        f"/api/v1/patients/{patient_id}/documents",
        files={"file": ("r.pdf", make_pdf(["Complete Blood Count. Haemoglobin 12.4 g/dL. HbA1c 8.1 % (ref 4.0-5.6)."]),
                        "application/pdf")},
        headers=family_headers,
    )
    document = worker.process_next(db)
    assert [f.label for f in document.facts] == ["HbA1c"]


def test_an_extraction_failure_costs_the_facts_not_the_pages(client, db, family_headers, patient_id, monkeypatch):
    def explode(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(extraction, "extract_document", explode)
    document = _upload_and_read(client, db, family_headers, patient_id, CHANDRA_LAB)
    assert document.status == DocumentStatus.EXTRACTED
    assert document.pages[0].text == CHANDRA_LAB
    assert document.facts == []


# --- deciding -------------------------------------------------------------------


def _decide(client, headers, document_id, fact_id, **body):
    return client.patch(f"/api/v1/documents/{document_id}/facts/{fact_id}", json=body, headers=headers)


def test_the_review_queue_holds_read_documents_oldest_first(client, db, family_headers, admin_headers, patient_id):
    first = _upload_and_read(client, db, family_headers, patient_id, CHANDRA_LAB).id
    second = _upload_and_read(client, db, family_headers, patient_id, CHANDRA_LAB).id
    queue = client.get("/api/v1/admin/documents/queue", headers=admin_headers).json()
    ids = [d["id"] for d in queue]
    assert ids.index(first) < ids.index(second)
    assert queue[0]["facts_pending"] == 4
    assert client.get("/api/v1/admin/documents/queue", headers=family_headers).status_code == 403


def test_an_admin_confirms_edits_and_rejects(client, db, family_headers, admin_headers, patient_id):
    document = _upload_and_read(client, db, family_headers, patient_id, CHANDRA_LAB)
    hb, hba1c, glucose, creat = sorted(document.facts, key=lambda f: f.id)

    assert _decide(client, admin_headers, document.id, hb.id, action="confirm").json()["status"] == "confirmed"
    edited = _decide(client, admin_headers, document.id, glucose.id, action="edit", value_text="124", value_num=124).json()
    assert edited["status"] == "edited" and edited["value_num"] == 124
    assert edited["original"]["value_num"] == 142, "the proposal survives the correction"
    assert edited["ref_high"] == 100, "an edit changes only the fields sent"
    assert _decide(client, admin_headers, document.id, creat.id, action="reject").json()["status"] == "rejected"


def test_verification_waits_for_every_fact(client, db, family_headers, admin_headers, patient_id):
    document = _upload_and_read(client, db, family_headers, patient_id, CHANDRA_LAB)
    facts = sorted(document.facts, key=lambda f: f.id)
    _decide(client, admin_headers, document.id, facts[0].id, action="confirm")

    blocked = client.post(f"/api/v1/documents/{document.id}/verify", json={}, headers=admin_headers)
    assert blocked.status_code == 409 and "3 facts are still waiting" in blocked.json()["detail"]

    for fact in facts[1:]:
        _decide(client, admin_headers, document.id, fact.id, action="confirm")
    verified = client.post(
        f"/api/v1/documents/{document.id}/verify",
        json={"document_date": "2026-11-02", "doc_type": "lab_report"},
        headers=admin_headers,
    )
    assert verified.status_code == 200, verified.text
    body = verified.json()
    assert body["status"] == "verified" and body["document_date"] == "2026-11-02"
    assert body["status_label"] == "Checked by the care team"


def test_a_decided_document_is_closed(client, db, family_headers, admin_headers, patient_id):
    document = _upload_and_read(client, db, family_headers, patient_id, CHANDRA_LAB)
    for fact in document.facts:
        _decide(client, admin_headers, document.id, fact.id, action="confirm")
    client.post(f"/api/v1/documents/{document.id}/verify", json={}, headers=admin_headers)

    fact_id = document.facts[0].id
    assert _decide(client, admin_headers, document.id, fact_id, action="reject").status_code == 409
    assert client.post(f"/api/v1/documents/{document.id}/facts", json={"label": "x"}, headers=admin_headers).status_code == 409


def test_an_admin_adds_a_fact_for_a_page_nothing_could_read(client, db, family_headers, admin_headers, patient_id):
    ocr_engine.use_engine(FakeOcrEngine(text=None))
    client.post(
        f"/api/v1/patients/{patient_id}/documents",
        files={"file": ("rx.png", png_bytes(), "image/png")},
        headers=family_headers,
    )
    document = worker.process_next(db)
    assert document.status == DocumentStatus.NEEDS_MANUAL

    added = client.post(
        f"/api/v1/documents/{document.id}/facts",
        json={"kind": "medication", "label": "ORS", "value_text": "2 sachets", "page_no": 1},
        headers=admin_headers,
    )
    assert added.status_code == 201, added.text
    assert added.json()["status"] == "added" and added.json()["source"] == "manual"
    assert client.post(f"/api/v1/documents/{document.id}/verify", json={}, headers=admin_headers).status_code == 200


def test_a_bad_edit_is_refused(client, db, family_headers, admin_headers, patient_id):
    document = _upload_and_read(client, db, family_headers, patient_id, CHANDRA_LAB)
    fact = document.facts[0]
    assert _decide(client, admin_headers, document.id, fact.id, action="edit", ref_low=10, ref_high=5).status_code == 400
    assert _decide(client, admin_headers, document.id, fact.id, action="edit", label="").status_code == 400
    assert _decide(client, admin_headers, document.id, fact.id, action="shred").status_code == 422
    assert _decide(client, admin_headers, document.id, fact.id, action="edit", secret="x").status_code == 422
    assert _decide(client, admin_headers, document.id, 99999, action="confirm").status_code == 404


def test_rejecting_a_document_needs_a_reason_and_is_audited(client, db, family_headers, admin_headers, patient_id):
    document = _upload_and_read(client, db, family_headers, patient_id, CHANDRA_LAB)
    assert client.post(f"/api/v1/documents/{document.id}/reject", json={"reason": ""}, headers=admin_headers).status_code == 422
    rejected = client.post(
        f"/api/v1/documents/{document.id}/reject", json={"reason": "Wrong patient"}, headers=admin_headers
    )
    assert rejected.json()["status"] == "rejected"
    detail = db.scalar(
        select(AuditEvent.detail).where(
            AuditEvent.subject_id == document.id, AuditEvent.action == AuditAction.DOCUMENT_REJECTED
        )
    )
    assert "Wrong patient" in detail


def test_only_admins_decide(client, db, family_headers, nurse_headers, admin_headers, patient_id):
    document = _upload_and_read(client, db, family_headers, patient_id, CHANDRA_LAB)
    fact_id = document.facts[0].id
    for headers in (family_headers, nurse_headers):
        assert _decide(client, headers, document.id, fact_id, action="confirm").status_code == 403
        assert client.post(f"/api/v1/documents/{document.id}/verify", json={}, headers=headers).status_code == 403
        assert client.post(f"/api/v1/documents/{document.id}/extract", headers=headers).status_code == 403


def test_extracting_again_keeps_every_decision(client, db, family_headers, admin_headers, patient_id):
    document = _upload_and_read(client, db, family_headers, patient_id, CHANDRA_LAB)
    facts = sorted(document.facts, key=lambda f: f.id)
    _decide(client, admin_headers, document.id, facts[0].id, action="reject")
    _decide(client, admin_headers, document.id, facts[1].id, action="edit", value_text="8.0", value_num=8.0)

    again = client.post(f"/api/v1/documents/{document.id}/extract", headers=admin_headers).json()
    statuses = sorted(f["status"] for f in again["facts"])
    assert statuses == ["edited", "proposed", "proposed", "rejected"], "decided facts survive, undecided are re-proposed"
    assert sum(f["label"] == "HbA1c" for f in again["facts"]) == 1, "a corrected value must not come back"


def test_a_renamed_fact_does_not_come_back_under_its_old_name(client, db, family_headers, admin_headers, patient_id):
    document = _upload_and_read(client, db, family_headers, patient_id, CHANDRA_LAB)
    hb = sorted(document.facts, key=lambda f: f.id)[0]
    _decide(client, admin_headers, document.id, hb.id, action="edit", label="Hemoglobin")
    again = client.post(f"/api/v1/documents/{document.id}/extract", headers=admin_headers).json()
    labels = [f["label"] for f in again["facts"]]
    assert "Hemoglobin" in labels and "Haemoglobin" not in labels


# --- who sees which facts --------------------------------------------------------


def _verify_all(client, admin_headers, document, reject_first=True):
    for index, fact in enumerate(sorted(document.facts, key=lambda f: f.id)):
        action = "reject" if reject_first and index == 0 else "confirm"
        _decide(client, admin_headers, document.id, fact.id, action=action)
    assert client.post(f"/api/v1/documents/{document.id}/verify", json={}, headers=admin_headers).status_code == 200


def test_family_and_nurse_see_no_facts_before_verification(
    client, db, family_headers, nurse_headers, admin_headers, patient_id, started_visit_id
):
    document = _upload_and_read(client, db, family_headers, patient_id, CHANDRA_LAB)
    assert client.get(f"/api/v1/documents/{document.id}", headers=family_headers).json()["facts"] == []
    admin_view = client.get(f"/api/v1/documents/{document.id}", headers=admin_headers).json()
    assert len(admin_view["facts"]) == 4 and "source_quote" in admin_view["facts"][0]


def test_after_verification_only_decided_facts_are_shown(
    client, db, family_headers, nurse_headers, admin_headers, patient_id, started_visit_id
):
    document = _upload_and_read(client, db, family_headers, patient_id, CHANDRA_LAB)
    _verify_all(client, admin_headers, document)

    family = client.get(f"/api/v1/documents/{document.id}", headers=family_headers).json()
    assert len(family["facts"]) == 3, "the rejected fact never reaches the family"
    assert "source_quote" not in family["facts"][0], "review details are for admins"
    assert family["facts_in_record"] == 3

    nurse = client.get(f"/api/v1/documents/{document.id}", headers=nurse_headers).json()
    assert len(nurse["facts"]) == 3
    hba1c = next(f for f in nurse["facts"] if f["label"] == "HbA1c")
    assert hba1c["out_of_range"] is True


def test_out_of_range_needs_both_a_number_and_a_range():
    fact = ExtractedFact(value_num=8.1, ref_low=4.0, ref_high=5.6)
    assert fact.out_of_range is True
    assert ExtractedFact(value_num=5.0, ref_low=4.0, ref_high=5.6).out_of_range is False
    assert ExtractedFact(value_num=5.0).out_of_range is None
    assert ExtractedFact(ref_low=4.0, ref_high=5.6).out_of_range is None


def test_verification_is_audited_with_the_count(client, db, family_headers, admin_headers, patient_id):
    document = _upload_and_read(client, db, family_headers, patient_id, CHANDRA_LAB)
    _verify_all(client, admin_headers, document)
    detail = db.scalar(
        select(AuditEvent.detail).where(
            AuditEvent.subject_id == document.id, AuditEvent.action == AuditAction.DOCUMENT_VERIFIED
        )
    )
    assert "3 facts added to the record" in detail


def test_erasure_and_export_cover_facts(client, db, family_headers, admin_headers, patient_id):
    from app.services import privacy_service

    document = _upload_and_read(client, db, family_headers, patient_id, CHANDRA_LAB)
    _verify_all(client, admin_headers, document)
    db.expire_all()  # the decisions were made through the API, in another session

    exported = privacy_service.REGISTRY_BY_KEY["documents"].export(db, patient_id)
    labels = {f["label"] for d in exported for f in d["facts"]}
    assert labels == {"HbA1c", "Fasting Glucose", "Creatinine"}

    privacy_service.REGISTRY_BY_KEY["documents"].erase(db, patient_id)
    db.commit()
    assert db.scalars(select(ExtractedFact).where(ExtractedFact.patient_id == patient_id)).all() == []
