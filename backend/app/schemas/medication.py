"""Medication schedule and administration-log schemas."""

from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..models.enums import MedicationChangeKind, MedicationLogStatus, PillOrganiserStatus


class MedicationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    dosage: str = Field(..., min_length=1, max_length=60)
    frequency: str = Field(default="daily", max_length=60)
    scheduled_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$", examples=["08:00"])
    active: bool = True


class MedicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    name: str
    dosage: str
    frequency: str
    scheduled_time: str
    active: bool


class MedicationLogCreate(BaseModel):
    medication_id: int
    status: MedicationLogStatus
    reason: str | None = None

    @model_validator(mode="after")
    def _reason_required_when_not_administered(self) -> Self:
        if self.status in (MedicationLogStatus.SKIPPED, MedicationLogStatus.REFUSED):
            if not self.reason or not self.reason.strip():
                raise ValueError("A reason is required when a dose is skipped or refused.")
        return self


class MedicationLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    medication_id: int
    visit_id: int | None = None
    status: MedicationLogStatus
    reason: str | None = None
    recorded_at: datetime
    photo: "AttachmentOut | None" = None


class MedicationUpdate(BaseModel):
    """Every field optional; only what changes is written to the history."""

    dosage: str | None = Field(default=None, min_length=1, max_length=60)
    frequency: str | None = Field(default=None, min_length=1, max_length=60)
    scheduled_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    active: bool | None = None
    reason: str | None = Field(default=None, max_length=500)


class MedicationChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    medication_id: int
    medication_name: str | None = None
    kind: MedicationChangeKind
    previous_value: str | None = None
    new_value: str | None = None
    reason: str | None = None
    changed_by_name: str
    changed_at: datetime


class PillOrganiserFillCreate(BaseModel):
    compartments_filled: int = Field(ge=0, le=64)
    visit_id: int | None = None
    note: str | None = Field(default=None, max_length=255)


class PillOrganiserFillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    visit_id: int | None = None
    filled_by_name: str
    status: PillOrganiserStatus
    compartments_filled: int
    compartments_total: int
    covers_until: date | None = None
    note: str | None = None
    charged: bool
    filled_at: datetime


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    content_type: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    created_at: datetime
    url: str


MedicationLogOut.model_rebuild()
