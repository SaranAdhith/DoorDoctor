"""Family health reports — generation, listing and PDF rendering (§4.1).

A report is the plain-language summary, frozen and given a period. It reuses
`summary_service` rather than describing the same data a second way, so the
document a family keeps says exactly what the dashboard said on the day it was
generated.

The PDF is rendered from the frozen narrative on every fetch, with WeasyPrint
and the same `app/templates/<kind>/` convention `billing_service` established
for invoices. There is no second templating engine and no blob column.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import now
from ..models import (
    NotificationType,
    Patient,
    PatientStatus,
    Report,
    ReportKind,
)
from . import notification_service, summary_service

logger = logging.getLogger("doordoctor.reports")

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "reports"

TITLE_FOR_KIND: dict[ReportKind, str] = {
    ReportKind.WEEKLY: "Weekly care report",
    ReportKind.MONTHLY: "Monthly care report",
    ReportKind.ON_DEMAND: "Care report",
}


# --------------------------------------------------------------------------
# Periods
# --------------------------------------------------------------------------


def _midnight(moment: datetime) -> datetime:
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


def period_for(kind: ReportKind, reference: datetime | None = None) -> tuple[datetime, datetime]:
    """The period a report of this kind covers.

    **`period_start` is always midnight**, which is what lets two runs on the
    same day produce the same row and makes the unique constraint able to do its
    job. `period_end` is not: a weekly report generated on Sunday evening must
    include Sunday's visit, and truncating the end to midnight would silently
    drop the most recent day of care from the document.

    A monthly report covers a **closed calendar month**, so both of its bounds
    land on the 1st.
    """
    reference = reference or now()
    if kind == ReportKind.MONTHLY:
        first_of_this_month = _midnight(reference).replace(day=1)
        start = (first_of_this_month - timedelta(days=1)).replace(day=1)
        return start, first_of_this_month
    return _midnight(reference) - timedelta(days=7), reference


def label_for(kind: ReportKind, period_start: datetime) -> str:
    """How the narrative refers to its own period, in the reader's words."""
    if kind == ReportKind.MONTHLY:
        return f"{period_start:%B %Y}"
    return "the last 7 days"


# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------


def generate(
    db: Session,
    patient: Patient,
    kind: ReportKind = ReportKind.ON_DEMAND,
    reference: datetime | None = None,
    *,
    notify: bool = True,
) -> Report:
    """Generate (or refresh) one report and freeze its narrative.

    Re-generating an existing period **refreshes that row** rather than adding a
    duplicate: the scheduler can run twice without producing two Sunday reports,
    and the demo's "Generate report" button stays honest on the fifth press.
    """
    period_start, period_end = period_for(kind, reference)

    # Built over the report's *own* period, not a rolling window — otherwise a
    # report headed "July" quotes an August reading.
    #
    # Deliberately unassisted: a document a family keeps should not read
    # differently depending on whether an API key happened to be set when the
    # scheduler fired.
    narrative = summary_service.build_for_period(
        db, patient, period_start, period_end, label_for(kind, period_start)
    )

    report = db.scalar(
        select(Report).where(
            Report.patient_id == patient.id,
            Report.kind == kind,
            Report.period_start == period_start,
        )
    )
    created = report is None
    if report is None:
        report = Report(patient_id=patient.id, kind=kind, period_start=period_start)
        db.add(report)

    report.period_end = period_end
    report.title = TITLE_FOR_KIND[kind]
    report.headline = narrative["headline"][:400]
    report.narrative = narrative
    report.generated_at = now()

    db.flush()

    if created and notify:
        notification_service.create_notification(
            db,
            user_id=patient.family_user_id,
            patient_id=patient.id,
            type_=NotificationType.SYSTEM,
            title=f"{report.title} for {patient.name}",
            message=narrative["headline"],
        )

    db.commit()
    db.refresh(report)
    return report


def list_for_patient(db: Session, patient_id: int, limit: int = 24) -> list[Report]:
    return list(
        db.scalars(
            select(Report)
            .where(Report.patient_id == patient_id)
            .order_by(Report.generated_at.desc())
            .limit(limit)
        )
    )


