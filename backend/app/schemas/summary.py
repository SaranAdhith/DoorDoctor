"""Plain-language summary schemas (§2.2)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SummaryHighlight(BaseModel):
    """One chip. `tone` drives colour, so it is a closed set, not free text."""

    tone: Literal["good", "watch", "attention"]
    text: str


class PlainSummaryOut(BaseModel):
    patient_id: int
    patient_name: str
    window: str
    window_label: str
    headline: str
    paragraphs: list[str]
    highlights: list[SummaryHighlight]
    what_happens_next: list[str]
    reading_count: int
    dose_count: int
    visit_count: int
    flagged_count: int
    open_alert_count: int
    generated_at: datetime
    source: Literal["deterministic", "assisted"]
    """Honest provenance. `deterministic` is the normal case and not a degraded one."""
    disclaimer: str
