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
| 5 | Realistic seed data | ✅ done — `d840578` |
| 6 | Plain-language summary + reports | ✅ done — `052841f` |
| 7 | AI assistant (family + admin) | ✅ done — `8d91748` |
| 8 | Public marketing site + leads | ✅ done — `PENDING` |
| 9 | Clinical features (labs → escalation) | ⬜ **next** |
| 10 | Trust, GPS, medication, community, consent, ops, notifications | ⬜ |
| 11 | Multi-family, hardening, tests, docs | ⬜ |

Phases 1–8 are the "credible demoable platform" line. A finished phase 8 beats a broken phase 11.

---

## How to verify (run before every commit)

```bash
cd backend  && .venv/bin/python -m pytest          # 408 passing today; the count only grows
cd backend  && .venv/bin/python -m app.seed        # must run clean (~5.4 s, full population)
cd backend  && .venv/bin/python -m app.seed --small        # the dataset the test suite uses
cd backend  && .venv/bin/python -m app.seed --demo-reset   # rewind the 148/92 path between demos
cd backend  && .venv/bin/python -m app.billing --generate-invoices --dry-run   # previews, writes nothing
cd frontend && npx tsc -p tsconfig.json --noEmit   # zero errors, no `any`, no @ts-ignore
cd frontend && npm run build                       # clean
cd frontend && npx vitest run                      # 87 passing today
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
| `GROQ_API_KEY` | Phase 6 | `""` (empty) | LLM key. **Empty is the demo configuration** — everything works without it |
| `GROQ_MODEL` | Phase 6 | `llama-3.3-70b-versatile` | Model id |
| `GROQ_BASE_URL` | Phase 6 | `https://api.groq.com/openai/v1` | Any OpenAI-compatible provider drops in here |
| `ASSISTANT_ENABLED` | Phase 6 | `true` | Master switch for every LLM call — summary **and** assistant |
| `REPORTS_SCHEDULER_ENABLED` | Phase 6 | `true` | **`false` in `tests/conftest.py`** — `TestClient` runs the lifespan |

Backend venv is `backend/.venv` (Python 3.13.12). Node v20.20.2. WeasyPrint's system libraries
(pango, cairo, harfbuzz, gobject) are verified present for Phase 6. PyPI and npm are reachable.

## Dependencies added so far

| Where | Package | For |
|---|---|---|
| frontend | `lucide-react` | Icons, replacing emoji (Phase 2) |
| backend | `weasyprint` 69.0 | Invoice PDFs (Phase 4) — **pulled forward from Phase 6** |
| backend | `apscheduler` 3.11.3 | Weekly/monthly report scheduling (Phase 6) |
| frontend | `react-helmet-async` 3.0.0 | Per-route SEO tags (Phase 8) |

Still planned: `alembic` (backend); `@playwright/test` (frontend).
**No `anthropic` — the provider is Groq via `httpx`.** Phase 6 added the Groq client and it needed
no new dependency, exactly as planned.

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

#### ⚠️ Reconcile with the real §3 — these values are now PUBLISHED

**Phase 8 published every value below on `/pricing`, unlabelled, on the founder's explicit
instruction (2026-08-22).** They were internal placeholders; they are now public claims to paying
customers. Reconciling is still a one-file change — everything below lives in
`backend/app/core/pricing.py` and `test_pricing.py` catches anything that moves — but the cost of
being wrong is no longer internal.

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

### Phase 5 — realistic seed data → `d840578`

