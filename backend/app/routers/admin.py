"""Admin operational endpoints."""

from typing import Any

from fastapi import APIRouter

from ..core.dependencies import AdminUser, DbSession
from ..schemas.admin import AdminSummary
from ..schemas.billing import RevenueSummaryOut
from ..services import admin_service, billing_service

router = APIRouter(tags=["admin"])


@router.get("/admin/summary", response_model=AdminSummary, summary="Operational counts")
def summary(db: DbSession, current_user: AdminUser) -> dict[str, int]:
    return admin_service.summary(db)


@router.get("/admin/revenue", response_model=RevenueSummaryOut, summary="Revenue and MRR")
def revenue(db: DbSession, current_user: AdminUser) -> dict[str, Any]:
    """Money in, money owed, and what recurs.

    Recognised revenue counts paid invoices only — an issued invoice is a claim,
    not income, and a dashboard that conflates them flatters the business.
    """
    return billing_service.revenue_summary(db)
