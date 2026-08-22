"""Invoices: generation, idempotency, credits, PDFs, payment and revenue."""

import pytest

from app.core import pricing
from app.models import Invoice, InvoiceStatus, Subscription
from app.services import billing_service, subscription_service
from tests.conftest import DEMO_PASSWORD, auth, login
from sqlalchemy import select


def _family_subscription(db):
    return db.scalar(
        select(Subscription)
        .where(Subscription.family_user_id.is_not(None))
        .order_by(Subscription.id)
    )


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def test_family_sees_their_own_invoice_history(client, family_headers):
    invoices = client.get("/api/v1/invoices", headers=family_headers).json()
    assert len(invoices) == 15, "fourteen settled periods plus the one in flight"
    assert all(invoice["billed_to"] == "Darren D'Souza" for invoice in invoices)

    outstanding = [i for i in invoices if i["status"] == "issued"]
    assert len(outstanding) == 1
    assert outstanding[0]["total_paise"] == pricing.rupees(3_500)


def test_the_thirteenth_month_was_free(client, family_headers):
    """Twelve paid months earned a credit that covered the next invoice."""
    invoices = client.get("/api/v1/invoices", headers=family_headers).json()
    free = [i for i in invoices if i["total_paise"] == 0]
    assert len(free) == 1

    invoice = free[0]
    assert invoice["subtotal_paise"] == pricing.rupees(3_500)
    assert invoice["credit_paise"] == pricing.rupees(3_500)
    assert invoice["credits"][0]["kind"] == "loyalty"


def test_invoice_lines_describe_what_was_bought(client, family_headers):
    invoices = client.get("/api/v1/invoices", headers=family_headers).json()
    line = invoices[0]["lines"][0]
    assert line["description"] == "Care Plus — 1 month"
    assert line["quantity"] == 1
    assert line["amount_paise"] == pricing.rupees(3_500)


def test_admin_sees_every_invoice(client, admin_headers, family_headers):
    admin_invoices = client.get("/api/v1/invoices", headers=admin_headers).json()
    family_invoices = client.get("/api/v1/invoices", headers=family_headers).json()
    assert len(admin_invoices) > len(family_invoices)

    billed = {invoice["billed_to"] for invoice in admin_invoices}
    assert "Ashwin Technologies Pvt Ltd" in billed


def test_a_corporate_invoice_bills_per_employee(client, admin_headers):
    invoices = client.get("/api/v1/invoices", headers=admin_headers).json()
    corporate = next(i for i in invoices if i["billed_to"] == "Ashwin Technologies Pvt Ltd")
    line = corporate["lines"][0]
    assert line["quantity"] == 40
    assert line["unit_paise"] == pricing.rupees(2_800)
    assert line["amount_paise"] == pricing.rupees(2_800) * 40


def test_another_family_cannot_read_this_invoice(client, family_headers, other_family):
    invoice_id = client.get("/api/v1/invoices", headers=family_headers).json()[0]["id"]
    headers = auth(login(client, other_family["email"], DEMO_PASSWORD))

    # 404 rather than 403: a 403 would confirm the invoice exists.
    assert client.get(f"/api/v1/invoices/{invoice_id}", headers=headers).status_code == 404
    assert client.get(f"/api/v1/invoices/{invoice_id}/pdf", headers=headers).status_code == 404


def test_a_nurse_cannot_read_invoices(client, nurse_headers, family_headers):
    invoice_id = client.get("/api/v1/invoices", headers=family_headers).json()[0]["id"]
    assert client.get(f"/api/v1/invoices/{invoice_id}", headers=nurse_headers).status_code == 403


def test_invoices_require_authentication(client, family_headers):
    invoice_id = client.get("/api/v1/invoices", headers=family_headers).json()[0]["id"]
    assert client.get(f"/api/v1/invoices/{invoice_id}/pdf").status_code == 401


# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------


def test_generating_the_same_period_twice_does_not_bill_twice(db):
    subscription = _family_subscription(db)
    before = len(subscription.invoices)

    first = billing_service.generate_invoice(db, subscription)
    second = billing_service.generate_invoice(db, subscription)

    assert first.id == second.id
    assert len(db.scalars(select(Invoice).where(Invoice.subscription_id == subscription.id)).all()) == before


