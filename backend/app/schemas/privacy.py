"""Consent, export and erasure schemas (§4.14)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConsentDecision(BaseModel):
    kind: str = Field(min_length=1, max_length=60)
    granted: bool
    patient_id: int | None = None


class ConsentStateOut(BaseModel):
    kind: str
    label: str
    blurb: str
    required: bool
    status: str | None = None
    granted: bool
    decided_at: datetime | None = None
    decided_by_name: str | None = None
    version: str | None = None
    current_version: str
    needs_review: bool


class ConsentRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    label: str
    version: str
    status: str
    decided_at: datetime
    decided_by_name: str
    source: str


class HoldingOut(BaseModel):
    key: str
    label: str
    count: int


class AuditEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    at: datetime
    actor_label: str
    actor_role: str | None = None
    action: str
    subject_type: str
    subject_id: int | None = None
    patient_id: int | None = None
    detail: str | None = None


class RetainedOut(BaseModel):
    label: str
    reason: str


class PrivacyOverviewOut(BaseModel):
    patient_id: int
    patient_name: str
    policy_version: str
    audit_retention_days: int
    erasure_destroys: list[str]
    erasure_retains: list[RetainedOut]
    holdings: list[HoldingOut]
    consents: list[ConsentStateOut]
    consent_history: list[ConsentRecordOut]
    audit_trail: list[AuditEntryOut]
    erasure_request: dict[str, Any] | None = None


class ErasureRequestCreate(BaseModel):
    patient_id: int
    reason: str | None = Field(default=None, max_length=1000)


class ErasureDecision(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class ErasureRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    patient_name: str
    requested_by_name: str
    reason: str | None = None
    status: str
    decided_by_name: str | None = None
    decided_at: datetime | None = None
    decision_note: str | None = None
    outcome: str | None = None
    created_at: datetime
