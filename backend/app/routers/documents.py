"""Uploaded medical documents (Phase 12, Layer 1a).

Every route here is new; no existing route changed shape. The bytes of an
uploaded document are served by the existing `/attachments/{id}` route, behind
the same `authorize_patient` check as every other file.

Uploads answer **202 Accepted**: the file is stored and queued, and its text is
read in the background (`app.intelligence.documents.worker`).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from ..config import settings
from ..core.dependencies import AdminUser, CurrentUser, DbSession, authorize_patient
from ..core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from ..core.intelligence import DOCUMENT_MAX_BYTES
from ..intelligence.documents import access, intake, service
from ..models import DocumentStatus, DocumentType


def _documents_enabled() -> None:
    if not settings.documents_enabled:
        raise NotFoundError("Not found.")


router = APIRouter(tags=["documents"], dependencies=[Depends(_documents_enabled)])


async def _read_capped(file: UploadFile) -> bytes:
    """Read with an explicit cap, never trusting the declared size — the same
    rule as the dose-photo upload."""
    data = await file.read(DOCUMENT_MAX_BYTES + 1)
    if len(data) > DOCUMENT_MAX_BYTES:
        raise BadRequestError(f"Documents must be under {DOCUMENT_MAX_BYTES // (1024 * 1024)} MB.")
    return data


def _doc_type(value: str | None) -> DocumentType:
    if not value:
        return DocumentType.UNKNOWN
    try:
        return DocumentType(value)
    except ValueError:
        allowed = ", ".join(t.value for t in DocumentType)
        raise BadRequestError(f"Document type must be one of: {allowed}.") from None


@router.post(
    "/patients/{patient_id}/documents",
    response_model=dict,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a medical document (family, admin)",
)
async def upload_for_patient(
    patient_id: int,
    db: DbSession,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    doc_type: str | None = Form(default=None),
) -> dict[str, Any]:
    patient = access.authorize_upload_for_patient(db, current_user, patient_id)
    kind = _doc_type(doc_type)
    data = await _read_capped(file)
    document = intake.upload(
        db,
        patient=patient,
        data=data,
        uploader=current_user,
        title=title,
        filename=file.filename,
        doc_type=kind,
    )
    return service.serialize(document, current_user)


@router.post(
    "/visits/{visit_id}/documents",
    response_model=dict,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Add a document during a visit (nurse, visit in progress)",
)
async def upload_during_visit(
    visit_id: int,
    db: DbSession,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    doc_type: str | None = Form(default=None),
) -> dict[str, Any]:
    visit, _ = access.authorize_nurse_upload(db, current_user, visit_id)
    kind = _doc_type(doc_type)
    data = await _read_capped(file)
    document = intake.upload(
        db,
        patient=visit.patient,
        data=data,
        uploader=current_user,
        title=title,
        filename=file.filename,
        doc_type=kind,
        visit=visit,
    )
    return service.serialize(document, current_user)


@router.get(
    "/patients/{patient_id}/documents",
    response_model=list[dict],
    summary="Documents for a patient",
)
def list_for_patient(patient_id: int, db: DbSession, current_user: CurrentUser) -> list[dict[str, Any]]:
    authorize_patient(db, current_user, patient_id)
    return [service.serialize(d, current_user) for d in service.list_for_patient(db, current_user, patient_id)]


@router.get("/documents/{document_id}", response_model=dict, summary="One document")
def get_document(document_id: int, db: DbSession, current_user: CurrentUser) -> dict[str, Any]:
    document = access.authorize_document(db, current_user, document_id)
    return service.serialize_with_pages(document, current_user)


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Remove a document (admin; family uploader before verification)",
)
def delete_document(document_id: int, db: DbSession, current_user: CurrentUser) -> Response:
    document = access.authorize_document(db, current_user, document_id)
    if not access.can_delete(current_user, document):
        raise ForbiddenError("Only an admin, or the person who uploaded it before it was checked, can remove a document.")
    service.remove(db, document, actor=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/documents/{document_id}/reprocess",
    response_model=dict,
    summary="Read a document again (admin)",
)
def reprocess(document_id: int, db: DbSession, current_user: AdminUser) -> dict[str, Any]:
    document = access.authorize_document(db, current_user, document_id)
    return service.serialize(service.reprocess(db, document), current_user)


@router.get("/admin/documents", response_model=list[dict], summary="All documents (admin)")
def admin_list(
    db: DbSession,
    current_user: AdminUser,
    status_filter: DocumentStatus | None = Query(default=None, alias="status"),
) -> list[dict[str, Any]]:
    return [service.serialize(d, current_user) for d in service.list_for_admin(db, status=status_filter)]
