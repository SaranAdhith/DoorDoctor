"""Plans, subscriptions and metered quota usage.

`Plan.entitlements` is a JSON document rather than a column per feature. Phase 9
reads it for care-manager ratios, telemedicine limits and lab panels; keeping it
as data means a new tier is a row, and a new entitlement is a key in
`core/pricing.py` — neither is a migration or a service change.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, now
from .enums import BillingCycle, PlanAudience, SubscriptionStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .billing import Invoice
    from .organization import Organization
    from .referral import Credit
    from .user import User


class Plan(Base):
    """A sellable plan. Rows are generated from `core/pricing.py`, never typed by hand."""

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    audience: Mapped[PlanAudience] = mapped_column(
        SAEnum(PlanAudience, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    tagline: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    monthly_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    # Null where no annual price was recorded — corporate and institutional.
    annual_paise: Mapped[Optional[int]] = mapped_column(Integer)
    recommended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_label: Mapped[Optional[str]] = mapped_column(String(20))
    unit_included: Mapped[Optional[int]] = mapped_column(Integer)
    unit_paise: Mapped[Optional[int]] = mapped_column(Integer)
    unit_period: Mapped[Optional[str]] = mapped_column(String(10))
    entitlements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now, nullable=False)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="plan")

    def price_paise(self, cycle: BillingCycle) -> Optional[int]:
        return self.annual_paise if cycle == BillingCycle.ANNUAL else self.monthly_paise


class Subscription(Base):
    """One paying relationship: a family, or an organization — never both.

    The `CheckConstraint` is the point. A subscription with neither owner is
    unbillable and a subscription with both is ambiguous about who to charge;
    the database refuses both rather than trusting every future call site.
    """

    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint(
            "(family_user_id IS NOT NULL AND organization_id IS NULL) "
            "OR (family_user_id IS NULL AND organization_id IS NOT NULL)",
            name="ck_subscription_single_owner",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), index=True, nullable=False)
    family_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus, values_callable=lambda e: [m.value for m in e]),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
    )
    billing_cycle: Mapped[BillingCycle] = mapped_column(
        SAEnum(BillingCycle, values_callable=lambda e: [m.value for m in e]),
        default=BillingCycle.MONTHLY,
        nullable=False,
    )
    seats: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
    current_period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    # Counts periods actually invoiced and paid — the input to the loyalty reward.
    paid_months: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # Minted on first read of the referrals screen, so a subscriber always has one.
    referral_code: Mapped[Optional[str]] = mapped_column(String(20), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now, nullable=False)

    plan: Mapped["Plan"] = relationship(back_populates="subscriptions")
    family_user: Mapped[Optional["User"]] = relationship()
    organization: Mapped[Optional["Organization"]] = relationship(back_populates="subscriptions")
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )
    credits: Mapped[list["Credit"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )
    usage: Mapped[list["QuotaUsage"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )

    @property
    def is_live(self) -> bool:
        """Still entitled to service. A cancelled-at-period-end subscription is."""
        return self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE)

    @property
    def owner_label(self) -> str:
        if self.organization is not None:
            return self.organization.name
        return self.family_user.name if self.family_user else "Unknown"


class QuotaUsage(Base):
    """Metered consumption, keyed by the period it belongs to.

    Keying on `period_start` is what makes rollover free: a new period writes new
    rows, so last period's numbers survive as history instead of being reset to
    zero by a job that has to remember to run.
    """

    __tablename__ = "quota_usage"
    __table_args__ = (
        UniqueConstraint("subscription_id", "period_start", "quota", name="uq_quota_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id"), index=True, nullable=False
    )
    # Plain string, not a database enum: the meters are defined in
    # `core/pricing.QUOTAS`, so adding one stays a one-file change.
    quota: Mapped[str] = mapped_column(String(40), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now, nullable=False)

    subscription: Mapped["Subscription"] = relationship(back_populates="usage")
