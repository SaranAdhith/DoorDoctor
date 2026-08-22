"""Lab orders and results (§4.2).

RECORDED: a blood panel costs ₹499, and an abnormal result raises an alert plus
a 24-hour follow-up task. Panel contents and reference ranges are `ASSUMED` and
live in `core/clinical.py`.

**Each result stores the reference range it was compared against.** A flag of
"high" with no range beside it is a diagnosis by implication; with the range
stored, it is arithmetic the reader can re-run — and it stays re-runnable after
someone edits `core/clinical.py`, which is the whole point of copying it here.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import LabBilling, LabFlag, LabOrderStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .patient import Patient
    from .user import User


class LabOrder(Base):
    __tablename__ = "lab_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    # The panel code from `core.clinical.LAB_PANELS`. A plain string, not a
    # database enum, so adding a panel stays a one-file change in clinical.py.
    panel_code: Mapped[str] = mapped_column(String(40), nullable=False)
    panel_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[LabOrderStatus] = mapped_column(
        SAEnum(LabOrderStatus, values_callable=lambda e: [m.value for m in e]),
        default=LabOrderStatus.ORDERED,
        index=True,
        nullable=False,
    )
    # How it was paid for: the plan's allowance, or a ₹499 add-on. Recorded on
    # the order so a line on an invoice can be traced back to a clinical event.
    billing: Mapped[LabBilling] = mapped_column(
        SAEnum(LabBilling, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    price_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invoice_line_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoice_lines.id"))
    ordered_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    ordered_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)
    collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    reported_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    patient: Mapped["Patient"] = relationship(back_populates="lab_orders")
    ordered_by_user: Mapped["User"] = relationship(foreign_keys=[ordered_by])
    results: Mapped[list["LabResult"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="LabResult.id"
    )

    @property
    def abnormal_results(self) -> list["LabResult"]:
        return [r for r in self.results if LabFlag(r.flag).is_abnormal]


class LabResult(Base):
    __tablename__ = "lab_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("lab_orders.id"), index=True, nullable=False)
    analyte_code: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    # Copied from `core.clinical` at result time, deliberately. A range that
    # moves later must not silently re-flag a result somebody already read.
    ref_low: Mapped[Optional[float]] = mapped_column(Float)
    ref_high: Mapped[Optional[float]] = mapped_column(Float)
    flag: Mapped[LabFlag] = mapped_column(
        SAEnum(LabFlag, values_callable=lambda e: [m.value for m in e]),
        default=LabFlag.UNKNOWN,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)

    order: Mapped["LabOrder"] = relationship(back_populates="results")
