"""Follow-up tasks — the work an automated finding creates for a human.

RECORDED: an abnormal lab result raises an alert **and a 24-hour follow-up
task**. That is the only recorded task rule; the screening, wearable and
escalation tasks that reuse this module take their due windows from
`core/clinical.py` marked `ASSUMED`.

**A task is not an alert and the difference is deliberate.** An alert tells a
family something about their relative. A task tells the care team to do
something. Merging them would either spam families with internal work items or
hide clinical findings inside an ops queue. So tasks are **admin and nurse
only** — a family reads the alert, not the ticket it opened.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..core.exceptions import BadRequestError, NotFoundError
from ..database import now
from ..models import (
    FollowUpTask,
    Nurse,
    Patient,
    TaskKind,
    TaskStatus,
    User,
    UserRole,
    Visit,
)

logger = logging.getLogger("doordoctor.tasks")


def create(
    db: Session,
    *,
    patient: Patient,
    kind: TaskKind,
    title: str,
    detail: str = "",
    due_in_hours: int,
    source_type: str | None = None,
    source_id: int | None = None,
    assigned_user_id: int | None = None,
    as_of: datetime | None = None,
) -> FollowUpTask:
    """Open a task. `due_in_hours` always comes from `core/clinical.py`."""
    moment = as_of or now()
    task = FollowUpTask(
        patient_id=patient.id,
        kind=kind,
        title=title,
        detail=detail,
        due_at=moment + timedelta(hours=due_in_hours),
        status=TaskStatus.OPEN,
        source_type=source_type,
        source_id=source_id,
        assigned_user_id=assigned_user_id,
        created_at=moment,
    )
    db.add(task)
    db.flush()
    logger.info(
        "Follow-up task %s opened for patient %s (kind=%s, due in %sh)",
        task.id,
        patient.id,
        kind.value,
        due_in_hours,
    )
    return task


def open_for_source(
    db: Session, source_type: str, source_id: int
) -> FollowUpTask | None:
    """The open task a given finding already created, if any.

    Regenerating a lab result or re-running a wearable batch must not open a
    second ticket for the same finding — a queue that grows a row every time a
    job re-runs stops being a queue anyone works.
    """
    return db.scalar(
        select(FollowUpTask).where(
            FollowUpTask.source_type == source_type,
            FollowUpTask.source_id == source_id,
            FollowUpTask.status == TaskStatus.OPEN,
        )
    )


def _assigned_nurse_user_id(db: Session, patient: Patient) -> int | None:
    """The user behind the nurse who most recently saw this patient.

    Best effort: a task with no assignee still lands in the admin queue, which is
    better than refusing to create it because nobody has been rostered yet.
    """
    row = db.scalar(
        select(Nurse.user_id)
        .join(Visit, Visit.nurse_id == Nurse.id)
        .where(Visit.patient_id == patient.id, Visit.nurse_id.is_not(None))
        .order_by(Visit.scheduled_at.desc())
        .limit(1)
    )
    return int(row) if row is not None else None


def assign_to_patients_nurse(db: Session, patient: Patient) -> int | None:
    return _assigned_nurse_user_id(db, patient)


def list_tasks(
    db: Session,
    user: User,
    *,
    status: TaskStatus | None = None,
    patient_id: int | None = None,
    limit: int = 200,
) -> list[FollowUpTask]:
    """Tasks this user may work.

    Admins see everything. A nurse sees the tasks assigned to them — not every
    task for every patient they have ever visited, which would make the queue
    unworkable and would show them findings for patients they no longer cover.
    """
    query = select(FollowUpTask).options(selectinload(FollowUpTask.patient))

    if user.role == UserRole.NURSE:
        query = query.where(FollowUpTask.assigned_user_id == user.id)
    elif user.role != UserRole.ADMIN:  # pragma: no cover - router guards this
        raise NotFoundError("Task not found.")

    if status is not None:
        query = query.where(FollowUpTask.status == status)
    if patient_id is not None:
        query = query.where(FollowUpTask.patient_id == patient_id)

    return list(
        db.scalars(
            query.order_by(FollowUpTask.status, FollowUpTask.due_at, FollowUpTask.id).limit(limit)
        )
    )


def get_for_user(db: Session, user: User, task_id: int) -> FollowUpTask:
    task = db.get(FollowUpTask, task_id)
    if task is None:
        raise NotFoundError("Task not found.")
    if user.role == UserRole.ADMIN:
        return task
    if user.role == UserRole.NURSE and task.assigned_user_id == user.id:
        return task
    raise NotFoundError("Task not found.")


def complete(db: Session, task: FollowUpTask, user: User, note: str | None = None) -> FollowUpTask:
    if task.status != TaskStatus.OPEN:
        raise BadRequestError("This task is already closed.")
    task.status = TaskStatus.DONE
    task.completed_by = user.id
    task.completed_at = now()
    if note is not None:
        task.completion_note = note.strip() or None
    db.flush()
    return task


def cancel(db: Session, task: FollowUpTask, user: User, note: str | None = None) -> FollowUpTask:
    if task.status != TaskStatus.OPEN:
        raise BadRequestError("This task is already closed.")
    task.status = TaskStatus.CANCELLED
    task.completed_by = user.id
    task.completed_at = now()
    if note is not None:
        task.completion_note = note.strip() or None
    db.flush()
    return task


def summary(db: Session, user: User) -> dict[str, Any]:
    """Counts for the ops header. Overdue is the number anyone actually acts on."""
    tasks = list_tasks(db, user, status=TaskStatus.OPEN)
    return {
        "open": len(tasks),
        "overdue": sum(1 for t in tasks if t.is_overdue),
    }


def serialize(task: FollowUpTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "patient_id": task.patient_id,
        "patient_name": task.patient.name if task.patient else None,
        "kind": task.kind.value,
        "title": task.title,
        "detail": task.detail,
        "due_at": task.due_at,
        "status": task.status.value,
        "is_overdue": task.is_overdue,
        "source_type": task.source_type,
        "source_id": task.source_id,
        "assigned_user_id": task.assigned_user_id,
        "assigned_user_name": task.assigned_user.name if task.assigned_user else None,
        "completed_by": task.completed_by,
        "completed_at": task.completed_at,
        "completion_note": task.completion_note,
        "created_at": task.created_at,
    }