- **`seed.py` became `backend/app/seed/`** via `git mv` (history preserved): `demo_data.py` (rosters,
  no logic), `generators.py` (pure functions, no db and no clock), `core.py` (the Phase-4 demo core),
  `population.py` (the wider business), `business.py` (Phase 4's billing seed, carried across),
  `reset.py`, `__main__.py`. `python -m app.seed` and `from app.seed import seed` both still work.
- **Two profiles from one code path.** `SMALL` is the Phase-4 dataset *exactly*; `FULL` is `SMALL`
  **plus** a population, never a second construction of the demo core. `tests/conftest.py` seeds
  `SMALL`, so **all 183 existing tests pass untouched** — they assert `total == 15` doses,
  `paid_months == 14`, `active_subscriptions == 4`, and they test the *application*, not the
  population. Rewriting them to tolerate 28 patients would have weakened them for nothing.
- **`tests/test_seed.py` (27 new tests) covers `FULL`**, seeding it once for the module. It asserts
  the four invariants the rest of the suite depends on but cannot see: patient 1 is Lakshmi, nurse 1
  is Anitha, **Anitha holds exactly one open visit today**, and **Lakshmi carries no open alert**.
  Break either of the last two and the alert tests still pass — against the wrong patient.
- **28 patients · 14 nurses · 18 families · 3 admins · 6 Bangalore zones · 1,453 visits ·
  1,290 readings · 3,490 doses · 34 alerts (30 resolved, 4 open) · 182 invoices · MRR ₹2,30,250.**
  Seeds in **5.4 s**.
- **Vitals are trajectories, not noise.** Four arcs (stable / improving / drifting / episodic) plus a
  sine wobble over the visit index, so consecutive readings stay related and a 90-day chart has a
  shape. Baselines follow the condition list — a patient recorded as diabetic does not sit at 95
  mg/dL for three months.
- **The alert count is exact by construction.** Every generated reading is clamped inside the
  patient's thresholds, so only `demo_data.EXCURSIONS` — a table of exactly 34 — can breach. Alerts
  are then raised by **`alert_service.create_threshold_alert`**, the real engine; nothing writes an
  `Alert` row. "A breaching reading always has an alert" is therefore true of the seed for the same
  reason it is true in production, and a test asserts it over every reading.
- **⚠️ The clamp flattened the charts, and nearly shipped that way.** A treated hypertensive's first
  baseline was 132 against a ceiling of 136, so **27% of systolic readings came out pinned** and
  those patients' charts drew a flat line — the trajectory existed in the arithmetic and was sheared
  off before it reached the database. Amplitudes are now sized *against* the clamp and baselines
  lowered to what a patient under treatment reads. 336 → 29 pinned of 1,256.
  **If you touch `_DRIFT`, `_WOBBLE` or `baseline_for`, re-run that check** —
  `test_generated_readings_are_not_pinned_to_the_clamp` is what keeps it honest.
- **bcrypt costs 0.729 s per hash**, so the digest of `Demo@123` is computed **once** and reused for
  all ~35 demo accounts. Identical `password_hash` values are acceptable here (the password is
  published) and would not be in production. Seeded invoices also pass an explicit `reference=`,
  because `payment_gateway.charge()` mints `MAN-<random>` and a fixed-seed dataset cannot hold one.
- **Billing tenures are spread, not uniform** — 1 to 18 months across the 18 families, plus one
  annual NRI account, one past-due account and one cancelling at period end. Uniform 14-month
  histories would have been ~250 invoices of identical data and a worse demo.
- **Two real `visit_service` bugs surfaced, neither reachable at six visits:**
  `list_today_visits` filtered a newest-100 page *after* fetching it, so a forward week of scheduling
  pushed today off the end and **the admin operations dashboard rendered an empty board**; and it
  kept a nurse's *future* visits on their worklist, contradicting its own docstring. The day window
  is now in the query. `list_visits_for_user`'s cap went 100 → 250 — a stopgap until Phase 10's
  visit board makes that list windowed and paginated.
- **`_bill_history` could not bill an annual subscriber** (`ConflictError: already been paid`) — it
  billed the period still running, then found that same paid row as the current invoice. It now bills
  only periods whose end has passed. Latent since Phase 4; nothing was sold annually until now.
- `--demo-reset` rewinds only what a demo run changes: Lakshmi's visit back to `scheduled`, its
  readings and dose logs deleted, its alerts and notifications gone. Users, subscriptions, invoices
  and 90 days of history are untouched. It deletes alerts *before* the readings they reference —
  SQLite does not enforce foreign keys unless asked, so a dangling row would survive silently.
- Verified live in Chrome at 375/768/1024/1440 across all three roles and twelve screens, zero
  console errors.

#### ⚠️ Evidence about the real §3, from the recorded visit volume

§2.4 records **~1,400 visits over 90 days for 28 patients — 16.7 visits per patient per month.**
Phase 4's entitlements are **4 / 8 / 12 per month** and are marked `ASSUMED`. The recorded volume is
roughly **double the highest assumed tier**, which is real evidence that the true per-tier allowance
is nearer alternate-day to daily care. Add this to the reconciliation list above.

**Founder's decision, 2026-08-22: leave 4 / 8 / 12 as they are, and publish them.** Phase 8 puts
them on `/pricing` unlabelled. The evidence above is unchanged and so is the deferral below — this
is now a *published* number that the recorded volume contradicts, which raises the cost of
reconciling it without changing what needs to be reconciled.

Consequence: **quota enforcement at the point of use stays deferred.** Enforcing an invented limit
against a recorded volume would refuse the visits the demo is specified to contain. The seed's
cadences (`demo_data.VISITS_PER_WEEK`: 2 / 4 / 6 per week) follow the recorded volume, not the
assumed entitlements. Reconcile §3 first, then enforce.

#### Deliberately deferred out of Phase 5

- **A real `zone` column** on `Patient` and `Nurse`. Zones live in this seed as addresses plus the
  nurse→zone roster in `demo_data.ZONES` / `EXTRA_NURSES`, which is enough for six recognisable
  Bangalore areas across the patient list. Phase 10 owns the zone view and the ~30–45 subscriber
  break-even and should lift that table into a column then.
- **A resolution note on `Alert`.** §8's journey 3 says the admin "resolves it with a note", and
  there is nowhere to put one — `alert_service.resolve` takes no note and the model has no column.
  Phase 10's alert queue with SLA is the right place. A drafted table of resolution notes was deleted
  rather than left as data with no home.
- **The suite takes 2m13s, and almost all of it is bcrypt.** ~180 logins × 0.73 s per verify. Phase 5
  removed the *seed's* share of that cost; the login share needs a test-only cost factor, which is a
  change to `core/security.py` and belongs with Phase 11's hardening.

---

### Phase 6 — plain-language summary, reports, the LLM boundary → `052841f`

- **The banned-word list is a runtime guard, not only a test.** `summary_service`
  `contains_clinical_language()` is applied to the deterministic output by the suite *and* to every
  LLM rewrite at runtime. A test asserting the generator avoids "systolic" is worth little if the
  rewrite three steps later puts it back. Substring matching on purpose, so "thresholds" and
  "breached" are caught with their stems.
- **The deterministic generator is the product; the model is a polish pass.** It ships alone,
  verified live with `GROQ_API_KEY` unset. `source` is reported honestly in the payload
  (`deterministic` / `assisted`) so the fallback can be *shown* in a demo rather than asserted.
- **Four gates stand between a rewrite and a family member**, in `summary_service`, not in
  `llm_client` — the client is transport, the service owns meaning. Banned words · **no number that
  is not already in the deterministic text** · length between 0.5× and 2× · no advice register
  (`diagnos`, `prescri`, `i recommend`, `emergency room`). Gate 2 is the one that matters: a model
  cannot invent a blood pressure reading if a digit it was never given is grounds for rejection.
  Only the headline and paragraphs are ever rewritten — the highlights carry tones that drive UI.
- **`llm_client.complete()` never raises.** No key, disabled, timeout, 500, malformed body, empty
  completion — all return `None`, so every caller has one fallback path instead of an except-list
  that drifts. **Phase 7's assistant calls this same function** with `ASSISTANT_TIMEOUT` (8s) instead
  of `SUMMARY_TIMEOUT` (2s). Do not add a second client.
- **The prompt is never logged.** A prompt here contains a named person's readings. Only the failure
  *type* and elapsed ms are logged — `httpx` exception messages can echo the request, so the
  exception type is logged rather than the exception. A test asserts a patient name never reaches
  the log.
- **The cache is keyed on content, not only time.** 15 min per `(patient_id, window)` **plus a
  sha256 of the deterministic text**. Time alone would keep serving the last quarter-hour's paragraph
  after a nurse records a new reading; the fingerprint makes new data bust it immediately and turns
  the TTL into a cost control rather than a correctness risk. `cache.reset()` is called by the
  autouse fixture in conftest for the same reason `limiter.reset()` is.
- **⚠️ A monthly report headed "1 July — 1 August" was quoting a 21 August reading**, and it took
  rendering the PDF and *looking at it* to catch — every test passed. `build_deterministic` used a
  rolling window from `now()` while `period_for` returned a closed calendar month. Fixed by giving
  the generator an explicit `[since, until)` (`build_for_period`) and pushing the upper bound down
  into `vitals_service.history_since` and `medication_service.adherence_for_patient`.
  **If you add a data source to a summary, give it the `until` bound too.**
- **`period_start` is midnight, `period_end` is not.** The truncated start is what makes
  regeneration idempotent; truncating the *end* would drop Sunday's visit from the report generated
  on Sunday evening. Monthly is the exception — a closed calendar month, both bounds on the 1st.
- **A report is a record.** The narrative is frozen as JSON at generation time and the PDF is
  re-rendered from that snapshot on every fetch — Phase 4's invoice rule, unchanged, and no blob
  column. A test proves an existing report does not change when new readings arrive while a live
  summary does.
- **One report per patient per kind per period**, unique constraint *and* a lookup before insert.
  Re-generating refreshes the row rather than duplicating it, so the scheduler can fire twice and the
  demo's "Generate report" button stays honest on the fifth press. Refreshing does not re-notify — a
  regenerated document is not news.
- **`run_for_all` swallows a per-patient failure and continues.** A run that abandons twenty-seven
  families because of one is a worse bug than the one it gave up on.
- **No new templating engine.** Reports use `string.Template` + hand-escaped HTML in
  `app/templates/reports/report.html`, exactly as `billing_service` does for invoices. Jinja2 is not
  installed and was not added.
- **The scheduler is wiring and is tested as such.** `app/scheduler.py` registers two APScheduler
  cron jobs (Sunday 18:00 IST, 1st at 06:00 IST, `ZoneInfo("Asia/Kolkata")`, misfire grace so a
  sleeping laptop still produces the report once). The *bodies* are `report_service.run_weekly/
  run_monthly`, plain functions the tests call directly. **Two replicas would both fire** — moving
  these to a worker is a Phase 11 concern and is noted below.
- **`FamilyDashboard.tsx` gained exactly one component and one divider.** The entire existing
  clinical dashboard is untouched below a "Detailed health record" rule. Verified in the browser that
  the summary renders above it and that Latest Vitals / Upcoming Visit / Nurse / Recent Visits are
  all still present.
- **`SegmentedControl` segments no longer wrap.** "This month" wrapped to two lines at the
  constrained desktop width and distorted the control's height. A wrapping segment label is always
  wrong, so `whitespace-nowrap` went into the primitive rather than the call site.
- **287 backend tests** (was 210) and **61 Vitest** (was 56). Verified live in Chrome at
  375/768/1024/1440, zero console errors, three genuinely different windows, PDF 200 with a bearer
  token and 401 without, and the 148/92 path still raising an alert the summary immediately notices.

#### ⚠️ Not yet exercised against the real provider

Every Groq path is tested against a **monkeypatched `httpx`**. No request has ever been made to
`api.groq.com` — the founder has not supplied a key yet, and steps 1–3 did not need one. What is
proven is that the platform is correct and complete *without* one. When the key arrives, set
`GROQ_API_KEY` and confirm: a real completion clears the four gates, `source` flips to `assisted`,
and a deliberately slow network still falls back inside 2s.

#### Deliberately deferred out of Phase 6

- **Reports are family-facing only.** There is no admin view of generated reports and no "email this
  report" action — `notification_delivery` (Phase 3) is the seam for the latter when Phase 10 does
  notification routing.
- **No report for a patient with no data yet.** `run_for_all` generates one for every active patient
  including brand-new ones, whose report honestly says no checks were recorded. That is correct but
  slightly odd as a first impression; a "skip until there is something to say" rule belongs with
  Phase 10's onboarding flow.
- **The scheduler is in-process.** Fine for one machine; wrong for two replicas. Phase 11.

---

### Phase 7 — AI assistant, family + admin → `8d91748`

- **The model never queries the database.** `services/assistant_context.py` assembles a role-scoped
  **context pack** and that pack is the only thing a model ever sees. Authorization therefore happens
  while the pack is *built*, not while the answer is *written* — there is no prompt instruction to
  disobey, because another family's patient was never in the context. `build_family_pack` refuses to
  take a `patient_id` at all; the router resolves it through `authorize_patient` first.
- **⚠️ §2.3's intent list was never supplied**, so the 14 intents are `ASSUMED` and live in one file,
  `services/assistant_intents.py`. Same treatment as `core/pricing.py`. **Reconciliation table below.**
- **The deterministic fallback is the product.** Built and tested first, ships alone, and every
  intent is proven to answer with `GROQ_API_KEY` unset — parametrized over the catalogue, so an
  intent cannot be added without a test. The Groq path came last and is a polish pass.
- **The family pack is itself written in the family's vocabulary**, not just the answers composed
  from it. That turns Phase 6's banned-word gate from a trap into a near-certainty: a model copying a
  phrase straight out of the context cannot reintroduce a word the summary generator avoids. A test
  asserts `contains_clinical_language(pack.render()) is None`.
- **A family answer never quotes `Alert.message`.** `alert_service.build_alert_message` writes
  "Systolic blood pressure 148 mmHg (above configured threshold 140 mmHg)" — three banned words in
  one sentence. `breached_parameters` are translated through the new
  `summary_service.plain_metric_label()` and de-duplicated, because both halves of a blood pressure
  share one spoken name. **Admin answers use `alert_service.METRIC_LABELS` unchanged** — admins are
  clinical staff and "systolic" is the correct word for them.
- **Four gates stand between a model and a reader**, in `assistant_service`, not `llm_client` — the
  client is transport, the service owns meaning. (1) **no number outside `pack.numbers()`** ∪ the
  deterministic answer, (2) no banned vocabulary — **family only**, (3) no advice register, (4)
  length. Gate 1 is the analogue of Phase 6's rule and the one that matters. Gate 2 being family-only
  is asserted both ways: the same "systolic" wording is discarded for a family and **kept** for an
  admin.
- **The emergency intent short-circuits before the pack is built and never reaches a model.** Matched
  first, outside the scoring, returning a fixed **108 → nurse → DoorDoctor** escalation. Proven with
  a monkeypatch that raises if `complete` is called. Matching is **phrases only** — a bare "help"
  false-positives on "can you help me read my bill?", and a bare `108` false-positives on a blood
  sugar of 108, so the catalogue matches `call 108` / `dial 108` / `phone 108` and nothing barer.
  Both cases are pinned by tests.
- **No second LLM client.** `llm_client.complete()` is called with `ASSISTANT_TIMEOUT` (8s) instead
  of `SUMMARY_TIMEOUT` (2s), and a test asserts the assistant passes its own budget.
- **Nurses have no assistant.** Decided explicitly with the founder; `require_family_or_admin` plus a
  test that pins the 403 on all three routes, so it is explicit rather than accidental. A nurse
  assistant needs its own pack and intents — Phase 10.
- **Retention is access scoping, not redaction.** Nothing in an `assistant_messages` row is a
  credential (unlike Phase 3's reset tokens), so redacting would destroy the feature and protect
  nobody. `GET /assistant/conversations` filters `user_id == current_user.id` and **no route lets an
  admin read another user's history** — three tests, including one proving a second family sees an
  empty list. Erasure is deferred to Phase 10's consent/audit/Privacy work.
- **Rate limited at 30 questions per user per hour** through the existing `core/ratelimit.py`
  (`ASSISTANT_PER_USER`). Already reset per-test by the autouse fixture, so it cost no plumbing.
- **No new process-global cache**, deliberately: a summary repaints from identical inputs, an
  assistant question is different every time. If that ever changes, register it in
  `clean_process_state` or test order will decide test outcomes.
- **365 backend tests** (was 287) and **71 Vitest** (was 61). Verified live in Chrome at
  375/768/1024/1440 for both roles, zero console errors. The admin thread reports **MRR ₹2,30,250
  across 20 active subscriptions** and **Sanjay Dutta past due** — matching the Phase 5 ledger
  exactly, because the pack borrows `billing_service.revenue_summary` rather than re-querying it.
- Fixed on the way: readings were prefixed with the patient's name *per measurement* ("Lakshmi's
  blood pressure…, Lakshmi's heart rate…, Lakshmi's blood sugar…"), now bare phrases with the caller
  owning the sentence and **no pronoun at all** — `Patient.gender` records a gender, not pronouns.
  Pluralisation across every admin answer ("1 visits", "1 nurses on the roster"). "a RN/ANM" →
  "a qualified RN/ANM", which sidesteps article agreement for any credential string. `scrollIntoView`
  is feature-detected — absent in jsdom, and a scroll convenience must never throw in a render effect
  and blank the thread. The server's `disclaimer` was returned and never rendered; it now closes the
  panel. `LinkButton` gained the `icon` prop `Button` already had.

#### ⚠️ Reconcile with the real §2.3 — everything below is invented

All of it lives in **one file**, `backend/app/services/assistant_intents.py`:

| Value | Assumed | Confidence |
|---|---|---|
| The 14 intents themselves | 8 family · 5 admin · 1 shared, plus `emergency` and `unknown` | derived from what the data model can answer; the *coverage* is defensible, the *list* is invented |
| Intent ids and titles | `latest_readings`, `medicines`, `needs_attention`, … | invented |
| Starter questions (the chips) | "What were her last readings?" etc. | invented — these are user-visible copy |
| Match phrases and keywords | per intent | invented |
| `PHRASE_WEIGHT` 4 · `KEYWORD_WEIGHT` 1 · `MATCH_FLOOR` 2 | scoring | invented, tuned against the seeded data |
| Emergency phrase list | 25 phrases | invented; **the 108 → nurse → admin escalation itself is recorded** |
| `ASSISTANT_PER_USER = (30, 3600)` | rate budget | invented |
| Question cap of 500 characters | schema | invented |

The **escalation order (108 → nurse → admin)**, the **8-second timeout**, the **role split
(family + admin)** and the **"never diagnose, never touch medication, always close with the
disclaimer"** rules are all recorded in the plan and are *not* assumed.

#### Deliberately deferred out of Phase 7

- **No nurse assistant** — see above. Phase 10.
- **No erasure of stored exchanges.** Phase 10, with consent and the audit log.
- **The `AI_ASSISTANT` entitlement is not enforced.** It is `True` on all five plans, so a gate is a
  no-op today, and Phase 4 deferred point-of-use entitlement enforcement until §3 is reconciled.
  Consistent with that deferral, not an oversight.
- **The assistant is not on the family dashboard as a panel**, only as a link under the summary.
  Phase 6's layout was left alone deliberately; the assistant has its own screen.

---

### Phase 8 — public marketing site, lead capture, SEO → `PENDING`

- **Decisions taken with the founder before any code (2026-08-22):** §3 was never supplied, and the
  answer was **ship the `ASSUMED` values as they stand, label nothing**, and **leave the 4 / 8 / 12
  visit entitlements alone**. Both mean the same thing operationally: **Phase 8 does not touch
  `core/pricing.py`.** It reads it. The reconciliation tables under Phases 4 and 5 stay exactly as
  they were — the invented values are now *published*, which raises the stakes of reconciling them
  but does not change what needs reconciling.
- **No price is written anywhere in the frontend.** `GET /public/plans` (new, unauthenticated) calls
  the *same two functions* authenticated `/plans` uses — `subscription_service.list_plans` +
  `serialize_plan`, minus the auth dependency. A test asserts the two payloads are **identical**, not
  merely similar, which is what stops a second serializer ever being written. A second test asserts
  the served prices equal `pricing.PLANS`, so the DB round-trip is verified rather than assumed.
  A third pins ₹2,500 / ₹3,500 / ₹4,500 as **literals** — every other test compares the API to
  `pricing.py` and would still pass if `pricing.py` itself were edited.
- **The pricing page is a page that loads data, and is treated as one.** `PricingGrid` owns skeleton,
  error and retry. Phase 2's rule does not stop applying because a page is trying to sell something.
  The "Recommended" treatment reads `plan.recommended`; the entitlement lines reuse Phase 4's
  `lib/plan.entitlementLines`. Nothing branches on a plan code, on either side of the wire.
- **`POST /leads` is the only unauthenticated write in the codebase**, and every unusual thing about
  it follows from that sentence: rate limited **per IP (10/hr) and per email (3/hr)** through the
  existing `core/ratelimit` — not a second limiter, because `clean_process_state` resets exactly one;
  honeypot (`company_website`) that returns **the same 201 and the same body** as a real submission,
  because a 400 tells a bot its script was detected; every string capped in the schema; and a fixed
  reply that never reveals whether an address has enquired before. `lead_service.create` returns
  `None` on a honeypot hit so the router's response shape cannot depend on whether the caller was a
  bot — a test asserts the two responses are byte-identical.
- **A new lead raises no notification, deliberately.** An unauthenticated endpoint wired to every
  admin's notification bell is a spam amplifier. The limiter caps the table; it should not also have
  to cap the bell. Leads surface as an unworked count on **Admin → Leads** instead.
- **Lead reads are admin-only** — a lead list is a list of named strangers and their phone numbers.
  Family 403, nurse 403, anonymous 401, all three pinned. `handled_by`/`handled_at` are stamped when
  a lead moves off `new` and **cleared when it moves back**, because a stale name on an unworked
  enquiry is worse than no name.
- **`/` changed owner, and it was decided rather than allowed to happen.** `RootRedirect` is deleted;
  `/` renders the public home **for everyone, signed in or not**, and the header swaps "Sign in" for
  "Go to dashboard". A signed-in family member who follows a link to `/pricing` must be able to read
  it, and a redirect at `/` but not at `/pricing` is an inconsistency someone has to remember.
  **`ProtectedRoute` is unchanged** — it still sends an unauthenticated visitor to `/login`, not `/`.
- **The `*` route lands inside `PublicLayout`**, so a wrong URL arrives somewhere with navigation
  rather than at a dead end. The 404 is `noIndex`.
- **⚠️ Helmet *appends* meta tags it does not manage**, so the static
  `<meta name="description">` in `index.html` plus a per-route one shipped **two conflicting
  descriptions on every public page**. Caught by looking at the rendered head in a real browser, not
  by any test. The static tag is gone and the verification script now asserts `count === 1` per
  route. `<title>` is fine — there can only be one, and Helmet replaces it.
- **⚠️ A signed-in visitor got a horizontally scrolling marketing site at 375px.** Every element in
  the public header is `shrink-0`, and "Go to dashboard" is one word longer than the signed-out
  buttons — 381px of content in a 375px viewport. Only reachable while signed in, which is why an
  ordinary responsive pass would have missed it. The label now shortens to "Dashboard" below `sm`.
  **If you add anything to that header row, re-check it at 375px in both auth states.**
- **No invented social proof, and the sections are built so it stays that way.** `FounderPair` is one
  component precisely so Saran Adhith (Founder & CEO) and Darren D'Souza (Co-Founder) cannot be split
  up or given unequal cards by a later edit. `/trust-and-safety` carries an explicit **"what we are
  not claiming"** section — no accreditation, no audit, no customer numbers — and `/about` says
  plainly that DoorDoctor is early. The JSON-LD is `Organization` with both founders and **no**
  `aggregateRating` or `review`: structured data is still a claim.
- **`SMALL` seeds no leads**, so all 365 pre-existing backend tests are untouched; `FULL` seeds six
  across five kinds and four statuses, written directly rather than through `lead_service.create` so
  they can be backdated — the same reason `business.py` backdates `paid_at`. A test asserts
  `handled_at >= created_at`, which is the thing a backdating seed gets wrong silently.
- **408 backend tests** (was 365) and **87 Vitest** (was 71).
- Verified live in Chrome: all 15 routes render with exactly one meta description, a real `h1`, a
  distinct title and a canonical; ₹2,500/₹3,500/₹4,500 monthly and ₹25,000/₹35,000/₹45,000 annual;
  ₹84/₹77/₹65 per resident per day; ₹2,800 per employee per month; exactly one Recommended badge;
  **journey 1 end to end** (enquiry → admin sees it → marks it contacted); the login back-link;
  a signed-in visitor staying on `/`; the 429 rendering as a sentence; and **no horizontal overflow
  at 375 / 768 / 1024 / 1440** with zero console errors.

#### Deliberately deferred out of Phase 8

- **Lead notifications and assignment.** No email to the team when a lead arrives, and no "assign to
  me". `notification_delivery` (Phase 3) is the seam for the first; Phase 10's ops screens are the
  place for the second.
- **No admin creation of an organization from a lead.** A corporate enquiry is captured and worked,
  but converting it into an `Organization` + subscription is still manual — Phase 4 deferred
  corporate self-service and Phase 10 owns the ops screens.
- **Lead erasure.** Same deferral as `assistant_messages`: it lands with Phase 10's consent record,
  audit log and Privacy & Data page. Deleting rows without those is a half-built promise.
- **`sitemap.xml` is hand-maintained.** Fourteen URLs, no build step. If the public route list grows
  much past this, generate it.
- **Prerendering.** The public site is client-rendered, so a crawler that does not execute JavaScript
  sees an empty shell. Every meta tag and the JSON-LD are set at runtime by Helmet. If organic search
  matters commercially, this needs SSR or a prerender step — that is a Phase 11-scale decision, not a
  marketing-copy fix, and it is flagged here rather than quietly ignored.

---

## ▶ Starting Phase 9 — Clinical features (§4.2–4.9)

**Read `docs/build-log/phase-8.md` for how the last phase was structured, then write
`docs/build-log/phase-9.md` before writing any code.**

Phase 8 closed the "credible demoable platform" line: a stranger can now find DoorDoctor, understand
it, see what it costs and enquire, and an admin works that enquiry in-app. Phase 9 is the first phase
that adds genuinely new *clinical* surface.

### What Phase 9 covers

Labs (`models/lab.py`, entitlement-driven panels, abnormal → alert + 24-hour follow-up task),
hospital booking + SLA queue, care manager (**1:20 shared / 1:10 dedicated — both recorded**) with
`CareInteraction`, the **Senior Safety Score** (deterministic 0–100, weights in one constant block,
every component stored so it is always explainable, a 10+ point drop in 30 days raises an alert),
PHQ-2 screening, telemedicine booking (Premium 2/month — **recorded**), wearables (`models/device.py`,
API-key ingest, `scripts/simulate_wearable.py`, SpO2 <90% or HR out of range → the documented three
actions), and escalation events with a visible parallel-notification timeline plus a permanent
"In an emergency, call 108" block on every clinical screen.

### Reuse these — do not rebuild them

- **`subscription_service.entitlement()`** for lab panels, telemedicine limits and the care-manager
  ratio. `Plan.entitlements` is already a JSON column and **nothing anywhere branches on a tier
  name**. Keep it that way — Phase 4 built it specifically for this phase.
- **`alert_service.create_threshold_alert`** for every new alert source (abnormal lab, safety-score
  drop, wearable breach). Nothing writes an `Alert` row directly; the Phase 5 seed depends on that
  being true.
- **`core/pricing.py`** for the add-on prices. Blood panel ₹499 and pill organiser ₹199 are already
  there with `InvoiceLineKind.ADDON` ready — **lab ordering is the natural first buyer**, and Phase 4
  deferred the add-on purchase flow expecting exactly this.
- **`notification_delivery`** (Phase 3) for the escalation timeline's channels. One seam, not two.
- **`components/ui/`** and `components/charts/chartTheme.ts` for every new screen and chart.
- **`summary_service.plain_metric_label()`** whenever a clinical fact has to be said to a family.

### Things that will bite

- **Quota enforcement is still not wired at the point of use**, and Phase 9 is where it stops being
  free to ignore: telemedicine ("2 per month") and lab panels are *countable* entitlements whose
  whole point is a limit. The engine and its tests are ready (`consume_quota`). But §2.4's recorded
  visit volume is **double the assumed top visit tier**, so enforcing *visits* would refuse the
  visits the demo is specified to contain. **Enforce telemedicine and labs; leave visits unenforced**
  and say so — that is the split the evidence supports.
- **The care manager is not a fourth `UserRole`.** The plan is a profile on an admin user, which
  keeps the three-way route guard intact. Cheap to agree on early; expensive to change later.
- **`Alert` still has no resolution note column.** §8's journey 3 says the admin "resolves it with a
  note" and there is nowhere to put one. Phase 10 owns the alert queue, but if Phase 9 adds alert
  sources it may be the right moment to add the column.
- **The Senior Safety Score must store every component, not just the total.** A score a family cannot
  have explained to them is worse than no score. Same discipline as Phase 4's derived institutional
  bands: put the arithmetic in one constant block and let a test re-run it.
- **A wearable ingest endpoint is the second unauthenticated-ish surface** after `POST /leads`. It is
  API-key authenticated rather than open, but treat it with the same suspicion: cap the payload, rate
  limit it, and never let device-supplied text reach a log.

### Do not break these

- Patient 1 is Lakshmi, nurse 1 is Anitha, **Anitha holds exactly one open visit today**, and
  **Lakshmi carries no open alert**. `tests/test_seed.py` pins all four — and Phase 9 adds new alert
  sources, which is exactly how the last one gets broken.
- `tests/conftest.py` seeds `SMALL`, sets `GROQ_API_KEY=""` and `REPORTS_SCHEDULER_ENABLED=false`.
- The autouse `clean_process_state` fixture resets the rate limiter and the summary cache. **Register
  any new process-global there.**
- **`core/pricing.py` is read, never written** — unless the real §3 finally arrives, in which case it
  is the one file that changes.
- `/public/plans` and authenticated `/plans` must stay byte-identical. A test enforces it.
- Backend **408**, Vitest **87**. The counts only grow.

---

## Open items and deferrals

- **README image links.** `README.md` references `docs/screenshots/*.png`, which the history rewrite
  deleted. Either regenerate the screenshots (the app now looks materially different anyway, so
  these are stale) or drop the links. Worth doing as part of Phase 11 docs, or sooner if the founder
  wants the README presentable.
- **Care manager role.** §4.4 gives care managers their own ratios and worklist. Plan is to model
  them as a profile on an admin user rather than a fourth `UserRole`, which keeps the three-way
  route guard intact. Flagged for Phase 9; cheap to agree on early.
- ✅ **Login footer back-link** — done in Phase 8. `/` is the public home now, so the link goes
  somewhere instead of looping.
- ✅ **Business documents / prices** — done in Phase 4. Everything lives in
  `backend/app/core/pricing.py`. **§3 was never supplied, so the invented values are listed in the
  Phase 4 results above and must be reconciled before Phase 8 publishes a pricing page.** Phase 8
  imports these constants; it must not restate a number.
- ✅ **Entitlements as data** — done. `Plan.entitlements` is a JSON column read through
  `subscription_service.entitlement()`. Phase 9 reads it for care-manager ratios (1:20 shared,
  1:10 dedicated), telemedicine limits and lab panels. Nothing branches on a tier name; keep it
  that way.
- ✅ **Seed data is thin on the clinical side** — done in Phase 5. 28 patients, 14 nurses, 1,453
  visits and 1,290 readings across 90 days.
- ✅ **The billing seed survived the move.** `business.seed_business()` still builds its history by
  calling `billing_service` and `subscription_service`, so the loyalty and credit arithmetic is
  re-proved on every seed run. Keep it that way.
- **`/visits` returns the newest 250 visits, newest first**, so the admin visit table now leads with
  next week rather than today. Phase 10's visit board should replace it with a windowed, paginated
  query rather than raising the cap again.
- **The report scheduler is in-process (Phase 6).** APScheduler runs inside the API process, so two
  replicas would both generate Sunday's reports. Idempotency means the result is still one report per
  patient, but the work is done twice. Move to a worker in Phase 11 alongside Postgres.
- ⚠️ **No Groq request has ever been made (Phases 6 and 7).** Every LLM path in the codebase — the
  summary rewrite and now the assistant — is proven against a monkeypatched `httpx`/`complete`, and
  the platform is verified complete and correct with **no key at all**, which is what the definition
  of done required. The founder said on 2026-08-22 they would supply a key; it has not arrived yet.
  When it does, set `GROQ_API_KEY` and confirm three things: a real completion clears the four gates,
  `source` flips to `assisted` in both the summary and the assistant, and a deliberately slow network
  still falls back inside 2s / 8s respectively. Nothing is blocked in the meantime.
- ✅ **§2.3's intent list** — resolved the Phase 4 way. Never supplied, so the 14 intents are
  `ASSUMED` and isolated in `backend/app/services/assistant_intents.py`. Reconciliation table in the
  Phase 7 results above; reconciling is a one-file change. **Do not inline an intent string anywhere
  else.**
- ✅ **Plain-language summary and reports** — done in Phase 6. `summary_service` owns the vocabulary
  rule; `report_service` freezes and re-renders. Phase 7 reused `llm_client` and the four-gate
  validation shape rather than building either again, exactly as intended.
- ✅ **AI assistant** — done in Phase 7. `assistant_context` is the security boundary,
  `assistant_fallback` is the product, and the Groq path is a gated polish pass behind the same
  single `llm_client`.
- ✅ **Public marketing site and lead capture** — done in Phase 8. Fourteen public routes plus a
  404 under `PublicLayout`, prices served from `core/pricing.py` over `GET /public/plans` so no
  rupee figure is typed into the frontend, and `POST /leads` rate-limited and honeypot-protected
  behind an admin-only queue.
- **The public site is client-rendered.** Every meta tag and the JSON-LD are set at runtime by
  Helmet, so a crawler that does not execute JavaScript sees an empty shell. If organic search
  matters commercially this needs SSR or a prerender step — a Phase 11-scale decision, recorded here
  rather than quietly ignored.
- **`frontend/public/sitemap.xml` is hand-maintained.** Fourteen URLs and no build step. If the
  public route list grows much past this, generate it.

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
