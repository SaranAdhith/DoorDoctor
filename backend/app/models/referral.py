"""Referrals and account credits.

A referral reward and a loyalty reward both end in the same place — money off the
next invoice — so they are one mechanism with two reasons, not two parallel
systems that billing would have to apply separately and keep in step.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import CreditKind, ReferralStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .subscription import Subscription
    from .user import User


class Referral(Base):
    """One invitation and, if it converts, the reward it earned."""

    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    referrer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    # Stored lowercased. Nullable because a code can be shared rather than emailed.
    referred_email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    referred_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[ReferralStatus] = mapped_column(
        SAEnum(ReferralStatus, values_callable=lambda e: [m.value for m in e]),
        default=ReferralStatus.PENDING,
        nullable=False,
    )
    reward_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    rewarded_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)

    referrer: Mapped["User"] = relationship(foreign_keys=[referrer_user_id])
    referred_user: Mapped[Optional["User"]] = relationship(foreign_keys=[referred_user_id])


class Credit(Base):
    """Money owed back to a subscriber, waiting to be applied to an invoice.

    `applied_invoice_id` being null is what "unspent" means — there is no separate
    boolean that could disagree with it.
    """

    __tablename__ = "billing_credits"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id"), index=True, nullable=False
    )
    kind: Mapped[CreditKind] = mapped_column(
        SAEnum(CreditKind, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    referral_id: Mapped[Optional[int]] = mapped_column(ForeignKey("referrals.id"))
    applied_invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoices.id"), index=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, nullable=False)

    subscription: Mapped["Subscription"] = relationship(back_populates="credits")

    @property
    def is_unspent(self) -> bool:
        return self.applied_invoice_id is None
