"""Senior Safety Score endpoints (§4.5).

Read access follows `authorize_patient` exactly, so someone else's patient is a
404 here for the same reason it is everywhere else. Recalculation is admin-only:
it writes a row, can raise an alert, and is not something a family member should
be able to trigger repeatedly.
"""

from typing import Any

from fastapi import APIRouter, Query

from ..core.dependencies import AdminUser, CurrentUser, DbSession, authorize_patient
from ..models import SafetyScore
from ..schemas.safety import SafetyHistoryPoint, SafetyRecalculate, SafetyScoreOut
from ..services import safety_score

router = APIRouter(prefix="/patients", tags=["safety"])


def _live_payload(db, patient) -> dict[str, Any]:
    """The score as it stands right now, with the stored trend attached.

    Computed live rather than read back, so a family opening the page after a
    visit sees the visit reflected. The stored row supplies `previous_score` and
    `delta`, which only exist once there is history to compare against.
    """
    payload = safety_score.compute(db, patient)
    stored = safety_score.latest(db, patient.id)
    if stored is not None:
        payload["previous_score"] = stored.previous_score
        payload["delta"] = stored.delta
    return payload


@router.get(
    "/{patient_id}/safety-score",
    response_model=SafetyScoreOut,
    summary="Senior Safety Score with its full breakdown",
)
def get_safety_score(patient_id: int, current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    patient = authorize_patient(db, current_user, patient_id)
    return _live_payload(db, patient)


@router.get(
    "/{patient_id}/safety-score/history",
    response_model=list[SafetyHistoryPoint],
    summary="Stored safety scores, oldest first",
)
def get_safety_history(
    patient_id: int,
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=24, ge=1, le=180),
) -> list[SafetyScore]:
    patient = authorize_patient(db, current_user, patient_id)
    return safety_score.history(db, patient.id, limit=limit)


@router.post(
    "/{patient_id}/safety-score/recalculate",
    response_model=SafetyScoreOut,
    summary="Recalculate and store a safety score (admin)",
)
def recalculate_safety_score(
    patient_id: int,
    current_user: AdminUser,
    db: DbSession,
    payload: SafetyRecalculate | None = None,
) -> dict[str, Any]:
    patient = authorize_patient(db, current_user, patient_id)
    window = payload.window_days if payload is not None else None
    row = safety_score.record(db, patient, window_days=window)
    db.commit()

    if row is None:
        # Nothing was stored, so report the live calculation and the reason.
        return safety_score.compute(db, patient, window_days=window)
    stored = safety_score.serialize(row)
    stored["available"] = True
    stored["unavailable_reason"] = None
    return stored
