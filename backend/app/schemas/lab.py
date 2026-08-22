"""Lab panel, order and result schemas (§4.2)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AnalyteOut(BaseModel):
    code: str
    label: str
    unit: str
    ref_low: float | None = None
    ref_high: float | None = None


class LabPanelOut(BaseModel):
    code: str
    name: str
    description: str
    turnaround_hours: int
    price_paise: int
    addon_code: str
    analytes: list[AnalyteOut] = []


class LabResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    analyte_code: str
    label: str
    value: float
    unit: str
    # The range travels with the result. A flag with no range beside it is a
    # diagnosis by implication.
    ref_low: float | None = None
    ref_high: float | None = None
    flag: str
    is_abnormal: bool
    description: str


class LabOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    patient_name: str | None = None
    panel_code: str
    panel_name: str
    status: str
    billing: str
    price_paise: int
    invoice_line_id: int | None = None
    ordered_at: datetime
    collected_at: datetime | None = None
    reported_at: datetime | None = None
    cancelled_at: datetime | None = None
    notes: str | None = None
    abnormal_count: int = 0
    results: list[LabResultOut] = []


class LabOrderCreate(BaseModel):
    panel_code: str = Field(max_length=40)
    notes: str | None = Field(default=None, max_length=500)


class LabResultsCreate(BaseModel):
    """A mapping of analyte code to value.

    Free-form keys are validated against the panel in `lab_service`, which knows
    what the panel contains — the schema would have to duplicate the catalogue
    to do it here, and then the two could disagree.
    """

    values: dict[str, float] = Field(min_length=1)
