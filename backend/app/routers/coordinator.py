"""Coordinator operational endpoints."""

from typing import Any

from fastapi import APIRouter

from ..core.dependencies import CoordinatorUser, DbSession
from ..schemas.coordinator import CoordinatorSummary
from ..services import coordinator_service

router = APIRouter(tags=["coordinator"])


@router.get("/coordinator/summary", response_model=CoordinatorSummary, summary="Operational counts")
def summary(db: DbSession, current_user: CoordinatorUser) -> dict[str, int]:
    return coordinator_service.summary(db)


@router.get("/caregivers", response_model=list[dict], summary="Caregiver directory (coordinator)")
def caregivers(db: DbSession, current_user: CoordinatorUser) -> list[dict[str, Any]]:
    return coordinator_service.list_caregivers(db)
