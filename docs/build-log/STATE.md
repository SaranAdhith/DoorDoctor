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
| 7 | AI assistant (family + admin) | ⬜ **next** |
| 8 | Public marketing site + leads | ⬜ |
| 9 | Clinical features (labs → escalation) | ⬜ |
| 10 | Trust, GPS, medication, community, consent, ops, notifications | ⬜ |
| 11 | Multi-family, hardening, tests, docs | ⬜ |

Phases 1–8 are the "credible demoable platform" line. A finished phase 8 beats a broken phase 11.

---

## How to verify (run before every commit)

```bash
cd backend  && .venv/bin/python -m pytest          # 287 passing today; the count only grows
cd backend  && .venv/bin/python -m app.seed        # must run clean (~5.4 s, full population)
cd backend  && .venv/bin/python -m app.seed --small        # the dataset the test suite uses
cd backend  && .venv/bin/python -m app.seed --demo-reset   # rewind the 148/92 path between demos
cd backend  && .venv/bin/python -m app.billing --generate-invoices --dry-run   # previews, writes nothing
cd frontend && npx tsc -p tsconfig.json --noEmit   # zero errors, no `any`, no @ts-ignore
cd frontend && npm run build                       # clean
cd frontend && npx vitest run                      # 61 passing today
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
| `ASSISTANT_ENABLED` | Phase 6 | `true` | Master switch for every LLM call |
| `REPORTS_SCHEDULER_ENABLED` | Phase 6 | `true` | **`false` in `tests/conftest.py`** — `TestClient` runs the lifespan |

Backend venv is `backend/.venv` (Python 3.13.12). Node v20.20.2. WeasyPrint's system libraries
(pango, cairo, harfbuzz, gobject) are verified present for Phase 6. PyPI and npm are reachable.

## Dependencies added so far

| Where | Package | For |
|---|---|---|
| frontend | `lucide-react` | Icons, replacing emoji (Phase 2) |
| backend | `weasyprint` 69.0 | Invoice PDFs (Phase 4) — **pulled forward from Phase 6** |
| backend | `apscheduler` 3.11.3 | Weekly/monthly report scheduling (Phase 6) |

Still planned: `alembic` (backend); `react-helmet-async`, `@playwright/test` (frontend).
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

## ▶ Starting Phase 7 — AI assistant, family + admin (§2.3)

**Read this whole section first, then the plan file's Phase 7 paragraph (line 256), then write
`docs/build-log/phase-7.md` before writing any code.** Everything below is what a cold session
would otherwise have to re-derive by reading the codebase.

### ⚠️ FIRST — §2.3's intent list was never supplied

The plan says the fallback "answers every **listed** family and admin intent". That list lives in
§2.3 of the founder's build prompt, **which is not in the repo and was never pasted into a build
session.** This is the same class of gap as §3 (pricing), which Phase 4 hit and resolved by
inventing values, isolating them in one file and marking them `ASSUMED`.

Do the same thing here, and do it deliberately:

1. **Ask the founder for §2.3's intent list.** It is one message and it removes the guesswork.
2. If it does not arrive, derive the intents from what the data model can actually answer, put them
   in **one module** (`services/assistant_intents.py` or a constant block at the top of
   `assistant_fallback.py`), and mark them `ASSUMED` in the same style as `core/pricing.py`. Add a
   reconciliation table to STATE.md exactly as Phase 4 did.
3. **Do not scatter intent strings across the service.** The reconciliation has to be a one-file
   change when the real list appears.

A defensible starting set, derived from what the platform genuinely knows — every one of these is
answerable from existing data with no new tables:

| Role | Intent | Answerable from |
|---|---|---|
| family | How has Amma been this week? | `summary_service.build_deterministic` |
| family | What were the last readings? | `vitals_service.latest_for_patient` |
| family | Is she taking her medicines? | `medication_service.adherence_for_patient` |
| family | When is the next visit? | `visit_service` upcoming |
| family | Who is the nurse, and are they verified? | `Nurse.credential`, `verification_status` |
| family | What was that alert about? | `alert_service`, `Alert.breached_parameters` |
| family | What does my plan cover / what have I paid? | `subscription_service.entitlement`, `billing_service` |
| family | Something is wrong right now | **the emergency path — 108, then nurse, then admin** |
| admin | Which patients need attention today? | open alerts by severity |
| admin | What is on the board today? | `visit_service.list_today_visits` |
| admin | Which visits are unassigned? | today's board, `nurse_id is None` |
| admin | How is nurse X doing? | `admin_service.list_nurses`, open visit counts |
| admin | What is MRR / who is past due? | `billing_service.revenue_summary` |

### Build order — the fallback first, exactly as Phase 6 did

1. **`services/assistant_context.py`** — assembles the role-scoped **context pack**. This is the
   security boundary and it is worth its own module: family packs contain only patients that pass
   `authorize_patient`, admin packs are org-wide but carry no billing detail a nurse could reach.
2. **`services/assistant_fallback.py`** — deterministic intent matcher over that pack. Built and
   tested **first**; answers every intent with no key and no network.
3. `models/assistant.py`, `services/assistant_service.py`, `routers/assistant.py`.
4. **Only then** the Groq path, behind the **existing** `llm_client.complete()` with
   `llm_client.ASSISTANT_TIMEOUT` (8s).
5. Frontend last.

**Verify with `GROQ_API_KEY` unset before calling the phase done** — that is the demo configuration,
and Phase 6 proved the pattern works.

### What Phase 6 already built — reuse it, do not rebuild it

```python
# backend/app/services/llm_client.py — the single LLM boundary. DO NOT WRITE A SECOND ONE.
complete(*, system: str, user: str, timeout: float,
         max_tokens: int = 400, temperature: float = 0.2) -> str | None
