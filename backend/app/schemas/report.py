"""Report schemas (§4.1)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .summary import SummaryHighlight


class ReportGenerateRequest(BaseModel):
    """On-demand generation. `kind` exists so a demo can produce either document."""

    kind: Literal["weekly", "monthly", "on_demand"] = "on_demand"


class ReportOut(BaseModel):
    id: int
    patient_id: int
    patient_name: str | None = None
    kind: str
    title: str
    period_start: datetime
    period_end: datetime
    headline: str
    paragraphs: list[str] = []
    highlights: list[SummaryHighlight] = []
    what_happens_next: list[str] = []
    reading_count: int = 0
    dose_count: int = 0
    visit_count: int = 0
    generated_at: datetime
