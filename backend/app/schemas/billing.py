"""Invoice and revenue schemas."""

from datetime import datetime

from pydantic import BaseModel


class InvoiceLineOut(BaseModel):
    id: int
    description: str
    kind: str
    quantity: int
    unit_paise: int
    amount_paise: int


class AppliedCreditOut(BaseModel):
    id: int
    kind: str
    reason: str
    amount_paise: int


class InvoiceOut(BaseModel):
    id: int
    number: str
    subscription_id: int
    plan_name: str
    billed_to: str
    period_start: datetime
    period_end: datetime
    issued_at: datetime
    due_at: datetime
    subtotal_paise: int
    credit_paise: int
    total_paise: int
    status: str
    paid_at: datetime | None = None
    payment_reference: str | None = None
    lines: list[InvoiceLineOut] = []
    credits: list[AppliedCreditOut] = []


class PlanRevenueOut(BaseModel):
    plan: str
    subscribers: int
    mrr_paise: int


class RevenueSummaryOut(BaseModel):
    """Recognised revenue is paid invoices only; MRR normalises annual to a month."""

    mrr_paise: int
    arr_paise: int
    active_subscriptions: int
    cancelled_subscriptions: int
    pending_cancellations: int
    collected_all_time_paise: int
    collected_this_month_paise: int
    outstanding_paise: int
    overdue_paise: int
    credits_outstanding_paise: int
    arpu_paise: int
    by_plan: list[PlanRevenueOut] = []
