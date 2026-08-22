"""Corporate and institutional accounts.

A company buying elder care for its employees and a retirement home buying it
for its residents differ only in what a "unit" is. Both hang a normal
`Subscription` off this row, so billing has one code path rather than three.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import OrganizationType

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .subscription import Subscription


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    org_type: Mapped[OrganizationType] = mapped_column(
        SAEnum(OrganizationType, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    # Employees for a corporate account, residents for an institution.
    seats: Mapped[int] = mapped_column(default=1, nullable=False)
    contact_name: Mapped[Optional[str]] = mapped_column(String(120))
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(30))
    city: Mapped[Optional[str]] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now, nullable=False)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="organization")

    @property
    def seat_label(self) -> str:
        return "resident" if self.org_type == OrganizationType.INSTITUTION else "employee"
