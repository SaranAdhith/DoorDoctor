# Phase 4 — Subscriptions, plans, billing, quotas, referrals, loyalty (§3)

**Goal:** DoorDoctor stops being a monitoring demo and becomes a business with a price list. A
family can see what they pay for and what it entitles them to; an admin can see what the company
earns. Every later phase asks *this* layer what a subscriber is allowed to do.

**Constraint that shapes everything below:** the §3 text was not available when this phase was
built. Prices are recorded verbatim in the plan file's Phase 8 section and are used as-is. Tier
*names*, entitlement *quantities*, the referral reward and the loyalty benefit are **not** recorded
anywhere. Rather than scatter guesses, every unrecorded value is a named constant in **one file**,
marked `ASSUMED`, and listed in STATE.md. Reconciling with the real §3 is then a one-file edit.

---

## Step 1 — `core/pricing.py`, the single source of prices

Not a service, not a model — a constants module with no imports from the app, so anything may read
it and nothing can circle back. Money is **integer paise** throughout (₹3,500 → `350000`); no float
touches money at any point.

Recorded verbatim, not invented:

| | Monthly | Annual |
|---|---|---|
| tier 1 | ₹2,500 | ₹25,000 |
| tier 2 (**Recommended**) | ₹3,500 | ₹35,000 |
| tier 3 | ₹4,500 | ₹45,000 |

Annual is exactly 10× monthly, which is the recorded "2 months free" — asserted by a test rather
than trusted.

Corporate ₹2,800/employee/month. Add-ons: blood panel ₹499, pill organiser ₹199.

**Institutional bands are derived, not guessed.** The prompt gives both a monthly figure and a
per-resident-per-day rate, and the pair fixes the band size:

```
₹84/day × 30 × 15 residents = ₹37,800  ≈ ₹38,000
₹77/day × 30 × 25 residents = ₹57,750  ≈ ₹58,000
₹65/day × 30 × 40 residents = ₹78,000  =  ₹78,000   exact
```

So the three institutional plans include **15 / 25 / 40 residents**. The arithmetic is written into
the module and asserted by a test, so the derivation is auditable instead of folklore.

`ASSUMED` in this module: the three individual tier names, every entitlement quantity, the
institutional plan names, the referral reward and the loyalty benefit. No GST or tax is modelled —
none was specified, and inventing a tax rate would put a wrong number on an invoice.

## Step 2 — entitlements are data on the plan row, never `if tier == "premium"`

STATE.md flags this: Phase 9 reads these for care-manager ratios, telemedicine limits and lab
panels. A branch on a tier string would put Phase 9's business rules inside Phase 4's code.

So `Plan.entitlements` is a JSON column, seeded from `pricing.py`, and every consumer goes through
`subscription_service.entitlement(sub, key)`. Adding a tier later is a data change.

The two ratios recorded in STATE.md — **1:20 shared, 1:10 dedicated** — are used as-is; which tier
gets which is `ASSUMED`. Telemedicine **2/month on Premium** is recorded; the lower tiers are
`ASSUMED`.

## Step 3 — models

`models/organization.py` — `Organization` (corporate | institution, seats, contact). Corporate and
institutional subscriptions are the same `Subscription` row pointed at an org instead of a family
user, so billing has one code path rather than three.

`models/subscription.py`:
- `Plan` — code, name, audience, cycle prices, `recommended`, `entitlements` JSON, `sort_order`.
- `Subscription` — plan, **exactly one of** `family_user_id` / `organization_id` (enforced by a
  `CheckConstraint`, not by hope), status, cycle, seats, period window, `paid_months`,
  `cancel_at_period_end`, `referral_code`.
- `QuotaUsage` — unique on `(subscription_id, period_start, quota)`. Keying usage by period start
  is what makes **rollover free**: a new period is new rows, and last period's numbers survive as
  history instead of being reset to zero.

`models/billing.py` — `Invoice` (+ `InvoiceLine`). Numbered `DD-YYYY-NNNNNN`, unique.
`subtotal → credits → total`, all paise.

`models/referral.py` — `Referral` and `Credit`. **Referral rewards and loyalty rewards are the same
mechanism**: a `Credit` row with a `kind`. Two reward systems that both mean "money off the next
invoice" should not be two tables; billing then applies credits without caring where they came from.

## Step 4 — `services/subscription_service.py`

