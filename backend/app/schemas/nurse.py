"""Nurse profile and credential schemas (§4.10).

Two output shapes, deliberately not one with optional fields. A response model
whose sensitive fields are merely `None` for families is one forgotten
`exclude_none` away from being a leak; two models cannot make that mistake.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models.enums import CredentialKind, NurseStatus


class CredentialCreate(BaseModel):
    kind: CredentialKind
    title: str = Field(min_length=2, max_length=120)
    issuing_body: str = Field(min_length=2, max_length=120)
    registration_number: str | None = Field(default=None, max_length=60)
    issued_on: date | None = None
    expires_on: date | None = None


class CredentialDecision(BaseModel):
    note: str | None = Field(default=None, max_length=255)


class NurseUpdate(BaseModel):
    status: NurseStatus | None = None
    zone: str | None = Field(default=None, max_length=60)
    languages: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=2000)
    years_experience: int | None = Field(default=None, ge=0, le=60)
    joined_on: date | None = None


class CredentialPublicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    title: str
    issuing_body: str
    verified_at: datetime | None = None
    verified_by_name: str | None = None
    expires_on: date | None = None
    expired: bool


class CredentialAdminOut(CredentialPublicOut):
    registration_number: str | None = None
    issued_on: date | None = None
    verification_status: str
    note: str | None = None


class NurseProfileOut(BaseModel):
    """What a family sees. No registration number, no email, no phone."""

    id: int
    name: str
    credential: str
    verification_status: str
    status: str
    zone: str | None = None
    joined_on: date | None = None
    years_experience: int | None = None
    languages: list[str] = []
    bio: str | None = None
    credentials: list[CredentialPublicOut] = []
    visits_to_this_patient: int
    last_visit_at: datetime | None = None


class NurseAdminOut(BaseModel):
    id: int
    user_id: int
    name: str
    email: str
    phone: str | None = None
    credential: str
    verification_status: str
    status: str
    zone: str | None = None
    joined_on: date | None = None
    years_experience: int | None = None
    languages: list[str] = []
    bio: str | None = None
    credentials: list[CredentialAdminOut] = []
    open_visits: int
    completed_visits: int
    patients_covered: int
    expiring_credentials: list[CredentialAdminOut] = []
