# DoorDoctor Platform v2 — Build State

Running ledger for the multi-phase build. **Read this first in a new session**, then
`docs/build-log/phase-N.md` for the phase you are starting. Together with `git log` this restores
full context without re-reading the codebase.

The full build specification lives in the founder's original prompt. The phase plan is at
`/home/saran/.claude/plans/doordoctor-platform-clever-hippo.md`.

---

## Locked decisions

| Decision | Answer |
|---|---|
| Source of facts | **The build prompt is the source of truth.** No business documents exist in the repo. Every price, tier, ratio and founder name comes from the prompt verbatim. Invent no traction, testimonials, customer counts, certifications or partner logos — DoorDoctor is pre-launch. |
| Checkpointing | Report at each phase boundary and continue. No waiting for approval between phases. |
| Git | Commit directly on `main`, one conventional commit per phase boundary, full suite green before each. **Commit promptly** — see the incident note below. |
| LLM provider | **Groq, not Anthropic.** The founder supplies a free Groq API key when a phase needs it. No `anthropic` package, no Claude API key. The deterministic fallback is mandatory and is built and tested *first*. |

### Founders — always named together, as an equal pair
- **Saran Adhith** — Founder & CEO
- **Darren D'Souza** — Co-Founder

### LLM integration contract (Phases 6 and 7)
- Single boundary: `backend/app/services/llm_client.py`.
- Groq's OpenAI-compatible endpoint `https://api.groq.com/openai/v1/chat/completions`, called with
  **`httpx`, already in requirements.txt** — no new dependency.
- Env: `GROQ_API_KEY`, `GROQ_MODEL` (default `llama-3.3-70b-versatile`), `GROQ_BASE_URL`,
  `ASSISTANT_ENABLED`.
- Timeouts: **2s** for the plain-summary rewrite, **8s** for the assistant. Both fall back silently
  to deterministic output. The demo must work with no key and no network.

---

## Phase status

| Phase | Scope | Status |
|---|---|---|
| 1 | Terminology refactor (caregiver→nurse, coordinator→admin) | ✅ done — `53fdb4d` |
| 2 | Design system, UI primitives, sidebar navigation | ✅ done — `3cd24cf` |
| 3 | Forgot password + login rebuild | ✅ done — `2eeb9f8` |
| 4 | Subscriptions, plans, billing, quotas, referrals, loyalty | ✅ done — `2058e32` |
| 5 | Realistic seed data | ⬜ **next** |
| 6 | Plain-language summary + reports | ⬜ |
| 7 | AI assistant (family + admin) | ⬜ |
| 8 | Public marketing site + leads | ⬜ |
| 9 | Clinical features (labs → escalation) | ⬜ |
| 10 | Trust, GPS, medication, community, consent, ops, notifications | ⬜ |
| 11 | Multi-family, hardening, tests, docs | ⬜ |

Phases 1–8 are the "credible demoable platform" line. A finished phase 8 beats a broken phase 11.

---

## How to verify (run before every commit)

```bash
cd backend  && .venv/bin/python -m pytest          # 183 passing today; the count only grows
cd backend  && .venv/bin/python -m app.seed        # must run clean
cd backend  && .venv/bin/python -m app.billing --generate-invoices --dry-run   # previews, writes nothing
cd frontend && npx tsc -p tsconfig.json --noEmit   # zero errors, no `any`, no @ts-ignore
cd frontend && npm run build                       # clean
cd frontend && npx vitest run                      # 56 passing today
```

Note: `npx tsc -b --noEmit` is **invalid** here (referenced project disables emit) — use
`-p tsconfig.json --noEmit` as above, or `npm run build` which runs `tsc -b && vite build`.

### Visual verification
Chrome and the Playwright browsers are already installed on this machine. `playwright-core` is
installed in `frontend/` with `--no-save` (deliberately **not** in package.json). Drive it with a
throwaway script placed **inside `frontend/`** so it can resolve `node_modules`:

```js
import { chromium } from 'playwright-core'
const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome-stable', headless: true })
```
Log in at `http://127.0.0.1:5173/login`, fill email + `Demo@123`, submit. Check 375 / 768 / 1024 / 1440.

---

## Environment

