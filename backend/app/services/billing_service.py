"""Invoice generation, payment and PDF rendering (§3).

Two properties matter more than anything else here:

1. **Generation is idempotent per period.** Re-running the generator must never
   bill a family twice. There is a unique constraint on
   `(subscription_id, period_start)` *and* a lookup before insert — the check
   catches it politely, the constraint catches it when the check is bypassed.
2. **An issued invoice is a historical record.** Totals are stored, not derived,
   so an invoice from last March still says what it said last March after the
   price list moves.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..core import pricing
from ..core.exceptions import BadRequestError, ConflictError, NotFoundError
from ..database import now
from ..models import (
    BillingCycle,
    Credit,
    Invoice,
    InvoiceLine,
    InvoiceLineKind,
    InvoiceStatus,
    Referral,
    ReferralStatus,
    Subscription,
    SubscriptionStatus,
    User,
    UserRole,
)
from . import payment_gateway, referral_service, subscription_service

logger = logging.getLogger("doordoctor.billing")

PAYMENT_TERMS_DAYS = 7
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "invoices"


# --------------------------------------------------------------------------
# Numbering
# --------------------------------------------------------------------------


def next_invoice_number(db: Session, issued_at: datetime) -> str:
    """`DD-YYYY-NNNNNN`, sequential within the year.

    Derived from the highest existing number in that year rather than a row
    count, so voiding an invoice cannot cause the next one to reuse a number.
    """
    prefix = f"DD-{issued_at.year}-"
    highest = db.scalar(
        select(func.max(Invoice.number)).where(Invoice.number.like(f"{prefix}%"))
    )
    sequence = 1
    if highest:
        try:
            sequence = int(highest.rsplit("-", 1)[1]) + 1
        except (IndexError, ValueError):  # pragma: no cover - defensive
            sequence = 1
    return f"{prefix}{sequence:06d}"


# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------


def find_invoice_for_period(
    db: Session, subscription: Subscription, period_start: datetime
) -> Optional[Invoice]:
    return db.scalar(
        select(Invoice).where(
            Invoice.subscription_id == subscription.id,
            Invoice.period_start == period_start,
        )
    )


def generate_invoice(
    db: Session,
    subscription: Subscription,
    *,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    issued_at: datetime | None = None,
    status: InvoiceStatus = InvoiceStatus.ISSUED,
    apply_credits: bool = True,
) -> Invoice:
    """Invoice one billing period. Returns the existing invoice if there is one."""
    start = period_start or subscription.current_period_start
    end = period_end or subscription.current_period_end

    existing = find_invoice_for_period(db, subscription, start)
    if existing is not None:
        return existing

    issued = issued_at or start
    plan = subscription.plan
    cycle = subscription.billing_cycle

    invoice = Invoice(
        number=next_invoice_number(db, issued),
        subscription_id=subscription.id,
        period_start=start,
        period_end=end,
        issued_at=issued,
        due_at=issued + timedelta(days=PAYMENT_TERMS_DAYS),
        status=status,
    )
    db.add(invoice)
    db.flush()

    unit = subscription_service.price_paise(plan, cycle, seats=1)
    quantity = subscription.seats if plan.unit_label == "employee" else 1
    period_label = "year" if cycle == BillingCycle.ANNUAL else "month"
    description = f"{plan.name} — 1 {period_label}"
    if quantity > 1:
        description = f"{plan.name} — {quantity} {plan.unit_label}s, 1 {period_label}"

    db.add(
        InvoiceLine(
            invoice_id=invoice.id,
            description=description,
            kind=InvoiceLineKind.SUBSCRIPTION,
            quantity=quantity,
            unit_paise=unit,
            amount_paise=unit * quantity,
        )
    )
    db.flush()

    subtotal = int(
        db.scalar(
            select(func.coalesce(func.sum(InvoiceLine.amount_paise), 0)).where(
                InvoiceLine.invoice_id == invoice.id
            )
        )
        or 0
    )
    credit_total = _apply_credits(db, invoice, subscription, subtotal) if apply_credits else 0

    invoice.subtotal_paise = subtotal
    invoice.credit_paise = credit_total
    invoice.total_paise = max(0, subtotal - credit_total)
    db.flush()

    logger.info(
        "Invoice %s issued for subscription %s: subtotal=%s credits=%s total=%s",
        invoice.number,
        subscription.id,
        subtotal,
        credit_total,
        invoice.total_paise,
    )
    return invoice


def charge_addon(
    db: Session,
    subscription: Subscription,
    *,
    addon_code: str,
    quantity: int = 1,
    description: str | None = None,
    as_of: datetime | None = None,
) -> InvoiceLine:
    """Bill an incidental purchase — Phase 4's deferred add-on flow.

    An add-on is **not a billing period**, so it gets its own invoice issued at
    the moment of purchase rather than waiting for the next cycle. A family who
    orders a ₹499 lab panel on the 3rd should not find the charge on an invoice
    dated the 1st.

    `period_start == period_end == the purchase moment` keeps the schema's
    `(subscription_id, period_start)` uniqueness meaningful: two add-ons bought
    in the same request land on **one** invoice rather than colliding, which is
    also the behaviour a customer would expect. Credits apply exactly as they do
    to a subscription invoice — `_apply_credits` is reused, so the "a credit is
    never split" rule holds here too without being restated.
    """
    spec = pricing.ADD_ONS_BY_CODE.get(addon_code)
    if spec is None:
        raise BadRequestError(f"Unknown add-on '{addon_code}'.")

    moment = as_of or now()
    invoice = find_invoice_for_period(db, subscription, moment)
    if invoice is None:
        invoice = Invoice(
            number=next_invoice_number(db, moment),
            subscription_id=subscription.id,
            period_start=moment,
            period_end=moment,
            issued_at=moment,
            due_at=moment + timedelta(days=PAYMENT_TERMS_DAYS),
            status=InvoiceStatus.ISSUED,
        )
        db.add(invoice)
        db.flush()

    line = InvoiceLine(
        invoice_id=invoice.id,
        description=description or f"{spec.name} ({spec.unit})",
        kind=InvoiceLineKind.ADDON,
        quantity=max(1, quantity),
        unit_paise=spec.price_paise,
        amount_paise=spec.price_paise * max(1, quantity),
    )
    db.add(line)
    db.flush()

    _retotal(db, invoice, subscription)
    logger.info(
        "Add-on %s x%s billed on invoice %s (subscription %s)",
        addon_code,
        quantity,
        invoice.number,
        subscription.id,
    )
    return line


def _retotal(db: Session, invoice: Invoice, subscription: Subscription) -> Invoice:
    """Recompute an invoice from its lines.

    Credits already spent on this invoice are left alone — re-running
    `_apply_credits` would double-count them — so only the shortfall created by
    a newly added line is covered.
    """
    subtotal = int(
        db.scalar(
            select(func.coalesce(func.sum(InvoiceLine.amount_paise), 0)).where(
                InvoiceLine.invoice_id == invoice.id
            )
        )
        or 0
    )
    already = invoice.credit_paise or 0
    extra = _apply_credits(db, invoice, subscription, max(0, subtotal - already))
    invoice.subtotal_paise = subtotal
    invoice.credit_paise = already + extra
    invoice.total_paise = max(0, subtotal - invoice.credit_paise)
    db.flush()
    return invoice


def _apply_credits(db: Session, invoice: Invoice, subscription: Subscription, subtotal: int) -> int:
    """Spend unused credits against this invoice, oldest first.

    A credit is never split and never spent past the invoice total — a credit
    worth more than the bill stays whole and waits for the next one, which keeps
    the arithmetic explainable to a customer looking at both.
    """
    applied = 0
    for credit in subscription_service.unspent_credits(db, subscription):
        if applied >= subtotal:
            break
        if credit.amount_paise > subtotal - applied:
            continue
        credit.applied_invoice_id = invoice.id
        credit.applied_at = now()
        applied += credit.amount_paise
    db.flush()
    return applied


def generate_due_invoices(
    db: Session, *, as_of: datetime | None = None, dry_run: bool = False
) -> list[dict[str, Any]]:
    """Invoice every live subscription whose period has closed.

    Rolls each subscription forward first, invoicing every period it passes
    through, so a subscription that was missed for two months produces two
    invoices rather than one that silently swallows a month of revenue.

    **A dry run does the real work and then rolls it back**, rather than walking
    a separate "what would happen" branch. A preview computed by a second code
    path is a second implementation, and the one thing a dry run must never do
    is disagree with the real run it is previewing.

    Returns plain summaries rather than ORM objects, because after a dry run's
    rollback those objects no longer refer to anything.
    """
    moment = as_of or now()
    created: list[Invoice] = []

    try:
        subscriptions = db.scalars(
            select(Subscription)
            .options(selectinload(Subscription.plan))
            .where(
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE])
            )
            .order_by(Subscription.id)
        ).all()

        for subscription in subscriptions:
            guard = 0
            while subscription.is_live and subscription.current_period_end <= moment:
                guard += 1
                if guard > 120:  # pragma: no cover - runaway guard
                    logger.error("Invoice catch-up ran away on subscription %s", subscription.id)
                    break

                period_start = subscription.current_period_start
                period_end = subscription.current_period_end
                if find_invoice_for_period(db, subscription, period_start) is None:
                    created.append(
                        generate_invoice(
                            db,
                            subscription,
                            period_start=period_start,
                            period_end=period_end,
                            issued_at=period_start,
                        )
                    )

                if subscription.cancel_at_period_end:
                    subscription.status = SubscriptionStatus.CANCELLED
                    subscription.cancelled_at = period_end
                    break

                subscription.current_period_start = period_end
                subscription.current_period_end = subscription_service.period_end_for(
                    period_end, subscription.billing_cycle
                )
                db.flush()

            # The period the subscription is in now, if it has not been billed yet.
            if (
                subscription.is_live
                and find_invoice_for_period(db, subscription, subscription.current_period_start)
                is None
                and subscription.current_period_start <= moment
            ):
                created.append(generate_invoice(db, subscription))

        # Read the summaries out while the objects are still live.
        summaries = [_summarise(invoice) for invoice in created]
    except Exception:
        db.rollback()
        raise

    if dry_run:
        db.rollback()
    else:
        db.commit()
    return summaries


def _summarise(invoice: Invoice) -> dict[str, Any]:
    subscription = invoice.subscription
    return {
        "number": invoice.number,
        "billed_to": subscription.owner_label if subscription else "-",
        "period_start": invoice.period_start,
        "period_end": invoice.period_end,
        "total_paise": invoice.total_paise,
    }


# --------------------------------------------------------------------------
# Payment
# --------------------------------------------------------------------------


def mark_paid(db: Session, invoice: Invoice, *, reference: str | None = None) -> Invoice:
    """Settle an invoice through the payment boundary and count the paid period."""
    if invoice.status == InvoiceStatus.PAID:
        raise ConflictError("This invoice has already been paid.")
    if invoice.status == InvoiceStatus.VOID:
        raise BadRequestError("A voided invoice cannot be paid.")

    if reference is None and invoice.total_paise > 0:
        result = payment_gateway.charge(
            amount_paise=invoice.total_paise, description=f"DoorDoctor invoice {invoice.number}"
        )
        if not result.succeeded:  # pragma: no cover - simulated gateway always succeeds
            raise BadRequestError("The payment could not be completed. Please try again.")
        invoice.payment_reference = result.reference
        invoice.payment_status = result.status
    else:
        invoice.payment_reference = reference or "CREDIT"
        invoice.payment_status = None

    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = now()

    subscription_service.record_paid_period(db, invoice.subscription)
    _reward_referrer_if_converted(db, invoice)
    db.flush()
    return invoice


def _reward_referrer_if_converted(db: Session, invoice: Invoice) -> None:
    """Pay whoever referred this family, once the family actually pays.

    Rewarding on signup instead would let anyone farm credits by creating
    accounts that never produce a rupee. `reward_referrer` is idempotent — it
    moves the referral to `rewarded`, so a second paid invoice pays nothing.
    """
    subscription = invoice.subscription
    if subscription is None or subscription.family_user_id is None:
        return

    referral = db.scalar(
        select(Referral).where(
            Referral.referred_user_id == subscription.family_user_id,
            Referral.status == ReferralStatus.JOINED,
        )
    )
    if referral is not None:
        referral_service.reward_referrer(db, referral)


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def _loaded(query):
    return query.options(
        selectinload(Invoice.lines),
        selectinload(Invoice.subscription).selectinload(Subscription.plan),
        selectinload(Invoice.subscription).selectinload(Subscription.family_user),
        selectinload(Invoice.subscription).selectinload(Subscription.organization),
    )


def get_invoice(db: Session, invoice_id: int) -> Invoice:
    invoice = db.scalar(_loaded(select(Invoice)).where(Invoice.id == invoice_id))
    if invoice is None:
        raise NotFoundError("Invoice not found.")
    return invoice


def list_invoices(db: Session, *, subscription_id: int | None = None) -> list[Invoice]:
    query = _loaded(select(Invoice)).order_by(Invoice.issued_at.desc(), Invoice.id.desc())
    if subscription_id is not None:
        query = query.where(Invoice.subscription_id == subscription_id)
    return list(db.scalars(query).all())


def invoices_for_user(db: Session, user: User) -> list[Invoice]:
    """A family sees only their own invoices; an admin sees every invoice."""
    if user.role == UserRole.ADMIN:
        return list_invoices(db)
    subscription = subscription_service.for_user(db, user)
    if subscription is None:
        return []
    return list_invoices(db, subscription_id=subscription.id)


def serialize(db: Session, invoice: Invoice) -> dict[str, Any]:
    credits = db.scalars(
        select(Credit).where(Credit.applied_invoice_id == invoice.id).order_by(Credit.id)
    ).all()
    subscription = invoice.subscription
    return {
        "id": invoice.id,
        "number": invoice.number,
        "subscription_id": invoice.subscription_id,
        "plan_name": subscription.plan.name if subscription and subscription.plan else "",
        "billed_to": subscription.owner_label if subscription else "",
        "period_start": invoice.period_start,
        "period_end": invoice.period_end,
        "issued_at": invoice.issued_at,
        "due_at": invoice.due_at,
        "subtotal_paise": invoice.subtotal_paise,
        "credit_paise": invoice.credit_paise,
        "total_paise": invoice.total_paise,
        "status": invoice.status.value,
        "paid_at": invoice.paid_at,
        "payment_reference": invoice.payment_reference,
        "lines": [
            {
                "id": line.id,
                "description": line.description,
                "kind": line.kind.value,
                "quantity": line.quantity,
                "unit_paise": line.unit_paise,
                "amount_paise": line.amount_paise,
            }
            for line in invoice.lines
        ],
        "credits": [
            {"id": c.id, "kind": c.kind.value, "reason": c.reason, "amount_paise": c.amount_paise}
            for c in credits
        ],
    }


# --------------------------------------------------------------------------
# Revenue (admin)
# --------------------------------------------------------------------------


def revenue_summary(db: Session, *, as_of: datetime | None = None) -> dict[str, Any]:
    """What the business is earning. Recognised revenue is *paid* invoices only.

    MRR is normalised to a month — an annual subscription contributes a twelfth
    of its price, not its whole price in the month it renewed.
    """
    moment = as_of or now()
    month_start = moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    live = db.scalars(
        select(Subscription)
        .options(selectinload(Subscription.plan))
        .where(Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE]))
    ).all()

    mrr = 0
    by_plan: dict[str, dict[str, Any]] = {}
    for subscription in live:
        period_price = subscription_service.price_paise(
            subscription.plan, subscription.billing_cycle, subscription.seats
        )
        monthly = (
            period_price // 12 if subscription.billing_cycle == BillingCycle.ANNUAL else period_price
        )
        mrr += monthly
        bucket = by_plan.setdefault(
            subscription.plan.code,
            {"plan": subscription.plan.name, "subscribers": 0, "mrr_paise": 0},
        )
        bucket["subscribers"] += 1
        bucket["mrr_paise"] += monthly

    def _sum(*conditions) -> int:
        return int(
            db.scalar(select(func.coalesce(func.sum(Invoice.total_paise), 0)).where(*conditions)) or 0
        )

    collected_all_time = _sum(Invoice.status == InvoiceStatus.PAID)
    collected_this_month = _sum(Invoice.status == InvoiceStatus.PAID, Invoice.paid_at >= month_start)
    outstanding = _sum(Invoice.status == InvoiceStatus.ISSUED)
    overdue = _sum(Invoice.status == InvoiceStatus.ISSUED, Invoice.due_at < moment)

    cancelled = int(
        db.scalar(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatus.CANCELLED
            )
        )
        or 0
    )
    pending_cancellation = int(
        db.scalar(
            select(func.count(Subscription.id)).where(
                Subscription.cancel_at_period_end.is_(True),
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
        )
        or 0
    )
    credits_outstanding = int(
        db.scalar(
            select(func.coalesce(func.sum(Credit.amount_paise), 0)).where(
                Credit.applied_invoice_id.is_(None)
            )
        )
        or 0
    )

    return {
        "mrr_paise": mrr,
        "arr_paise": mrr * 12,
        "active_subscriptions": len(live),
        "cancelled_subscriptions": cancelled,
        "pending_cancellations": pending_cancellation,
        "collected_all_time_paise": collected_all_time,
        "collected_this_month_paise": collected_this_month,
        "outstanding_paise": outstanding,
        "overdue_paise": overdue,
        "credits_outstanding_paise": credits_outstanding,
        "arpu_paise": mrr // len(live) if live else 0,
        "by_plan": sorted(by_plan.values(), key=lambda row: row["mrr_paise"], reverse=True),
    }


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------


def render_pdf(db: Session, invoice: Invoice) -> bytes:
    """Render an invoice to PDF with WeasyPrint.

    Pulled forward from Phase 6 so `/invoices/{id}/pdf` is a real document rather
    than a placeholder Phase 6 would have to replace. Phase 6's report renderer
    reuses the same dependency and the same template directory convention.
    """
    from weasyprint import HTML  # imported lazily — it pulls in cairo/pango

    html = _render_invoice_html(db, invoice)
    return HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf()


def _render_invoice_html(db: Session, invoice: Invoice) -> str:
    from string import Template

    data = serialize(db, invoice)
    template = Template((TEMPLATE_DIR / "invoice.html").read_text(encoding="utf-8"))

    lines = "".join(
        "<tr>"
        f"<td>{_escape(line['description'])}</td>"
        f"<td class='num'>{line['quantity']}</td>"
        f"<td class='num'>{format_inr(line['unit_paise'])}</td>"
        f"<td class='num'>{format_inr(line['amount_paise'])}</td>"
        "</tr>"
        for line in data["lines"]
    )
    credits = "".join(
        "<tr class='credit'>"
        f"<td colspan='3'>{_escape(credit['reason'])}</td>"
        f"<td class='num'>−{format_inr(credit['amount_paise'])}</td>"
        "</tr>"
        for credit in data["credits"]
    )

    status = data["status"]
    return template.safe_substitute(
        number=_escape(data["number"]),
        billed_to=_escape(data["billed_to"]),
        plan_name=_escape(data["plan_name"]),
        issued_at=data["issued_at"].strftime("%d %b %Y"),
        due_at=data["due_at"].strftime("%d %b %Y"),
        period=f"{data['period_start'].strftime('%d %b %Y')} — {data['period_end'].strftime('%d %b %Y')}",
        lines=lines,
        credits=credits,
        subtotal=format_inr(data["subtotal_paise"]),
        credit_total=format_inr(data["credit_paise"]),
        total=format_inr(data["total_paise"]),
        status=_escape(status.upper()),
        status_class=status,
        paid_note=(
            f"Paid on {data['paid_at'].strftime('%d %b %Y')} · reference {_escape(data['payment_reference'] or '')}"
            if status == "paid" and data["paid_at"]
            else f"Payable by {data['due_at'].strftime('%d %b %Y')}"
        ),
    )


def _escape(value: str) -> str:
    from html import escape

    return escape(str(value))


def format_inr(paise: int) -> str:
    """Indian digit grouping: ₹1,23,456 rather than ₹123,456.

    The frontend has its own copy in `lib/money.ts` for the same reason the
    password rule is mirrored — the PDF is rendered server-side and cannot ask
    the browser to format it.
    """
    rupees, remainder = divmod(abs(int(paise)), pricing.PAISE_PER_RUPEE)
    digits = str(rupees)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        digits = ",".join(parts) + "," + tail
    sign = "-" if paise < 0 else ""
    if remainder:
        return f"{sign}₹{digits}.{remainder:02d}"
    return f"{sign}₹{digits}"
