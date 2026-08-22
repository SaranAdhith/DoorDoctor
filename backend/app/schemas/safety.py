"""Senior Safety Score schemas (§4.5).

Every field of the breakdown is on the wire. The score is only defensible if the
components that produced it travel with it — a client that receives a bare
number has no way to explain it, and would invent an explanation.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SafetyComponentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str
    blurb: str
    weight: int
    value: float | None = None
    points: float | None = None
    detail: str
    has_data: bool


class SafetyScoreOut(BaseModel):
    """A stored calculation, or a live one that has not been stored.

    `available` is False when too little of the scale had data behind it. In that
    case `score` is null and `unavailable_reason` carries the sentence to show —
    the client must not substitute a zero.
    """

    model_config = ConfigDict(from_attributes=True)

    patient_id: int
    available: bool = True
    score: int | None = None
    band: str | None = None
    band_label: str | None = None
    band_tone: str | None = None
    band_blurb: str | None = None
    window_days: int
    covered_weight: int
    total_weight: int
    previous_score: int | None = None
    delta: int | None = None
    components: list[SafetyComponentOut] = []
    calculated_at: datetime
    unavailable_reason: str | None = None


class SafetyHistoryPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    score: int
    band: str
    calculated_at: datetime


class SafetyRecalculate(BaseModel):
    """Admins may narrow the window when reviewing. Bounded, because an
    unbounded window turns one screen into a full-table scan."""

    window_days: int | None = Field(default=None, ge=7, le=180)
