"""Plan and subscription schemas.

Every money field is named `*_paise` and typed `int`. The unit is in the field
name so no client has to guess whether 3500 means rupees or paise — it means
₹35.00, and `350000` means ₹3,500.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..models.enums import BillingCycle


class PlanOut(BaseModel):
    id: int
    code: str
    name: str
    audience: str
    tagline: str
    monthly_paise: int
    annual_paise: int | None = None
    recommended: bool = False
    unit_label: str | None = None
    unit_included: int | None = None
    unit_paise: int | None = None
    unit_period: str | None = None
    entitlements: dict[str, Any] = {}


class QuotaOut(BaseModel):
    quota: str
    label: str
    period: str
    #: `null` means unlimited, for both the allowance and what is left of it.
    limit: int | None = None
    used: int
    remaining: int | None = None
    unlimited: bool
    period_start: datetime
    period_end: datetime


class SubscriptionOut(BaseModel):
    id: int
    status: str
    billing_cycle: str
    seats: int
    started_at: datetime
    current_period_start: datetime
    current_period_end: datetime
    renews_at: datetime | None = None
    paid_months: int
    cancel_at_period_end: bool
    cancelled_at: datetime | None = None
    owner_label: str
    family_user_id: int | None = None
    organization_id: int | None = None
    period_price_paise: int
    credit_balance_paise: int
    months_to_loyalty_reward: int
    plan: PlanOut
    quotas: list[QuotaOut] = []


class ChangePlanRequest(BaseModel):
    plan_code: str = Field(..., max_length=40, examples=["premium"])
    billing_cycle: BillingCycle | None = None


class CancelRequest(BaseModel):
    #: Families cancel at the end of the period they have paid for. Only an
    #: admin may end a subscription mid-period.
    immediate: bool = False
    reason: str | None = Field(default=None, max_length=300)