available() -> bool                    # settings.assistant_enabled and a non-empty key
SUMMARY_TIMEOUT = 2.0 ; ASSISTANT_TIMEOUT = 8.0
```

It **never raises** — no key, disabled, timeout, 500, malformed body and empty completion all return
`None`, so there is exactly one fallback path. It **never logs the prompt or the completion**; a test
asserts a patient name never reaches the log. Keep that property.

- **The validation shape to copy** is `summary_service._rewrite_is_acceptable`: gates live in the
  **service**, not the client — the client is transport, the service owns meaning. Fall back
  silently, and report `source` (`deterministic` / `assisted`) honestly in the payload so the demo
  can *show* the fallback rather than assert it.
  The assistant needs different gates. The strongest one available here is the analogue of Phase 6's
  "no invented numbers": **no claim outside the context pack.** At minimum, every number in the
  answer must appear in the pack.
- **`summary_service.contains_clinical_language(text) -> str | None`** — the banned-word guard.
  Apply it to **family-facing** assistant answers; §2.3 does not require it explicitly, but a
  platform that says "blood pressure" on the dashboard and "systolic" in the assistant has two
  voices. Do not apply it to admin answers — admins are clinical staff.
- **`summary_service.build_deterministic(db, patient, window)`** already produces a plain-language
  view of one patient's window. Use it *in* the family context pack rather than assembling the same
  facts a second way.
- **`_SummaryCache`** (content fingerprint + TTL + `reset()`) is the caching pattern if assistant
  answers need it. **Register any new process-global cache in the autouse `clean_process_state`
  fixture in `tests/conftest.py`**, or test order will decide test outcomes.

### Proposed API surface

```
POST /assistant/ask          {question, patient_id?}  -> {answer, source, intent, disclaimer, ...}
GET  /assistant/conversations                          -> the caller's own history
GET  /assistant/suggestions?patient_id=                -> role-scoped starter questions
```

Role handling follows the existing precedent: `CurrentUser` + `authorize_patient` for anything
patient-scoped. **Someone else's patient is a 404, never a 403** — a 403 confirms the record exists,
which is enough to learn that a named person is a DoorDoctor patient. `authorize_report` in
`core/dependencies.py` is the most recent worked example.

### Things that will bite

- **Rate limit `/assistant/ask`.** `core/ratelimit.py` already exists (Phase 3, sliding window,
  raises `TooManyRequestsError` → 429 + `Retry-After`) and is already reset per-test by the autouse
  fixture. An unmetered LLM endpoint behind a login is the obvious way to burn a free Groq tier.
- **Conversation persistence is a privacy decision, not a schema decision.** `models/assistant.py`
  will store a family member's questions about a named patient. Phase 3 set the precedent that
  sensitive values are redacted *before* they are persisted (`notification_delivery.deliver(...,
  sensitive=[...])`, and a test proves the raw token never lands in a stored body). Decide the
  retention stance explicitly and write it in the docstring.
- **Nurses.** The plan names *family + admin* only. Decide explicitly whether a nurse gets an
  assistant; if not, `require_family_or_admin` already exists. Do not leave it accidental.
- **The emergency intent must be matched deterministically and must never reach the model.**
  "I think she is having a stroke" is not a question to send to a 70B model with an 8s timeout and a
  fallback path. Match it in `assistant_fallback` first, return **108 → nurse → admin** immediately,
  and short-circuit before any LLM call.
- **The suite is ~3 minutes**, almost all bcrypt (~180 logins × 0.73s). Run targeted files while
  iterating (`pytest tests/test_assistant.py -q`) and the full suite before committing.

### Do not break these

- Patient 1 is Lakshmi, nurse 1 is Anitha, **Anitha holds exactly one open visit today**, and
  **Lakshmi carries no open alert**. `tests/test_seed.py` pins all four.
- `tests/conftest.py` seeds `SMALL` and sets `GROQ_API_KEY=""` and `REPORTS_SCHEDULER_ENABLED=false`.
- **To test the assisted path, monkeypatch `llm_client.complete`** — copy the `assisted` fixture at
  the bottom of `tests/test_summary.py`, which also hands back a call counter for cache assertions.
  `tests/test_llm_client.py` shows how to fake `httpx` responses without a network.
- The autouse `clean_process_state` fixture resets the rate limiter and the summary cache.

### Definition of done for Phase 7

- Every intent answered **with `GROQ_API_KEY` unset**, proven by test.
- A family user asking about another family's patient is **refused** (404), proven by test.
- The emergency path returns 108 → nurse → admin without touching the model, proven by test.
- Backend test count grows from **287**; Vitest from **61**.
- Verified live in Chrome at 375 / 768 / 1024 / 1440, zero console errors.
- `docs/build-log/phase-7.md` written before the code and closed with an "As executed" section.
- One conventional commit on `main`, then the hash recorded in the phase table above.


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
- **No Groq request has ever been made (Phase 6).** Every LLM path is proven against a monkeypatched
  `httpx`, and the platform is verified complete with no key at all. Ask the founder for the key
  before Phase 7 reaches its step 3.
- ✅ **Plain-language summary and reports** — done in Phase 6. `summary_service` owns the vocabulary
  rule; `report_service` freezes and re-renders. Phase 7 reuses `llm_client` and the four-gate
  validation shape rather than building either again.

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
