"""Care circle schemas (§4.13)."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models.enums import CareCircleRole


def _plausible_email(value: str | None) -> str | None:
    """The same shape check `schemas/lead.py` applies, and no more.

    `EmailStr` would mean adding `email-validator`, and nothing else in this
    codebase validates an address harder than this. A circle form that rejects a
    real but unusual address stops a family adding the person who has the spare
    key, which is a worse outcome than storing an address nobody replies to.
    """
    if value is None:
        return None
    address = value.strip().lower()
    if not address:
        return None
    if "@" not in address or address.startswith("@") or address.endswith("@"):
        raise ValueError("Enter a valid email address.")
    return address


class CareCircleMemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    relationship_label: str = Field(default="Family", max_length=60)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    role: CareCircleRole = CareCircleRole.VIEWER
    receives_alerts: bool = False
    receives_reports: bool = False
    note: str | None = Field(default=None, max_length=255)

    _email = field_validator("email")(classmethod(lambda cls, v: _plausible_email(v)))


class CareCircleMemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    relationship_label: str | None = Field(default=None, max_length=60)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    role: CareCircleRole | None = None
    receives_alerts: bool | None = None
    receives_reports: bool | None = None
    note: str | None = Field(default=None, max_length=255)

    _email = field_validator("email")(classmethod(lambda cls, v: _plausible_email(v)))


class CareCircleMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    user_id: int | None = None
    name: str
    relationship_label: str
    phone: str | None = None
    email: str | None = None
    role: CareCircleRole
    is_primary: bool
    receives_alerts: bool
    receives_reports: bool
    has_login: bool
    note: str | None = None
