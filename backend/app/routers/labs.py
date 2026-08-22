"""Lab panel and order endpoints (§4.2).

Ordering is a family or admin action — a nurse does not spend a family's
allowance or add ₹499 to their invoice. Recording results is admin-only: it is
the step that can raise an alert and open a task, and it stands in for a
laboratory feed that does not exist in this build.
"""

from typing import Any

from fastapi import APIRouter, status

from ..core.dependencies import (
    AdminUser,
    CurrentUser,
    DbSession,
    FamilyOrAdminUser,
    authorize_patient,
)
from ..schemas.lab import LabOrderCreate, LabOrderOut, LabPanelOut, LabResultsCreate
from ..services import lab_service

router = APIRouter(tags=["labs"])


@router.get("/lab-panels", response_model=list[LabPanelOut], summary="Published lab panels")
def list_panels(current_user: CurrentUser) -> list[dict[str, Any]]:
    """The catalogue from `core/clinical.py`, priced from `core/pricing.py`.

    Behind a login, unlike `/public/plans`: what tests DoorDoctor runs is not a
    published price list, and nothing on the marketing site quotes it.
    """
    return lab_service.list_panels()


@router.post(
    "/patients/{patient_id}/lab-orders",
    response_model=LabOrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Order a lab panel (family or admin)",
)
def order_panel(
    patient_id: int, payload: LabOrderCreate, current_user: FamilyOrAdminUser, db: DbSession
) -> dict[str, Any]:
    patient = authorize_patient(db, current_user, patient_id)
    lab_order = lab_service.order(
        db, patient=patient, user=current_user, panel_code=payload.panel_code, notes=payload.notes
    )
    db.commit()
    db.refresh(lab_order)
    return lab_service.serialize(lab_order)


@router.get(
    "/patients/{patient_id}/lab-orders",
    response_model=list[LabOrderOut],
    summary="Lab orders for a patient",
)
def list_orders(patient_id: int, current_user: CurrentUser, db: DbSession) -> list[dict[str, Any]]:
    patient = authorize_patient(db, current_user, patient_id)
    return [lab_service.serialize(o) for o in lab_service.list_for_patient(db, patient.id)]


@router.get(
    "/lab-orders/awaiting-results",
    response_model=list[LabOrderOut],
    summary="Orders still waiting on the laboratory (admin)",
)
def list_awaiting(current_user: AdminUser, db: DbSession) -> list[dict[str, Any]]:
    return [lab_service.serialize(o) for o in lab_service.list_awaiting_results(db)]


@router.get("/lab-orders/{order_id}", response_model=LabOrderOut, summary="One lab order")
def get_order(order_id: int, current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    return lab_service.serialize(lab_service.get_for_user(db, current_user, order_id))


@router.post(
    "/lab-orders/{order_id}/collect",
    response_model=LabOrderOut,
    summary="Mark a sample collected (admin)",
)
def collect_order(order_id: int, current_user: AdminUser, db: DbSession) -> dict[str, Any]:
    lab_order = lab_service.get_for_user(db, current_user, order_id)
    lab_service.mark_collected(db, lab_order)
    db.commit()
    db.refresh(lab_order)
    return lab_service.serialize(lab_order)


@router.post(
    "/lab-orders/{order_id}/results",
    response_model=LabOrderOut,
    summary="Record results (admin)",
)
def record_results(
    order_id: int, payload: LabResultsCreate, current_user: AdminUser, db: DbSession
) -> dict[str, Any]:
    """Attach results. An abnormal value raises one alert and one 24-hour task."""
    lab_order = lab_service.get_for_user(db, current_user, order_id)
    lab_service.record_results(db, lab_order, payload.values)
    db.commit()
    db.refresh(lab_order)
    return lab_service.serialize(lab_order)


@router.post(
    "/lab-orders/{order_id}/cancel",
    response_model=LabOrderOut,
    summary="Cancel an order before results (family or admin)",
)
def cancel_order(order_id: int, current_user: FamilyOrAdminUser, db: DbSession) -> dict[str, Any]:
    lab_order = lab_service.get_for_user(db, current_user, order_id)
    lab_service.cancel(db, lab_order, current_user)
    db.commit()
    db.refresh(lab_order)
    return lab_service.serialize(lab_order)
