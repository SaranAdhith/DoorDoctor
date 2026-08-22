"""Device registration and wearable ingest schemas (§4.8).

Every cap here has a matching constant in `core/clinical.py`. The schema is the
cheap first gate; the service owns the rule.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..core import clinical
from ..models.enums import DeviceKind, VitalMetric


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    kind: str
    label: str
    serial: str
    status: str
    online: bool
    last_seen_at: datetime | None = None
    registered_at: datetime


class DeviceRegistered(DeviceOut):
    """The **only** response that ever carries the plaintext key.

    It cannot be recovered afterwards, only rotated — which is what makes the
    stored sha256 worth anything.
    """

    api_key: str


class DeviceCreate(BaseModel):
    kind: DeviceKind
    label: str = Field(min_length=1, max_length=120)
    serial: str = Field(min_length=1, max_length=80)


class DeviceReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    metric: str
    label: str
    value: float
    recorded_at: datetime
    triggered: bool


class ReadingIn(BaseModel):
    """One measurement from a device.

    `value` is bounded so a malformed sensor cannot write an absurd number into
    a clinical record. The bounds are deliberately wide — this is a sanity gate,
    not a clinical range; the clinical rules live in `core/clinical.py`.
    """

    metric: VitalMetric
    value: float = Field(ge=-100, le=1000)
    recorded_at: datetime | None = None


class IngestIn(BaseModel):
    readings: list[ReadingIn] = Field(min_length=1, max_length=clinical.WEARABLE_MAX_BATCH)


class IngestAccepted(BaseModel):
    """Counts only.

    A device is told what happened to its own batch and **nothing about the
    patient**. A stolen device key must not become a health-record reader.
    """

    accepted: int
    skipped: int
    triggered: int
    actions: list[str] = []