def test_the_database_refuses_a_duplicate_period_even_without_the_lookup(db):
    """Belt and braces: the unique constraint stands on its own."""
    from sqlalchemy.exc import IntegrityError

    subscription = _family_subscription(db)
    existing = subscription.invoices[0]

    db.add(
        Invoice(
            number="DD-9999-000001",
            subscription_id=subscription.id,
            period_start=existing.period_start,
            period_end=existing.period_end,
            issued_at=existing.issued_at,
            due_at=existing.due_at,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_catching_up_missed_periods_produces_one_invoice_each(db):
    subscription = _family_subscription(db)
    before = len(db.scalars(select(Invoice).where(Invoice.subscription_id == subscription.id)).all())
    three_months_on = subscription_service.add_months(subscription.current_period_end, 2)

    billing_service.generate_due_invoices(db, as_of=three_months_on)

    after = db.scalars(select(Invoice).where(Invoice.subscription_id == subscription.id)).all()
    assert len(after) == before + 3, "a missed quarter must bill three periods, not one"
    starts = [invoice.period_start for invoice in after]
    assert len(starts) == len(set(starts))


def test_a_dry_run_predicts_the_real_run_and_writes_nothing(db):
    """The whole value of a dry run is that it cannot disagree with the real one."""
    subscription = _family_subscription(db)
    as_of = subscription_service.add_months(subscription.current_period_end, 2)
    before = {invoice.id for invoice in db.scalars(select(Invoice)).all()}

    preview = billing_service.generate_due_invoices(db, as_of=as_of, dry_run=True)

    assert preview, "a period has closed, so there is something to preview"
    assert {invoice.id for invoice in db.scalars(select(Invoice)).all()} == before

    # Running it a second time must predict the same thing, not compound.
    again = billing_service.generate_due_invoices(db, as_of=as_of, dry_run=True)
    assert [row["number"] for row in again] == [row["number"] for row in preview]

    actual = billing_service.generate_due_invoices(db, as_of=as_of)
    assert [row["number"] for row in actual] == [row["number"] for row in preview]
    assert [row["total_paise"] for row in actual] == [row["total_paise"] for row in preview]
    assert len(db.scalars(select(Invoice)).all()) == len(before) + len(preview)


def test_invoice_numbers_are_sequential_within_a_year(db):
    subscription = _family_subscription(db)
    numbers = [
        invoice.number
        for invoice in sorted(subscription.invoices, key=lambda i: i.issued_at)
        if invoice.number.startswith("DD-2026-")
    ]
    assert numbers == sorted(numbers)
    assert len(numbers) == len(set(numbers))


def test_a_credit_larger_than_the_bill_is_kept_whole_for_next_time(db):
    """A credit is never split, so both invoices stay explainable to a customer.

    The seed leaves a ₹3,500 referral credit unspent. Adding a ₹10,000 one and
    billing a ₹3,500 month must spend the credit that fits and leave the one
    that does not — rather than clipping ₹3,500 off the larger credit and
    leaving a ₹6,500 fragment nobody can account for.
    """
    from app.models import Credit, CreditKind

    subscription = _family_subscription(db)
    oversized = subscription_service.grant_credit(
        db,
        subscription,
        kind=CreditKind.ADJUSTMENT,
        amount_paise=pricing.rupees(10_000),
        reason="Goodwill",
    )
    invoice = billing_service.generate_invoice(
        db,
        subscription,
        period_start=subscription.current_period_end,
        period_end=subscription_service.add_months(subscription.current_period_end, 1),
    )

    # The ₹3,500 referral credit fits exactly and is spent; the ₹10,000 is not.
    assert invoice.credit_paise == pricing.rupees(3_500)
    assert invoice.total_paise == 0
    assert oversized.applied_invoice_id is None
    assert oversized.amount_paise == pricing.rupees(10_000), "kept whole, not clipped"
    assert subscription_service.unspent_credit_paise(db, subscription) == pricing.rupees(10_000)

    applied = db.scalars(select(Credit).where(Credit.applied_invoice_id == invoice.id)).all()
    assert [c.kind for c in applied] == [CreditKind.REFERRAL]


# --------------------------------------------------------------------------
# Payment
# --------------------------------------------------------------------------


def test_admin_can_settle_an_outstanding_invoice(client, admin_headers, family_headers):
    outstanding = next(
        i for i in client.get("/api/v1/invoices", headers=family_headers).json()
        if i["status"] == "issued"
    )
    response = client.post(f"/api/v1/invoices/{outstanding['id']}/pay", headers=admin_headers)
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["status"] == "paid"
    assert body["paid_at"] is not None
    # The simulated gateway hands back a reference and no money moves.
    assert body["payment_reference"].startswith("MAN-")


def test_a_family_cannot_mark_their_own_invoice_paid(client, family_headers):
    outstanding = next(
        i for i in client.get("/api/v1/invoices", headers=family_headers).json()
        if i["status"] == "issued"
    )
    assert client.post(f"/api/v1/invoices/{outstanding['id']}/pay", headers=family_headers).status_code == 403


def test_paying_twice_is_refused(client, admin_headers, family_headers):
    outstanding = next(
        i for i in client.get("/api/v1/invoices", headers=family_headers).json()
        if i["status"] == "issued"
    )
    client.post(f"/api/v1/invoices/{outstanding['id']}/pay", headers=admin_headers)
    again = client.post(f"/api/v1/invoices/{outstanding['id']}/pay", headers=admin_headers)
    assert again.status_code == 409


def test_paying_counts_a_paid_month(db):
    subscription = _family_subscription(db)
    before = subscription.paid_months
    outstanding = next(i for i in subscription.invoices if i.status == InvoiceStatus.ISSUED)

    billing_service.mark_paid(db, outstanding)
    assert subscription.paid_months == before + 1


def test_the_payment_boundary_never_takes_card_details():
    """The gateway signature accepts an amount and a description. Nothing else."""
    import inspect

    from app.services import payment_gateway

    parameters = set(inspect.signature(payment_gateway.charge).parameters)
    assert parameters == {"amount_paise", "description"}

    result = payment_gateway.charge(amount_paise=100, description="test")
    assert result.status.value == "simulated"
    assert "no money moved" in (result.detail or "").lower()


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------


def test_invoice_renders_as_a_pdf(client, family_headers):
    invoice = client.get("/api/v1/invoices", headers=family_headers).json()[0]
    response = client.get(f"/api/v1/invoices/{invoice['id']}/pdf", headers=family_headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:5] == b"%PDF-"
    assert invoice["number"] in response.headers["content-disposition"]
    assert len(response.content) > 2000


@pytest.mark.parametrize(
    "paise, expected",
    [
        (0, "₹0"),
        (19_900, "₹199"),
        (350_000, "₹3,500"),
        (7_800_000, "₹78,000"),
        (12_345_678, "₹1,23,456.78"),
        (100_000_000, "₹10,00,000"),
    ],
)
def test_amounts_use_indian_digit_grouping(paise, expected):
    """₹1,23,456 — lakh grouping, not the thousands grouping `toLocaleString` gives by default."""
    assert billing_service.format_inr(paise) == expected


# --------------------------------------------------------------------------
# Revenue
# --------------------------------------------------------------------------


def test_revenue_is_visible_to_admins_only(client, admin_headers, family_headers, nurse_headers):
    assert client.get("/api/v1/admin/revenue", headers=admin_headers).status_code == 200
    assert client.get("/api/v1/admin/revenue", headers=family_headers).status_code == 403
    assert client.get("/api/v1/admin/revenue", headers=nurse_headers).status_code == 403


def test_mrr_sums_the_live_subscriptions(client, admin_headers):
    body = client.get("/api/v1/admin/revenue", headers=admin_headers).json()
    expected = (
        pricing.rupees(2_800) * 40  # corporate, 40 employees
        + pricing.rupees(58_000)  # institution, 25 residents
        + pricing.rupees(3_500)  # Care Plus
        + pricing.rupees(2_500)  # Essential
    )
    assert body["mrr_paise"] == expected
    assert body["arr_paise"] == expected * 12
    assert body["active_subscriptions"] == 4
    assert body["arpu_paise"] == expected // 4


def test_an_annual_subscription_contributes_a_twelfth_to_mrr(db):
    """Otherwise MRR spikes in whatever month the annual plan renewed."""
    from app.models import BillingCycle

    subscription = _family_subscription(db)
    subscription.billing_cycle = BillingCycle.ANNUAL
    db.flush()

    summary = billing_service.revenue_summary(db)
    contribution = pricing.rupees(35_000) // 12
    assert any(row["mrr_paise"] == contribution for row in summary["by_plan"])


def test_only_paid_invoices_count_as_collected(client, admin_headers, family_headers):
    before = client.get("/api/v1/admin/revenue", headers=admin_headers).json()
    outstanding = next(
        i for i in client.get("/api/v1/invoices", headers=family_headers).json()
        if i["status"] == "issued"
    )
    assert before["outstanding_paise"] == outstanding["total_paise"]

    client.post(f"/api/v1/invoices/{outstanding['id']}/pay", headers=admin_headers)
    after = client.get("/api/v1/admin/revenue", headers=admin_headers).json()

    assert after["outstanding_paise"] == 0
    assert after["collected_all_time_paise"] == (
        before["collected_all_time_paise"] + outstanding["total_paise"]
    )
