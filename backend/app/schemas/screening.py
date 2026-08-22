"""PHQ-2 screening schemas (§4.7)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScreeningAnswerOption(BaseModel):
    value: int
    label: str


class ScreeningInstrumentOut(BaseModel):
    code: str
    name: str
    preamble: str
    questions: list[str]
    answers: list[ScreeningAnswerOption]
    max_total: int
    positive_cutoff: int
    cadence_days: int
    disclaimer: str


class ScreeningAnswerOut(BaseModel):
    question: str
    value: int


class ScreeningOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    instrument: str
    # Both answers travel, paired with the question each belongs to. A client
    # that only receives the total cannot show what was actually asked.
    answers: list[ScreeningAnswerOut] = []
    score: int
    max_score: int
    positive: bool
    administered_by: int
    administered_by_name: str | None = None
    visit_id: int | None = None
    administered_at: datetime
    note: str | None = None


class ScreeningCreate(BaseModel):
    """Answers are validated against the instrument in `screening_service`,
    which owns the scale. Bounds here are a first cheap gate, not the rule."""

    answers: list[int] = Field(min_length=1, max_length=10)
    visit_id: int | None = None
    note: str | None = Field(default=None, max_length=2000)


class ScreeningStatusOut(BaseModel):
    patient_id: int
    due: bool
    cadence_days: int
    latest: ScreeningOut | None = None