def serialize(report: Report) -> dict[str, Any]:
    narrative = report.narrative
    return {
        "id": report.id,
        "patient_id": report.patient_id,
        "patient_name": narrative.get("patient_name"),
        "kind": report.kind.value,
        "title": report.title,
        "period_start": report.period_start,
        "period_end": report.period_end,
        "headline": report.headline,
        "paragraphs": narrative.get("paragraphs", []),
        "highlights": narrative.get("highlights", []),
        "what_happens_next": narrative.get("what_happens_next", []),
        "reading_count": narrative.get("reading_count", 0),
        "dose_count": narrative.get("dose_count", 0),
        "visit_count": narrative.get("visit_count", 0),
        "generated_at": report.generated_at,
    }


# --------------------------------------------------------------------------
# Scheduled runs
# --------------------------------------------------------------------------


def _active_patients(db: Session) -> list[Patient]:
    return list(
        db.scalars(
            select(Patient)
            .options(selectinload(Patient.family_user))
            .where(Patient.status == PatientStatus.ACTIVE)
            .order_by(Patient.id)
        )
    )


def run_for_all(
    db: Session, kind: ReportKind, reference: datetime | None = None
) -> list[Report]:
    """Generate one report of `kind` for every active patient.

    Idempotent by construction — `generate` refreshes rather than duplicates —
    so a scheduler that fires twice, or a machine that wakes from sleep past the
    trigger, costs a re-render and nothing else.
    """
    reports: list[Report] = []
    for patient in _active_patients(db):
        try:
            reports.append(generate(db, patient, kind, reference))
        except Exception:  # pragma: no cover - one bad patient must not stop the run
            logger.exception("Report generation failed for patient %d", patient.id)
            db.rollback()
    logger.info("Generated %d %s report(s)", len(reports), kind.value)
    return reports


def run_weekly(db: Session, reference: datetime | None = None) -> list[Report]:
    return run_for_all(db, ReportKind.WEEKLY, reference)


def run_monthly(db: Session, reference: datetime | None = None) -> list[Report]:
    return run_for_all(db, ReportKind.MONTHLY, reference)


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------


def render_pdf(report: Report) -> bytes:
    """Render the **frozen** narrative, not a fresh one.

    This is what makes a report a record. Re-reading last month's PDF must not
    quietly re-run the generator against today's data.
    """
    from weasyprint import HTML  # imported lazily — it pulls in cairo/pango

    return HTML(string=_render_html(report), base_url=str(TEMPLATE_DIR)).write_pdf()


TONE_LABELS = {"good": "Going well", "watch": "Keep an eye on", "attention": "With the care team"}


def _render_html(report: Report) -> str:
    from string import Template

    narrative = report.narrative
    template = Template((TEMPLATE_DIR / "report.html").read_text(encoding="utf-8"))

    paragraphs = "".join(f"<p>{_escape(p)}</p>" for p in narrative.get("paragraphs", []))
    highlights = "".join(
        f'<li class="chip {_escape(h.get("tone", "good"))}">'
        f'<span class="chip-label">{_escape(TONE_LABELS.get(h.get("tone"), ""))}</span>'
        f'<span class="chip-text">{_escape(h.get("text", ""))}</span></li>'
        for h in narrative.get("highlights", [])
    )
    next_steps = "".join(f"<li>{_escape(s)}</li>" for s in narrative.get("what_happens_next", []))

    return template.safe_substitute(
        title=_escape(report.title),
        patient_name=_escape(narrative.get("patient_name", "")),
        period=f"{_day(report.period_start)} — {_day(report.period_end)}",
        generated_at=_day(report.generated_at),
        headline=_escape(report.headline),
        paragraphs=paragraphs,
        highlights=highlights,
        next_steps=next_steps,
        reading_count=narrative.get("reading_count", 0),
        visit_count=narrative.get("visit_count", 0),
        dose_count=narrative.get("dose_count", 0),
        disclaimer=_escape(narrative.get("disclaimer", "")),
    )


def _day(value: Any) -> str:
    """Frozen datetimes come back from JSON as ISO strings."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:  # pragma: no cover - defensive
            return value
    return f"{value.day} {value:%B %Y}"


def _escape(value: Any) -> str:
    from html import escape

    return escape(str(value))
