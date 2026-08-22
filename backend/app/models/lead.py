"""Enquiries from the public site (§2.6).

**This is the only table in the codebase a stranger can write to.** Every other
row is created by someone who has already authenticated. That single fact drives
the whole design:

* The write path (`POST /leads`) is rate limited per IP *and* per email, honeypot
  protected, and every string is capped in the Pydantic schema. An unbounded
  public text column is a free-text store that somebody else decides the size of.
* The read path is **admin only**. A lead list is a list of named strangers with
  their phone numbers; a family member or a nurse has no business in it, and a
  test pins both 403s.
* Creating a lead raises **no notification**. An unauthenticated endpoint wired
  to every admin's notification bell is a spam amplifier — the rate limiter caps
  the table, and it should not have to cap the bell as well.

Retention: this is contact data a person volunteered in order to be contacted, so
it is kept until it is worked. Erasure lands with Phase 10's consent record,
audit log and Privacy & Data page — the same deferral `models/assistant.py`
records, and for the same reason: deleting rows without those is a half-built
promise.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import LeadKind, LeadStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .user import User


class Lead(Base):
    """One enquiry from the marketing site."""

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Stored lowercased, like `Referral.referred_email`, so the rate limiter and
    # the duplicate-enquiry read agree on what "the same person" means.
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    city: Mapped[Optional[str]] = mapped_column(String(80))
    kind: Mapped[LeadKind] = mapped_column(
        SAEnum(LeadKind, values_callable=lambda e: [m.value for m in e]),
        default=LeadKind.FAMILY,
        index=True,
        nullable=False,
    )
    message: Mapped[Optional[str]] = mapped_column(Text)
    source_page: Mapped[Optional[str]] = mapped_column(String(120))
    """Which public page the form was submitted from. The pricing pages and the
    contact page share one form, and knowing which one converted is the whole
    reason a marketing site has more than one page."""

    status: Mapped[LeadStatus] = mapped_column(
        SAEnum(LeadStatus, values_callable=lambda e: [m.value for m in e]),
        default=LeadStatus.NEW,
        index=True,
        nullable=False,
    )
    admin_note: Mapped[Optional[str]] = mapped_column(Text)
    handled_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    handled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)

    handled_by: Mapped[Optional["User"]] = relationship()

    @property
    def is_new(self) -> bool:
        """Unworked. The count the admin nav badge and the summary tile both mean."""
        return self.status == LeadStatus.NEW
