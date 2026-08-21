"""Admin operational endpoints."""

from typing import Any

from fastapi import APIRouter

from ..core.dependencies import AdminUser, DbSession
from ..schemas.admin import AdminSummary
from ..services import admin_service

router = APIRouter(tags=["admin"])


@router.get("/admin/summary", response_model=AdminSummary, summary="Operational counts")
def summary(db: DbSession, current_user: AdminUser) -> dict[str, int]:
    return admin_service.summary(db)


@router.get("/nurses", response_model=list[dict], summary="Nurse directory (admin)")
def nurses(db: DbSession, current_user: AdminUser) -> list[dict[str, Any]]:
    return admin_service.list_nurses(db)