| Variable | Added in | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | baseline | `sqlite:///./doordoc.db` | Database connection |
| `JWT_SECRET` | baseline | `change-this-in-development` | Token signing |
| `JWT_EXPIRE_MINUTES` | baseline | `1440` | Access token lifetime |
| `CORS_ORIGINS` | baseline | `http://localhost:5173,...` | CORS allow-list |
| `VITE_API_BASE_URL` | baseline | `http://localhost:8000/api/v1` | Frontend API base |
| `FRONTEND_BASE_URL` | Phase 3 | `http://localhost:5173` | Where password-reset links point |

Backend venv is `backend/.venv` (Python 3.13.12). Node v20.20.2. WeasyPrint's system libraries
(pango, cairo, harfbuzz, gobject) are verified present for Phase 6. PyPI and npm are reachable.

## Dependencies added so far

| Where | Package | For |
|---|---|---|
| frontend | `lucide-react` | Icons, replacing emoji (Phase 2) |
| backend | `weasyprint` 69.0 | Invoice PDFs (Phase 4) — **pulled forward from Phase 6** |

Still planned: `apscheduler`, `alembic` (backend); `react-helmet-async`, `@playwright/test`
(frontend). **No `anthropic` — the provider is Groq via `httpx`.**

⚠️ **The backend venv has no `pip`** — it was created by `uv`. Install with
`uv pip install --python .venv/bin/python <package>`, not `.venv/bin/pip`.

---

## Phase results

### Phase 1 — terminology refactor → `53fdb4d`
- 51 files rewritten, 16 paths renamed via `git mv` (history preserved), ~700 occurrences resolved.
- Grep audit: **0** hits for caregiver/coordinator outside `docs/build-log/`.
- Live smoke test: all three roles log in, `/admin/summary` and `/nurses` serve, old
  `/coordinator/summary` and `/caregivers` 404, and the 148/92 breach path runs end-to-end.
- Family-facing prose was written by hand, not substituted — "your admin" is wrong to say to a
  family member, so FamilyAlerts reads "Your DoorDoctor care team reviews and resolves alerts".
- Repaired column alignment the shorter words broke in the README architecture box and the
  DESIGN.md route map.

### Phase 2 — design system, primitives, navigation → `3cd24cf`
- **Tokens** in `tailwind.config.js`: semantic surfaces, borders, text and clinical status colours
  layered on top of the untouched navy/brand palette. One type scale (display 32/40 → caption
  12/16), `.tnum` for readings, two elevations, one radius family.
- **Contrast was measured, not assumed.** Two candidates failed WCAG AA and were darkened:
  `text-muted` (slate-400 measured **3.39:1**) → `#5f7186`, and `status-good` (brand-600 measured
  **3.65:1** on its own tint) → brand-700 `#1d7529`. Every token now clears 4.5:1 against its
  worst-case ground. **Re-run that check if you touch a colour.**
- **28 primitives** in `components/ui/`, exported from one barrel. They *absorbed*
  `components/common/` and `cards/StatCard` — those are deleted, not paralleled.
  `Field` wires label + hint + error + ARIA once. `useFocusTrap` backs Modal and Drawer.
  `LinkButton` is kept separate from `Button` on purpose: a navigation is an anchor, an action is a
  button.
- **Navigation** replaced the top-tab bar: collapsible left sidebar with grouped sections
  (persisted in `localStorage`), top bar for notifications/account, mobile bottom tab bar, and the
  same sidebar served in a drawer below 768px.
- **Charts**: one axis/grid/tooltip/threshold treatment in `components/charts/chartTheme.ts`.
  Reuse it for every chart added later.
- Verified in a real browser at 375 / 768 / 1024 / 1440.

### Phase 3 — password reset, delivery channels, rebuilt login → `2eeb9f8`
- **Reset tokens**: `secrets.token_urlsafe(32)`, stored **only** as sha256. 30-minute expiry, single
  use, and a new request stamps `used_at` on the outstanding siblings so the newest link is the only
  working one. A completed reset kills every other open link for that account.
- **`POST /auth/forgot-password` always returns 200** with an identical body — the endpoint never
  answers "does this person have an account?". An inactive account is treated exactly like an
  unknown one. `debug_reset_url` appears only when `settings.is_development`.
- **`core/ratelimit.py`** — in-memory sliding window, **5/email/hr** and **20/IP/hr**, raising the
  new `TooManyRequestsError` (429 + `Retry-After`). Process-global, so `tests/conftest.py` has an
  **autouse fixture that resets it** — without that, test order decides test outcomes. Reusable by
  Phase 8's lead form.
