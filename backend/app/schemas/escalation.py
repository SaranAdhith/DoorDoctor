"""Escalation, timeline and hospital coordination schemas (§4.3, §4.9)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models.enums import HospitalBookingStatus


class EscalationStepOut(BaseModel):
    """One contact attempt.

    Steps sharing a `sequence` happened at the same moment. That is what lets
    the UI draw a fan-out rather than implying a queue worked one at a time.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    sequence: int
    actor: str
    channel: str
    target: str
    recipient_user_id: int | None = None
    status: str
    detail: str
    occurred_at: datetime


class EscalationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    patient_name: str | None = None
    trigger: str
    trigger_id: int | None = None
    alert_id: int | None = None
    severity: str
    status: str
    summary: str
    detail: str
    opened_at: datetime
    sla_minutes: int
    sla_due_at: datetime
    breached_sla: bool
    acknowledged_by: int | None = None
    acknowledged_at: datetime | None = None
    resolved_by: int | None = None
    resolved_at: datetime | None = None
    resolution_note: str | None = None
    # The recorded 108 -> nurse -> admin ladder, served rather than restated in
    # the client so the assistant, the emergency block and this agree.
    ladder: list[str] = []
    steps: list[EscalationStepOut] = []


class EscalationResolve(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class EscalationStepCreate(BaseModel):
    channel: str = Field(min_length=1, max_length=30)
    target: str = Field(min_length=1, max_length=160)
    detail: str = Field(min_length=1, max_length=2000)


class HospitalBookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    patient_name: str | None = None
    hospital_name: str
    department: str | None = None
    reason: str
    ambulance_required: bool
    preferred_at: datetime | None = None
    status: str
    requested_by: int
    requested_at: datetime
    sla_minutes: int
    sla_due_at: datetime
    breached_sla: bool
    confirmed_at: datetime | None = None
    confirmation_detail: str | None = None
    handled_by: int | None = None
    escalation_event_id: int | None = None
    notes: str | None = None


class HospitalBookingCreate(BaseModel):
    hospital_name: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=2000)
    department: str | None = Field(default=None, max_length=120)
    ambulance_required: bool = False
    preferred_at: datetime | None = None


class HospitalBookingUpdate(BaseModel):
    status: HospitalBookingStatus | None = None
    confirmation_detail: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)


class EmergencyBlockOut(BaseModel):
    """The permanent "call 108" block, served so eight screens cannot drift."""

    number: str
    title: str
    body: str
    ladder: list[str]
