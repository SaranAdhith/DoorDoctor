"""Public enquiry schemas (§2.6).

Every string here is capped. `POST /leads` is the only unauthenticated write in
the codebase, so the schema is the first line of defence and not a formality —
the same reasoning `schemas/assistant.py` records for `MAX_QUESTION_CHARS`, with
the difference that this endpoint has no login in front of it at all.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from ..models.enums import LeadKind, LeadStatus

MAX_NAME_CHARS = 120
MAX_EMAIL_CHARS = 255
MAX_PHONE_CHARS = 32
MAX_CITY_CHARS = 80
MAX_MESSAGE_CHARS = 2_000
MAX_SOURCE_CHARS = 120
MAX_NOTE_CHARS = 2_000

HONEYPOT_FIELD = "company_website"
"""The field a bot fills and a person never sees.

Named like something a form might plausibly ask a business for, because a
honeypot called `honeypot` is not one. The real form renders it hidden, with
`autocomplete="off"` and `tabIndex={-1}`, and never writes to it.
"""


class LeadCreate(BaseModel):
    """An enquiry from the public site.

    `model_config` is deliberately left at Pydantic's default (ignore unknown
    fields) rather than `extra="forbid"`: a scraper posting junk keys should get
    the same bland 200 as everyone else, not a validation error that tells it
    which keys are real.
    """

    name: str = Field(min_length=1, max_length=MAX_NAME_CHARS)
    email: str = Field(min_length=3, max_length=MAX_EMAIL_CHARS)
    phone: Optional[str] = Field(default=None, max_length=MAX_PHONE_CHARS)
    city: Optional[str] = Field(default=None, max_length=MAX_CITY_CHARS)
    kind: LeadKind = LeadKind.FAMILY
    message: Optional[str] = Field(default=None, max_length=MAX_MESSAGE_CHARS)
    source_page: Optional[str] = Field(default=None, max_length=MAX_SOURCE_CHARS)

    company_website: Optional[str] = Field(default=None, max_length=MAX_SOURCE_CHARS)
    """Honeypot. Non-empty means the submission is discarded — see
    `lead_service.create`. It is capped like every other field so it cannot be
    used to post a megabyte at a route that throws the value away."""

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Please tell us your name.")
        return cleaned

    @field_validator("email")
    @classmethod
    def _plausible_email(cls, value: str) -> str:
        """The same shape check `referral_service.invite` applies, and no more.

        `EmailStr` would mean adding `email-validator`, and nothing else in this
        codebase validates an address harder than this. A marketing form that
        rejects a real but unusual address costs a customer; the address is
        confirmed by someone replying to it, not by a regex.
        """
        address = value.strip().lower()
        if "@" not in address or address.startswith("@") or address.endswith("@"):
            raise ValueError("Enter a valid email address.")
        return address

    @field_validator("phone", "city", "message", "source_page")
    @classmethod
    def _blank_to_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class LeadAccepted(BaseModel):
    """The reply to every accepted enquiry, and to every honeypot hit.

    A fixed message with no id and no echo of the submission. It never reveals
    whether this email has enquired before — the same rule
    `POST /auth/forgot-password` follows, for the same reason.
    """

    message: str


class LeadOut(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str]
    city: Optional[str]
    kind: str
    message: Optional[str]
    source_page: Optional[str]
    status: str
    admin_note: Optional[str]
    handled_by: Optional[str]
    handled_at: Optional[datetime]
    created_at: datetime


class LeadUpdate(BaseModel):
    """An admin working the queue. Both fields optional so a note can be added
    without moving the status, and vice versa."""

    status: Optional[LeadStatus] = None
    admin_note: Optional[str] = Field(default=None, max_length=MAX_NOTE_CHARS)


class LeadSummaryOut(BaseModel):
    total: int
    new: int
    contacted: int
    qualified: int
    closed: int
    by_kind: dict[str, int]