- **`services/notification_delivery.py`** — `EmailChannel | SmsChannel | WhatsAppChannel |
  PushChannel` behind one protocol, writing a real `delivery_log` row and reporting `simulated`
  (no provider is bought in this build). This is the seam Phase 10's routing/preferences/quiet hours
  extends; don't build a second one.
- **Secrets are redacted before they are persisted.** `deliver(..., sensitive=[link])` replaces the
  value with `[redacted]` in the stored body. Otherwise `delivery_log` would be a table of live
  account takeovers. A test asserts the raw token never appears in any stored body — **keep it.**
- **One password rule**, `core/security.password_problem`, mirrored (not re-invented) in
  `frontend/src/lib/password.ts`. Both sides are asserted against the same cases, so drift fails a
  test on one side or the other.
- **`SegmentedControl` is a new primitive**, not inline markup: a `role="radiogroup"` needs roving
  tabindex and arrow keys, which the first inline version did not have. Phase 4's monthly/annual
  toggle and Phase 6's 7d/30d/90d picker should use it.
- **`AuthLayout`** now backs all three auth screens; `Login` was rebuilt onto it (segmented role
  picker, trust row, collapsed `<details>` demo access). The role picker is **presentation only** —
  the server decides the role. Commented in the source.
- Verified live in Chrome at 375/768/1024/1440, full journey end to end, and the 429 was confirmed
  against the running server (`retry-after: 3248`), not only in tests.

### Phase 4 — subscriptions, billing, quotas, referrals, loyalty → `2058e32`

- **⚠️ §3 of the build prompt was never supplied.** Prices came from the plan file's Phase 8
  paragraph verbatim. Tier *names*, every entitlement *quantity*, the referral reward and the
  loyalty benefit are **not recorded anywhere** and are marked `ASSUMED` in `core/pricing.py`.
  **See the reconciliation list below — that is the first thing to settle with the founder.**
- **`backend/app/core/pricing.py` is the single source of every price.** It imports nothing from
  the app, so anything may read it and nothing can circle back. Money is **integer paise**
  throughout; no float touches money anywhere in this codebase.
- **The institutional bands were derived, not guessed.** The prompt gives both a monthly price and
  a per-resident-per-day rate, and the pair fixes the band size: ₹84×30×**15** = ₹37,800 ≈ ₹38,000;
  ₹77×30×**25** = ₹57,750 ≈ ₹58,000; ₹65×30×**40** = ₹78,000 exactly. `test_pricing.py` asserts the
  exact rounding gap (₹200 / ₹250 / ₹0), so a moved price says by how much rather than failing
  vaguely.
- **Entitlements are a JSON column on the plan row**, seeded from the constants, read only through
  `subscription_service.entitlement()`. Nothing anywhere branches on a tier name — the STATE
  deferral asked for this, and Phase 9 depends on it. `None` means *unlimited* and is deliberately
  not a `-1` sentinel some caller would compare with `<`.
- **Referral and loyalty rewards are one mechanism.** Both produce a `Credit` row with a `kind`;
  billing applies credits without knowing where they came from. Two reward systems meaning "money
  off the next invoice" should not be two tables.
- **Invoice generation is idempotent per period** — a unique constraint on
  `(subscription_id, period_start)` *and* a lookup before insert. Billing a family twice is the bug
  that ends a company, so it is prevented in the schema, not only in the generator.
- **A credit is never split.** One worth more than the invoice stays whole and waits, so a customer
  comparing two invoices can account for every rupee.
- **`--dry-run` does the real work and rolls it back.** The first version walked a separate preview
  branch and reported "nothing to invoice" while the real run wrote four — a preview computed by a
  second code path is a second implementation, and the one thing it must never do is disagree.
- **`services/payment_gateway.py` is a boundary, not a stub.** Same shape as Phase 3's delivery
  seam. It accepts an **amount and a description and nothing else** — a test asserts that
  signature, so card details cannot start flowing through it later.
- **Someone else's invoice is a 404, not a 403**, matching `authorize_patient`. A 403 confirms the
  record exists, which is enough to learn that a named person is a DoorDoctor customer. Nurses have
  no billing access at all.
- **WeasyPrint 69.0 pulled forward from Phase 6** so `/invoices/{id}/pdf` is a real PDF. Phase 6's
  report renderer reuses a dependency already proven by the suite and the same
  `app/templates/<kind>/` convention.
- **The seed builds its billing history by calling the services**, not by writing rows: 14 monthly
  invoices, the loyalty credit earned at month 12 and the **13th month billed at ₹0**, a referral
  that converted, a corporate account (40 employees) and a residence (25 residents). If the loyalty
  arithmetic breaks, the demo data is visibly wrong instead of fabricated around the bug.
