"""Medication schedule and administration-log schemas."""

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..models.enums import MedicationLogStatus


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
