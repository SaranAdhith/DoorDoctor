"""Generated family health reports (§4.1)."""

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import ReportKind

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .patient import Patient


class Report(Base):
    """One report per patient per kind per period.

    The narrative is **frozen** at generation time and the PDF is re-rendered
    from that snapshot on every fetch — exactly as an invoice is re-rendered
    from stored totals. Phase 4's rule applies unchanged: an issued document is
    a historical record. A report from six weeks ago must still say what it said
    six weeks ago, even though the readings behind it have moved on. Freezing
    the narrative rather than storing a blob achieves that without putting
    megabytes of PDF in the database.
    """

    __tablename__ = "reports"
    __table_args__ = (
        # Belt and braces, as with invoices: the scheduler running twice must not
        # produce two Sunday reports. `report_service.generate` also looks before
        # it inserts, so the collision is handled politely rather than as an
        # IntegrityError.
        UniqueConstraint("patient_id", "kind", "period_start", name="uq_report_patient_kind_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    kind: Mapped[ReportKind] = mapped_column(
        SAEnum(ReportKind, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    headline: Mapped[str] = mapped_column(String(400), nullable=False)
    narrative_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="reports")

    @property
    def narrative(self) -> dict[str, Any]:
        try:
            return json.loads(self.narrative_json or "{}")
        except json.JSONDecodeError:  # pragma: no cover - defensive
            return {}

    @narrative.setter
    def narrative(self, value: dict[str, Any]) -> None:
        # `default=str` so the frozen snapshot keeps its datetimes verbatim
        # rather than failing to serialise them.
        self.narrative_json = json.dumps(value, default=str)
