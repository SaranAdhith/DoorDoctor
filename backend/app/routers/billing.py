"""Invoices (§3)."""

from typing import Any

from fastapi import APIRouter, Response

from ..core.dependencies import (
    AdminUser,
    DbSession,
    FamilyOrAdminUser,
    authorize_invoice,
)
from ..schemas.billing import InvoiceOut
from ..services import billing_service

router = APIRouter(tags=["billing"])


@router.get("/invoices", response_model=list[InvoiceOut], summary="Invoices for this account")
def invoices(db: DbSession, current_user: FamilyOrAdminUser) -> list[dict[str, Any]]:
    """A family sees their own invoices; an admin sees every invoice."""
    return [billing_service.serialize(db, invoice) for invoice in billing_service.invoices_for_user(db, current_user)]


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut, summary="One invoice")
def invoice(invoice_id: int, db: DbSession, current_user: FamilyOrAdminUser) -> dict[str, Any]:
    record = authorize_invoice(db, current_user, invoice_id)
    return billing_service.serialize(db, record)


@router.get(
    "/invoices/{invoice_id}/pdf",
    summary="Invoice as a PDF",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "The rendered invoice"}},
)
def invoice_pdf(invoice_id: int, db: DbSession, current_user: FamilyOrAdminUser) -> Response:
    """Rendered server-side and returned inline.

    Behind the same authorization as the JSON, which is why the frontend fetches
    it with the bearer token and turns the response into a blob — a bare
    `<a href>` would arrive unauthenticated.
    """
    record = authorize_invoice(db, current_user, invoice_id)
    pdf = billing_service.render_pdf(db, record)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="DoorDoctor-{record.number}.pdf"'},
    )


@router.post(
    "/invoices/{invoice_id}/pay",
    response_model=InvoiceOut,
    summary="Settle an invoice (admin)",
)
def pay(invoice_id: int, db: DbSession, current_user: AdminUser) -> dict[str, Any]:
    """Marks an invoice settled through the payment boundary.

    Admin-only, and deliberately so: no gateway is integrated in this build, so
    this records an out-of-band payment an admin has confirmed. It is not a
    self-service "pay now" button, because nothing here can take money.
    """
    record = authorize_invoice(db, current_user, invoice_id)
    billing_service.mark_paid(db, record)
    payload = billing_service.serialize(db, record)
    db.commit()
    return payload
