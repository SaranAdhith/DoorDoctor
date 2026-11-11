"""Request bodies for the Stage 2 review routes.

Field limits come from `core/intelligence.py`, the same numbers extraction
truncates to, so an admin's edit can never hold more than a proposal could.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ...core.intelligence import (
    FACT_LABEL_MAX,
    FACT_UNIT_MAX,
    FACT_VALUE_MAX,
    REJECTION_REASON_MAX,
)
from ...models import DocumentType, FactKind


class FactFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: FactKind | None = None
    label: str | None = Field(default=None, max_length=FACT_LABEL_MAX)
    value_text: str | None = Field(default=None, max_length=FACT_VALUE_MAX)
    value_num: float | None = None
    unit: str | None = Field(default=None, max_length=FACT_UNIT_MAX)
    ref_low: float | None = None
    ref_high: float | None = None
    observed_on: date | None = None
    page_no: int | None = Field(default=None, ge=1)

    def changes(self) -> dict:
        """Only the fields the caller actually sent — an edit of the unit must
        not blank the range."""
        return self.model_dump(exclude_unset=True)


class FactDecision(FactFields):
    action: Literal["confirm", "edit", "reject", "reopen"]


class FactCreate(FactFields):
    kind: FactKind = FactKind.OTHER
    label: str = Field(min_length=1, max_length=FACT_LABEL_MAX)


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_type: DocumentType | None = None
    document_date: date | None = None


class RejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=REJECTION_REASON_MAX)