`sync_plans` (constants → rows, idempotent) · `for_user` · `entitlement` · `has_entitlement` ·
`quota_status` · `consume_quota` · `advance_period` · `change_plan` · `cancel`.

**Period rollover and loyalty are one function.** `advance_period` walks the subscription forward
while `current_period_end` is in the past, incrementing `paid_months` — and every time that counter
crosses a multiple of **12**, it grants a loyalty `Credit`. A subscription that has been ignored for
three months lands in the right period with the right credits, because the loop runs to completion
rather than assuming it is called exactly once a month.

`consume_quota` raises `ConflictError` when the allowance is spent. Unlimited is `None`, not a
sentinel like `-1` that some caller will one day compare with `<`.

## Step 5 — `services/payment_gateway.py`

**No gateway is bought in this build.** Same shape as Phase 3's `notification_delivery.py`: a
`PaymentGateway` protocol, a `ManualGateway` that records an intent and reports `simulated`, and one
`charge()` entry point. When a real gateway arrives it implements the protocol; no call site moves.

Card numbers, UPI handles and gateway secrets are **never** accepted or stored — the boundary takes
an amount and a reference, nothing more.

## Step 6 — `services/billing_service.py`

`generate_invoice` · `generate_due_invoices` · `mark_paid` · `render_pdf`.

Invoice generation is **idempotent per period** — a unique constraint on
`(subscription_id, period_start)` plus a lookup before insert. Re-running the CLI must not bill a
family twice; that is the kind of bug that ends a company.

`python -m app.billing --generate-invoices [--as-of YYYY-MM-DD] [--dry-run]`.

**WeasyPrint is pulled forward from Phase 6** so `/invoices/{id}/pdf` returns a real PDF instead of
an HTML placeholder that Phase 6 would rewrite. Verified: WeasyPrint 69.0 installs into this venv
and renders. Phase 6's report renderer then reuses a dependency already proven by the test suite.

## Step 7 — `services/referral_service.py`

`code_for` (mint on first read, `DD-XXXXXX`, unique) · `summary` · `invite` · `record_signup`.

`invite` goes through Phase 3's delivery seam and Phase 3's rate limiter — the second consumer of
both, which is the point of having built them as abstractions.

## Step 8 — routers

`routers/subscriptions.py` — `GET /plans`, `GET /subscriptions/me`,
`POST /subscriptions/{id}/change-plan`, `POST /subscriptions/{id}/cancel`.
`routers/billing.py` — `GET /invoices`, `GET /invoices/{id}`, `GET /invoices/{id}/pdf`.
`routers/referrals.py` — `GET /referrals/me`, `POST /referrals/invite`.
`routers/admin.py` — `GET /admin/subscriptions`, `GET /admin/revenue`.

Authorization follows the existing rule in `core/dependencies.py`: **someone else's invoice is a
404, not a 403**, exactly as someone else's patient already is. A 403 would confirm the record
exists. Nurses have no billing access at all.

## Step 9 — seed

The demo family gets a **Care Plus** subscription started 14 months ago, so the screen shows a real
history: paid invoices, a loyalty credit already earned at month 12, one referral that converted,
and part of this month's visit quota consumed. A subscription created today would render every
interesting number as zero.

## Step 10 — frontend

`lib/money.ts` (`formatINR` — Indian digit grouping, from paise), `api/billing.ts`,
`pages/family/MyPlan.tsx`, `pages/admin/AdminSubscriptions.tsx`, `pages/admin/AdminRevenue.tsx`,
nav entries, routes.

The monthly/annual toggle uses Phase 3's **`SegmentedControl`** — STATE.md asked for it by name.
Invoice download needs an `Authorization` header, so `api/client.ts` gains a `getBlob` helper; a
plain `<a href>` would hit the endpoint unauthenticated.

## Acceptance

- Backend suite green and larger than 96; new files: `test_subscriptions.py`, `test_billing.py`,
  `test_referrals.py`, `test_pricing.py`.
- Annual = 10× monthly asserted. Institutional band arithmetic asserted.
- Invoice generation asserted idempotent.
- Family cannot read another family's subscription, invoice or PDF (404).
- Nurse gets 403 on every billing route.
- `python -m app.seed` clean · `npx tsc -p tsconfig.json --noEmit` clean · `npm run build` clean ·
  `npx vitest run` green.
- Verified live in Chrome at 375 / 768 / 1024 / 1440.

Commit: `feat(billing): subscriptions, plans, invoices, quotas, referrals and loyalty`
