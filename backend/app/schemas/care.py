"""Care manager, assignment and interaction schemas (§4.4)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models.enums import CareChannel, CareDirection, CareManagerKind


class CareManagerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    email: str | None = None
    phone: str | None = None
    kind: str
    capacity: int
    caseload: int
    available: int
    at_capacity: bool
    languages: str = ""
    active: bool = True


class CareManagerCreate(BaseModel):
    user_id: int
    kind: CareManagerKind
    languages: str = Field(default="", max_length=160)
    capacity: int | None = Field(default=None, ge=1, le=200)


class CareAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    care_manager_id: int
    care_manager_name: str | None = None
    care_manager_kind: str | None = None
    languages: str | None = None
    assigned_at: datetime
    ended_at: datetime | None = None
    ended_reason: str | None = None


class CareAssignmentCreate(BaseModel):
    """Omit the manager to let the service pick the least-loaded one of the kind
    the patient's plan grants."""

    care_manager_id: int | None = None


class CareInteractionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    care_manager_id: int | None = None
    care_manager_name: str | None = None
    channel: str
    direction: str
    subject: str
    note: str = ""
    minutes: int | None = None
    occurred_at: datetime
    visible_to_family: bool = True


class CareInteractionCreate(BaseModel):
    channel: CareChannel
    subject: str = Field(min_length=1, max_length=160)
    note: str = Field(default="", max_length=4000)
    direction: CareDirection = CareDirection.OUTBOUND
    minutes: int | None = Field(default=None, ge=1, le=600)
    visible_to_family: bool = True


class CareTeamOut(BaseModel):
    """What a family sees: who their care manager is, and what the plan grants."""

    patient_id: int
    entitled_kind: str | None = None
    assignment: CareAssignmentOut | None = None
    interactions: list[CareInteractionOut] = []