- `mark_paid` stamps `paid_at` from the real clock, which is right in production and wrong in a
  seed — the seed backdates it, or fourteen months of revenue reports as collected this morning.
- **183 backend tests** (was 96) and **56 Vitest** (was 29). `lib/money.ts` mirrors the server's
  `format_inr` (lakh grouping) and both are asserted against the same cases, exactly as the
  password rule is mirrored.
- Verified live in Chrome at 375/768/1024/1440: change-plan (proration credited — ₹2,938 of an
  unused Care Plus month), cancel, resume, referral invite, and the PDF fetched **with** a bearer
  token (200, `%PDF-`) and **without** one (401).
- Fixed on the way: `Table` carries a 36rem minimum width, which silently scrolled the value column
  of a half-width card out of sight. `cn()` is a plain joiner, **not** tailwind-merge, so passing
  `min-w-0` does not override it — that card is a `<dl>` now. **Do not expect Tailwind class
  conflicts to resolve by specificity anywhere in this codebase.**

#### ⚠️ Reconcile with the real §3 before Phase 8 publishes prices

Everything below is invented and lives in **one file**, `backend/app/core/pricing.py`:

| Value | Assumed | Confidence |
|---|---|---|
| Tier names | Essential / Care Plus / **Premium** | "Premium" is attested by the recorded 2-consult telemedicine limit; the other two are guesses |
| Visits per month | 4 / 8 / 12 | invented |
| Telemedicine per month | 0 / 1 / **2** | Premium's 2 is recorded; the rest invented |
| Lab panels per year | 0 / 2 / 4 | invented |
| Care-manager tier mapping | shared / shared / dedicated | the **1:20 and 1:10 ratios are recorded**; which tier gets which is invented |
| Family seats | 2 / 4 / 6 | invented |
| Referral reward | referrer 1 free month, friend ₹1,000 | invented |
| Loyalty reward | 1 free month per 12 paid months | the **12-month trigger is recorded**; the reward is invented |
| Corporate/institutional names and entitlements | descriptive placeholders | prices are recorded |

**No GST or tax is modelled** — none was specified, and an invented rate would put a wrong number
on an invoice that looks authoritative. Phase 8 must import these constants rather than restate any
number.

#### Deliberately deferred out of Phase 4

- **Quotas are tracked but not yet enforced at the point of use.** Scheduling a visit does not call
  `consume_quota`; the seed and the tests do. Wiring it into `visit_service` would have changed the
  behaviour of every existing visit test and would refuse visits for patients whose family has no
  subscription (the `other_family` fixture). Do it in Phase 5 alongside the realistic seed, or in
  Phase 9 with telemedicine and labs — the engine and its tests are ready either way.
- **Add-on purchase flow.** Blood panel ₹499 and pill organiser ₹199 are priced constants with an
  `InvoiceLineKind.ADDON` ready for them, but nothing sells one yet. Phase 9 adds lab ordering,
  which is the natural first buyer.
- **Corporate/institutional self-service.** Organizations are modelled and billed; there is no
  admin UI to create one. Phase 8 captures them as leads, Phase 10 does the ops screens.

---

## ⚠️ Incident — external `git filter-branch` during Phase 2

At ~21:00 on 2026-08-21 an **external** `git filter-branch` + `git reset` ran against this repo
(reflog: `filter-branch: rewrite`, then `reset: moving to HEAD`). It stripped the binary assets from
history — `assets/` and `docs/screenshots/`, 10 files — the standard "shrink the repo before pushing
to GitHub" operation. It was not run from the build session.

Effects:
- Phase 1's commit was rewritten `0c797ec` → `53fdb4d`. **Content survived intact.**
- The accompanying reset **discarded uncommitted changes to tracked files**, costing part of the
  Phase 2 work, which was redone. Untracked new files were unaffected.
- `assets/` and `docs/screenshots/` are gone from the working tree. The founder has since restored
  the README logo (`8c4c369`). `frontend/public/` logos were never touched, so the app UI is fine.
- The pre-rewrite commit is still reachable at `refs/original/refs/heads/main` if anything is needed
  back.

**Lesson applied: commit at every phase boundary promptly, and do not leave large amounts of work
uncommitted in the working tree.**

---

## ▶ Starting Phase 5 — realistic seed data

