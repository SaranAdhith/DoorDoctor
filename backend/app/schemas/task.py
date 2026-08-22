"""Follow-up task schemas (§4.2, §4.7, §4.8, §4.9)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    patient_name: str | None = None
    kind: str
    title: str
    detail: str
    due_at: datetime
    status: str
    is_overdue: bool
    source_type: str | None = None
    source_id: int | None = None
    assigned_user_id: int | None = None
    assigned_user_name: str | None = None
    completed_by: int | None = None
    completed_at: datetime | None = None
    completion_note: str | None = None
    created_at: datetime


class TaskComplete(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class TaskSummaryOut(BaseModel):
    open: int
    overdue: int
