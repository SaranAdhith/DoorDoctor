"""Family health reports (§4.1).

The property that matters most: **a report is a record**. Once generated, it
must keep saying what it said, even after the readings behind it have moved on.
"""

import pytest
from sqlalchemy import select

from app.models import Notification, NotificationType, Patient, Report, ReportKind
from app.services import report_service, summary_service
from tests.conftest import ABNORMAL_VITALS, auth, login


def _generate(client, headers, patient_id=1, kind="on_demand"):
    response = client.post(
        f"/api/v1/patients/{patient_id}/reports/generate", json={"kind": kind}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------


def test_generating_a_report_freezes_the_summary(client, family_headers):
    report = _generate(client, family_headers)

    assert report["kind"] == "on_demand"
    assert report["title"] == "Care report"
    assert report["headline"]
    assert report["paragraphs"], "a report with no narrative is an empty document"
    assert report["patient_name"] == "Lakshmi D'Souza"


def test_a_report_never_uses_clinical_language(client, family_headers):
    report = _generate(client, family_headers, kind="monthly")

    prose = [
        report["headline"],
        *report["paragraphs"],
        *[h["text"] for h in report["highlights"]],
        *report["what_happens_next"],
    ]
    for text in prose:
        assert summary_service.contains_clinical_language(text) is None, text


def test_regenerating_a_period_refreshes_rather_than_duplicates(client, family_headers, db):
    """The scheduler firing twice must not produce two Sunday reports."""
    first = _generate(client, family_headers, kind="weekly")
    second = _generate(client, family_headers, kind="weekly")

    assert first["id"] == second["id"]
    assert second["generated_at"] >= first["generated_at"]
    assert db.scalar(select(Report.id).where(Report.kind == ReportKind.WEEKLY)) is not None
    assert len(db.scalars(select(Report).where(Report.kind == ReportKind.WEEKLY)).all()) == 1


def test_weekly_and_monthly_are_separate_documents(client, family_headers):
    weekly = _generate(client, family_headers, kind="weekly")
    monthly = _generate(client, family_headers, kind="monthly")

    assert weekly["id"] != monthly["id"]
    assert weekly["title"] == "Weekly care report"
    assert monthly["title"] == "Monthly care report"
    assert monthly["period_start"] < weekly["period_start"]


def test_a_frozen_report_does_not_change_when_new_readings_arrive(
    client, family_headers, nurse_headers, started_visit_id
):
    """This is the whole reason the narrative is stored rather than re-derived."""
    before = _generate(client, family_headers)

    recorded = client.post(
        f"/api/v1/visits/{started_visit_id}/vitals", json=ABNORMAL_VITALS, headers=nurse_headers
    )
    assert recorded.status_code == 201, recorded.text

    fetched = client.get(f"/api/v1/reports/{before['id']}", headers=family_headers).json()
    assert fetched["headline"] == before["headline"]
    assert fetched["paragraphs"] == before["paragraphs"]
    assert fetched["reading_count"] == before["reading_count"]

    # ...while a fresh summary *does* see it.
    live = client.get("/api/v1/patients/1/plain-summary", headers=family_headers).json()
    assert live["reading_count"] == before["reading_count"] + 1


def test_generating_a_report_notifies_the_family(client, family_headers, db):
    report = _generate(client, family_headers)

    notification = db.scalar(
        select(Notification)
        .where(Notification.type == NotificationType.SYSTEM, Notification.patient_id == 1)
        .order_by(Notification.id.desc())
    )
    assert notification is not None
    assert report["title"] in notification.title


def test_refreshing_a_report_does_not_notify_again(client, family_headers, db):
    """A regenerated document is not news."""
    _generate(client, family_headers, kind="weekly")
    before = len(db.scalars(select(Notification).where(Notification.type == NotificationType.SYSTEM)).all())

    _generate(client, family_headers, kind="weekly")
    after = len(db.scalars(select(Notification).where(Notification.type == NotificationType.SYSTEM)).all())

    assert after == before


# --------------------------------------------------------------------------
# Listing
# --------------------------------------------------------------------------


def test_reports_list_newest_first(client, family_headers):
    _generate(client, family_headers, kind="monthly")
    _generate(client, family_headers, kind="weekly")

    listed = client.get("/api/v1/patients/1/reports", headers=family_headers).json()
    assert len(listed) == 2
    assert listed[0]["generated_at"] >= listed[1]["generated_at"]


def test_a_patient_with_no_reports_lists_nothing(client, family_headers):
    assert client.get("/api/v1/patients/1/reports", headers=family_headers).json() == []


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------


def test_the_pdf_is_a_real_document(client, family_headers):
    report = _generate(client, family_headers)

    response = client.get(f"/api/v1/reports/{report['id']}/pdf", headers=family_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert len(response.content) > 2000, "a one-page PDF should not be this small"
    assert "inline" in response.headers["content-disposition"]


def test_the_pdf_needs_a_token(client, family_headers):
    report = _generate(client, family_headers)
    assert client.get(f"/api/v1/reports/{report['id']}/pdf").status_code == 401


def test_the_pdf_renders_the_frozen_narrative(client, family_headers, db):
    """Re-reading last month's PDF must not re-run the generator against today."""
    report_json = _generate(client, family_headers)
    report = db.get(Report, report_json["id"])

    html = report_service._render_html(report)
    assert report.headline in html or report.headline.replace("'", "&#x27;") in html
    for paragraph in report.narrative["paragraphs"]:
        assert paragraph in html or paragraph.replace("'", "&#x27;") in html


# --------------------------------------------------------------------------
# Authorization — the same disclosure rule as everywhere else
# --------------------------------------------------------------------------


def test_another_familys_report_is_a_404(client, family_headers, other_family):
    report = _generate(client, family_headers)
    headers = auth(login(client, other_family["email"]))

    assert client.get(f"/api/v1/reports/{report['id']}", headers=headers).status_code == 404
    assert client.get(f"/api/v1/reports/{report['id']}/pdf", headers=headers).status_code == 404
    assert client.get("/api/v1/patients/1/reports", headers=headers).status_code == 404


def test_a_missing_report_is_a_404(client, family_headers):
    assert client.get("/api/v1/reports/9999", headers=family_headers).status_code == 404


def test_an_admin_may_read_and_generate_any_report(client, admin_headers):
    report = _generate(client, admin_headers)
    assert client.get(f"/api/v1/reports/{report['id']}", headers=admin_headers).status_code == 200


def test_an_assigned_nurse_may_read_but_not_generate(client, family_headers, nurse_headers):
    report = _generate(client, family_headers)

    assert client.get(f"/api/v1/reports/{report['id']}", headers=nurse_headers).status_code == 200
    refused = client.post(
        "/api/v1/patients/1/reports/generate", json={"kind": "weekly"}, headers=nurse_headers
    )
    assert refused.status_code == 403


def test_an_unknown_kind_is_rejected(client, family_headers):
    response = client.post(
        "/api/v1/patients/1/reports/generate", json={"kind": "yearly"}, headers=family_headers
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------
# Scheduled runs — the job bodies, not the wiring
# --------------------------------------------------------------------------


def test_the_weekly_run_covers_every_active_patient(db):
    patients = db.scalars(select(Patient)).all()
    reports = report_service.run_weekly(db)

    assert len(reports) == len(patients)
    assert {r.patient_id for r in reports} == {p.id for p in patients}
    assert all(r.kind == ReportKind.WEEKLY for r in reports)


def test_the_weekly_run_is_idempotent(db):
    first = report_service.run_weekly(db)
    second = report_service.run_weekly(db)

    assert [r.id for r in first] == [r.id for r in second]
    assert len(db.scalars(select(Report).where(Report.kind == ReportKind.WEEKLY)).all()) == len(first)


def test_the_monthly_run_covers_the_previous_calendar_month(db):
    reports = report_service.run_monthly(db)

    assert reports
    for report in reports:
        assert report.kind == ReportKind.MONTHLY
        assert report.period_start.day == 1
        assert report.period_end.day == 1
        assert report.period_start < report.period_end


def test_one_failing_patient_does_not_stop_the_run(db, other_family, monkeypatch):
    """A run that abandons twenty-seven families because of one is a worse bug
    than the one it gave up on.

    `other_family` is here so the run has more than one patient — with a single
    patient this property cannot be demonstrated at all.
    """
    real = report_service.summary_service.build_for_period
    calls = {"n": 0}

    def flaky(session, patient, since, until, label, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated failure on the first patient")
        return real(session, patient, since, until, label, **kwargs)

    monkeypatch.setattr(report_service.summary_service, "build_for_period", flaky)

    patients = db.scalars(select(Patient)).all()
    assert len(patients) > 1, "this test needs a second patient to mean anything"

    reports = report_service.run_weekly(db)
    assert len(reports) == len(patients) - 1
    assert calls["n"] == len(patients), "the run continued past the failure"


@pytest.mark.parametrize("kind", list(ReportKind))
def test_period_start_is_midnight_so_regeneration_is_idempotent(kind):
    from datetime import datetime

    start, _ = report_service.period_for(kind, datetime(2026, 8, 22, 14, 37, 51))
    assert (start.hour, start.minute, start.second, start.microsecond) == (0, 0, 0, 0)


def test_a_weekly_report_includes_the_day_it_is_generated():
    """Truncating the end to midnight would drop Sunday's visit from the
    report generated on Sunday evening."""
    from datetime import datetime

    reference = datetime(2026, 8, 22, 18, 0)
    start, end = report_service.period_for(ReportKind.WEEKLY, reference)
    assert end == reference
    assert start == datetime(2026, 8, 15, 0, 0)


def test_a_monthly_report_covers_a_closed_calendar_month():
    from datetime import datetime

    start, end = report_service.period_for(ReportKind.MONTHLY, datetime(2026, 8, 22, 14, 37))
    assert (start, end) == (datetime(2026, 7, 1), datetime(2026, 8, 1))
    assert report_service.label_for(ReportKind.MONTHLY, start) == "July 2026"


def test_a_monthly_report_never_quotes_a_reading_from_outside_its_month(db):
    """The defect this period refactor exists to prevent: a document headed
    July describing an August reading."""
    from sqlalchemy import select as _select

    from app.models import Vital

    reports = report_service.run_monthly(db)
    report = reports[0]
    in_period = db.scalars(
        _select(Vital).where(
            Vital.patient_id == report.patient_id,
            Vital.recorded_at >= report.period_start,
            Vital.recorded_at < report.period_end,
        )
    ).all()

    assert report.narrative["reading_count"] == len(in_period)
    assert report.narrative["window_label"] == f"{report.period_start:%B %Y}"
    assert f"{report.period_start:%B}" in report.narrative["paragraphs"][0]


def test_the_scheduler_stays_off_under_tests():
    from app.config import settings

    assert settings.reports_scheduler_enabled is False