Read `/home/saran/.claude/plans/doordoctor-platform-clever-hippo.md` (Phase 5 paragraph) for the
target dataset: `seed.py` → `backend/app/seed/` package, deterministic, 3 admins, 14 nurses, 28
patients across 6 Bangalore zones, 18 family users, ~1,400 visits over 90 days, vitals as
trajectories rather than noise, 30 resolved + 4 active alerts, and the 148/92 breach path preserved.

Four things measured at the end of Phase 4 that will bite otherwise:

1. **bcrypt costs 0.729 s per hash on this machine.** Today's 5 demo users are 3.6 s of the 5.4 s
   seed. Phase 5's ~35 users would be **~25 s every seed run** — and `tests/conftest.py` seeds the
   template database once per session, so the whole suite pays it. Every demo account shares
   `Demo@123`, so **hash it once and reuse the digest** for all of them. Identical `password_hash`
   values across demo users is fine here (the password is published in this file); it would not be
   in production.

2. **`payment_gateway.charge()` is not deterministic** — it mints `MAN-<random>` via `secrets`.
   Phase 5 requires a fixed seed, so either pass an explicit `reference=` to
   `billing_service.mark_paid()` for seeded invoices, or accept that payment references vary between
   runs and assert nothing about them.

3. **Billing history multiplies.** Today: 4 subscriptions → 36 invoices, in ~1.8 s of non-bcrypt
   work. Giving all 18 family users 14 months of history is ~250 invoices. Decide the spread
   deliberately — a mix of tenures (some 1 month old, some 14) is both faster and a better demo than
   giving everyone the same long history.

4. **Carry `_seed_business()` across intact.** It builds its history by calling `billing_service`
   and `subscription_service`, which is what proves the loyalty and credit arithmetic on every run.
   Reimplementing it with literal invoice rows would silently stop testing that.

Phase 4 left `--keep`; Phase 5 adds `--small` and `--demo-reset`. Keep `python -m app.seed` working
as the entry point — `tests/conftest.py` imports `seed` from it.

---

## Open items and deferrals

- **README image links.** `README.md` references `docs/screenshots/*.png`, which the history rewrite
  deleted. Either regenerate the screenshots (the app now looks materially different anyway, so
  these are stale) or drop the links. Worth doing as part of Phase 11 docs, or sooner if the founder
  wants the README presentable.
- **Care manager role.** §4.4 gives care managers their own ratios and worklist. Plan is to model
  them as a profile on an admin user rather than a fourth `UserRole`, which keeps the three-way
  route guard intact. Flagged for Phase 9; cheap to agree on early.
- **Login footer back-link deferred to Phase 8.** §2.5 asks for a back-link to the public site; `/`
  currently redirects to `/login`, so the link would be a loop. Add it when `pages/public/` lands.
- ✅ **Business documents / prices** — done in Phase 4. Everything lives in
  `backend/app/core/pricing.py`. **§3 was never supplied, so the invented values are listed in the
  Phase 4 results above and must be reconciled before Phase 8 publishes a pricing page.** Phase 8
  imports these constants; it must not restate a number.
- ✅ **Entitlements as data** — done. `Plan.entitlements` is a JSON column read through
  `subscription_service.entitlement()`. Phase 9 reads it for care-manager ratios (1:20 shared,
  1:10 dedicated), telemedicine limits and lab panels. Nothing branches on a tier name; keep it
  that way.
- **Seed data is thin on the clinical side** (1 patient, 1 nurse), so charts and vitals lists look
  sparse. Phase 5 fixes this; do not treat it as a bug before then. The *commercial* side is no
  longer thin — Phase 4 seeds 4 subscriptions, ~40 invoices, credits and a converted referral.
- **Phase 5 must not lose the billing seed.** `_seed_business()` in `seed.py` builds its history by
  calling `billing_service` and `subscription_service`. When `seed.py` becomes the
  `backend/app/seed/` package, carry that function across intact rather than reimplementing it with
  literal rows — it is what proves the loyalty and credit arithmetic on every run.

---

## Demo credentials

| Role | Email | Password |
|---|---|---|
| Family | `family@doordoctor.in` | `Demo@123` |
| Nurse | `nurse@doordoctor.in` | `Demo@123` |
| Admin | `admin@doordoctor.in` | `Demo@123` |
| Family (referred, Phase 4) | `meera@doordoctor.in` | `Demo@123` |

`meera@doordoctor.in` exists to make the referral story real — she was referred by the demo family
and her first payment is what earned them their reward. She has a subscription but no patient yet.
