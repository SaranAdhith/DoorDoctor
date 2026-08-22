"""AI assistant schemas (§2.3)."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

MAX_QUESTION_CHARS = 500
"""A cap, not a UX guess. It bounds the prompt, and it stops
`assistant_messages` becoming an unbounded free-text store of PHI-adjacent
material — see the retention note in `models/assistant.py`."""


class AssistantAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    patient_id: Optional[int] = None
    """Omitted by a family member means "my relative". An admin's questions are
    org-wide and this is ignored for them."""

    @field_validator("question")
    @classmethod
    def _not_only_whitespace(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Please type a question.")
        return cleaned


class AssistantAnswerOut(BaseModel):
    id: int
    question: str
    answer: str
    intent: str
    intent_title: str
    source: Literal["deterministic", "assisted"]
    """Honest provenance. `deterministic` is the normal case and not a degraded
    one — it is what the platform ships with no API key at all."""
    is_emergency: bool
    """Drives the alert treatment in the UI. Set by a deterministic match that
    never reached a model."""
    patient_id: Optional[int]
    disclaimer: str
    suggestions: list[str]
    created_at: datetime


class AssistantMessageOut(BaseModel):
    id: int
    question: str
    answer: str
    intent: str
    intent_title: str
    source: Literal["deterministic", "assisted"]
    is_emergency: bool
    patient_id: Optional[int]
    created_at: datetime


class AssistantSuggestionOut(BaseModel):
    intent: str
    title: str
    question: str
