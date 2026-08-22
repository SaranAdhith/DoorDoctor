"""Follow-up task endpoints (§4.2, §4.7, §4.8, §4.9).

**Admin and nurse only, deliberately.** A task is the care team's work, not the
family's news — the family reads the alert the finding raised. `require_roles`
is used directly here rather than one of the pre-built dependencies, because
this is the only surface in the codebase whose audience is "staff, but not
families".
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from ..core.dependencies import DbSession, require_roles
from ..models import TaskStatus, User, UserRole
from ..schemas.task import TaskComplete, TaskOut, TaskSummaryOut
from ..services import task_service

StaffUser = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.NURSE))]

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskOut], summary="Follow-up tasks (admin or nurse)")
def list_tasks(
    current_user: StaffUser,
    db: DbSession,
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    patient_id: int | None = Query(default=None),
) -> list[dict[str, Any]]:
    tasks = task_service.list_tasks(db, current_user, status=task_status, patient_id=patient_id)
    return [task_service.serialize(t) for t in tasks]


@router.get("/summary", response_model=TaskSummaryOut, summary="Open and overdue counts")
def task_summary(current_user: StaffUser, db: DbSession) -> dict[str, Any]:
    return task_service.summary(db, current_user)


@router.post("/{task_id}/complete", response_model=TaskOut, summary="Close a task")
def complete_task(
    task_id: int, current_user: StaffUser, db: DbSession, payload: TaskComplete | None = None
) -> dict[str, Any]:
    task = task_service.get_for_user(db, current_user, task_id)
    note = payload.note if payload is not None else None
    task_service.complete(db, task, current_user, note=note)
    db.commit()
    db.refresh(task)
    return task_service.serialize(task)


@router.post("/{task_id}/cancel", response_model=TaskOut, summary="Cancel a task")
def cancel_task(
    task_id: int, current_user: StaffUser, db: DbSession, payload: TaskComplete | None = None
) -> dict[str, Any]:
    task = task_service.get_for_user(db, current_user, task_id)
    note = payload.note if payload is not None else None
    task_service.cancel(db, task, current_user, note=note)
    db.commit()
    db.refresh(task)
    return task_service.serialize(task)
