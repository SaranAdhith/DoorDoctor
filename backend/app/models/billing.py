"""Invoices and their lines.

Every amount is integer paise. An invoice is `subtotal - credits = total`, and
each of those three is stored rather than recomputed on read, so an invoice
issued last March still says what it said last March even if the price list has
moved since.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import InvoiceLineKind, InvoiceStatus, PaymentStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .subscription import Subscription


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        # Billing the same period twice is the failure that ends a company, so it
        # is prevented in the schema and not only in the generator's logic.
        UniqueConstraint("subscription_id", "period_start", name="uq_invoice_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(24), unique=True, index=True, nullable=False)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id"), index=True, nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    subtotal_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    credit_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        SAEnum(InvoiceStatus, values_callable=lambda e: [m.value for m in e]),
        default=InvoiceStatus.ISSUED,
        nullable=False,
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # What the payment boundary handed back. Never a card number, never a token
    # that could be replayed — see `services/payment_gateway.py`.
    payment_reference: Mapped[Optional[str]] = mapped_column(String(60))
    payment_status: Mapped[Optional[PaymentStatus]] = mapped_column(
        SAEnum(PaymentStatus, values_callable=lambda e: [m.value for m in e])
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)

    subscription: Mapped["Subscription"] = relationship(back_populates="invoices")
    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceLine.id"
    )

    @property
    def is_payable(self) -> bool:
        return self.status == InvoiceStatus.ISSUED and self.total_paise > 0


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[InvoiceLineKind] = mapped_column(
        SAEnum(InvoiceLineKind, values_callable=lambda e: [m.value for m in e]),
        default=InvoiceLineKind.SUBSCRIPTION,
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    invoice: Mapped["Invoice"] = relationship(back_populates="lines")
