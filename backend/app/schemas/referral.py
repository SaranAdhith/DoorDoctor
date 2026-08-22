"""Referral schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class ReferralOut(BaseModel):
    id: int
    #: Partially masked — a referral list should not harvest customer contacts.
    email: str
    status: str
    reward_paise: int
    created_at: datetime
    joined_at: datetime | None = None
    rewarded_at: datetime | None = None


class ReferralSummaryOut(BaseModel):
    code: str
    share_url: str
    reward_months: int
    reward_paise: int
    friend_credit_paise: int
    total_earned_paise: int
    joined_count: int
    pending_count: int
    referrals: list[ReferralOut] = []


class ReferralInviteRequest(BaseModel):
    email: str = Field(..., max_length=255, examples=["a-friend@example.com"])


class ReferralInviteResponse(BaseModel):
    message: str
    summary: ReferralSummaryOut
