"""Family health reports (§4.1)."""

from typing import Any

from fastapi import APIRouter, Response, status

from ..core.dependencies import CurrentUser, DbSession, authorize_patient, authorize_report
from ..core.exceptions import ForbiddenError
from ..models import ReportKind, UserRole
from ..schemas.report import ReportGenerateRequest, ReportOut
from ..services import report_service

router = APIRouter(tags=["reports"])


@router.get(
    "/patients/{patient_id}/reports",
    response_model=list[ReportOut],
    summary="Reports generated for a patient",
)
def list_reports(patient_id: int, current_user: CurrentUser, db: DbSession) -> list[dict[str, Any]]:
    patient = authorize_patient(db, current_user, patient_id)
    return [report_service.serialize(r) for r in report_service.list_for_patient(db, patient.id)]


@router.post(
    "/patients/{patient_id}/reports/generate",
    response_model=ReportOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a report now (family or admin)",
)
def generate_report(
    patient_id: int,
    payload: ReportGenerateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """On-demand generation, so a demo does not have to wait for Sunday evening.

    Re-generating a period that already has a report **refreshes** it rather
    than adding a duplicate, which is the same rule the scheduler relies on.
    """
    if current_user.role not in (UserRole.FAMILY, UserRole.ADMIN):
        raise ForbiddenError("Only a family member or admin can generate a report.")
    patient = authorize_patient(db, current_user, patient_id)
    report = report_service.generate(db, patient, ReportKind(payload.kind))
    return report_service.serialize(report)


@router.get("/reports/{report_id}", response_model=ReportOut, summary="One report")
def get_report(report_id: int, current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    return report_service.serialize(authorize_report(db, current_user, report_id))


@router.get(
    "/reports/{report_id}/pdf",
    summary="Report as a PDF",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "The rendered report"}},
)
def report_pdf(report_id: int, current_user: CurrentUser, db: DbSession) -> Response:
    """Behind the same authorization as the JSON.

    Which is why the frontend fetches it with the bearer token and turns the
    response into a blob — a bare `<a href>` would arrive unauthenticated, the
    same reason `openInvoicePdf` exists.
    """
    report = authorize_report(db, current_user, report_id)
    pdf = report_service.render_pdf(report)
    filename = f"DoorDoctor-{report.kind.value}-{report.period_end:%Y-%m-%d}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
