"""Medication endpoints that are not scoped to a patient path."""

from fastapi import APIRouter

from ..core.dependencies import CurrentUser, DbSession, authorize_visit
from ..schemas.medication import MedicationLogOut
from ..services import medication_service

router = APIRouter(prefix="/medications", tags=["medications"])


@router.get(
    "/visit/{visit_id}/logs",
    response_model=list[MedicationLogOut],
    summary="Medication logs recorded during a visit",
)
def logs_for_visit(visit_id: int, current_user: CurrentUser, db: DbSession):
    visit = authorize_visit(db, current_user, visit_id)
    return medication_service.logs_for_visit(db, visit.id)
