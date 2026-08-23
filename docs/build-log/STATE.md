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
| Source of facts | **The build prompt is the source of truth.** No business documents exist in the repo. Every price, tier, ratio and founder name comes from the prompt verbatim. Invent no traction, testimonials, customer counts, certifications or partner logos — DoorDoctor is pre-launch. **Amended 2026-08-23 — see "Social proof" below.** |
| Social proof | The founder asked for review and tie-up sections on the home page, then asked (2026-08-23) for the sample content to read as real and for the on-page "not real" notices to be removed. Both done. **The reviews and partner organisations in `frontend/src/content/social-proof.ts` are invented and now carry nothing on the page marking them as such** — that file's header comment is the only remaining record, so read it before editing and do not delete it. Partner names are deliberately fictional so no real hospital's mark is used without an agreement. `SHOW_SOCIAL_PROOF = false` removes both bands. No `aggregateRating` JSON-LD, ever — `src/test/socialProof.test.tsx` locks that. **Do not delete these sections as a locked-decision violation; the founder asked for them twice.** |
| Checkpointing | Report at each phase boundary and continue. No waiting for approval between phases. |
| Git | Commit directly on `main`, one conventional commit per phase boundary, full suite green before each. **Commit promptly** — see the incident note below. **One author.** No `Co-Authored-By` trailer on any commit, and no tool or assistant attribution in a commit message. History was rewritten on 2026-08-23 to strip 36 such trailers, which is why every commit hash recorded below is newer than the work it names. A local `.git/hooks/commit-msg` deletes the trailer if a tool adds one, but hooks are not cloned, so this row is the rule. |
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
| 1 | Terminology refactor (caregiver→nurse, coordinator→admin) | ✅ done — `b128c8a` |
| 2 | Design system, UI primitives, sidebar navigation | ✅ done — `44ba9d8` |
| 3 | Forgot password + login rebuild | ✅ done — `fc7a3a4` |
| 4 | Subscriptions, plans, billing, quotas, referrals, loyalty | ✅ done — `ef01276` |
| 5 | Realistic seed data | ✅ done — `c780dd4` |
| 6 | Plain-language summary + reports | ✅ done — `688c767` |
| 7 | AI assistant (family + admin) | ✅ done — `b477574` |
| 8 | Public marketing site + leads | ✅ done — `817fb8e` |
| 9 | Clinical features (labs → escalation) | ✅ done — `43693d9` |
| 10 | Trust, GPS, medication, care circle, consent, ops, notifications | ✅ done — `dcbd711` |
| 11 | Multi-family, hardening, tests, docs | ⬜ **next** |

Phases 1–8 are the "credible demoable platform" line. A finished phase 8 beats a broken phase 11.

---

## How to verify (run before every commit)

```bash
cd backend  && .venv/bin/python -m pytest          # 804 passing today; the count only grows
cd backend  && .venv/bin/python -m app.seed        # must run clean (~5.4 s, full population)
cd backend  && .venv/bin/python -m app.seed --small        # the dataset the test suite uses
cd backend  && .venv/bin/python -m app.seed --demo-reset   # rewind the 148/92 path between demos
cd backend  && .venv/bin/python -m app.billing --generate-invoices --dry-run   # previews, writes nothing
cd frontend && npx tsc -p tsconfig.json --noEmit   # zero errors, no `any`, no @ts-ignore
cd frontend && npm run build                       # clean
cd frontend && npx vitest run                      # 133 passing today
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
| `UPLOAD_ROOT` | Phase 10 | `app/uploads` | Where dose photos are written. **Pointed at a temp dir in `tests/conftest.py`** — otherwise the suite writes patient photographs into the source tree. Never served statically |

Backend venv is `backend/.venv` (Python 3.13.12). Node v20.20.2. WeasyPrint's system libraries
(pango, cairo, harfbuzz, gobject) are verified present for Phase 6. PyPI and npm are reachable.

## Dependencies added so far

| Where | Package | For |
|---|---|---|
| frontend | `lucide-react` | Icons, replacing emoji (Phase 2) |
| backend | `weasyprint` 69.0 | Invoice PDFs (Phase 4) — **pulled forward from Phase 6** |
| backend | `apscheduler` 3.11.3 | Weekly/monthly report scheduling (Phase 6) |
| frontend | `react-helmet-async` 3.0.0 | Per-route SEO tags (Phase 8) |
| backend | `pillow` 12.3.0 | Dose photos: magic-byte validation and EXIF stripping (Phase 10). Already present as a WeasyPrint transitive; pinned because it is now imported directly, so **nothing was installed** |

Still planned: `alembic` (backend); `@playwright/test` (frontend).
**No `anthropic` — the provider is Groq via `httpx`.** Phase 6 added the Groq client and it needed
no new dependency, exactly as planned.

⚠️ **The backend venv has no `pip`** — it was created by `uv`. Install with
`uv pip install --python .venv/bin/python <package>`, not `.venv/bin/pip`.

---

## Phase results

### Phase 1 — terminology refactor → `b128c8a`
- 51 files rewritten, 16 paths renamed via `git mv` (history preserved), ~700 occurrences resolved.
- Grep audit: **0** hits for caregiver/coordinator outside `docs/build-log/`.
- Live smoke test: all three roles log in, `/admin/summary` and `/nurses` serve, old
  `/coordinator/summary` and `/caregivers` 404, and the 148/92 breach path runs end-to-end.
- Family-facing prose was written by hand, not substituted — "your admin" is wrong to say to a
  family member, so FamilyAlerts reads "Your DoorDoctor care team reviews and resolves alerts".
- Repaired column alignment the shorter words broke in the README architecture box and the
  DESIGN.md route map.

### Phase 2 — design system, primitives, navigation → `44ba9d8`
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

### Phase 3 — password reset, delivery channels, rebuilt login → `fc7a3a4`
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

### Phase 4 — subscriptions, billing, quotas, referrals, loyalty → `ef01276`

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
- Phase 1's commit was rewritten `b128c8a` → `b128c8a`. **Content survived intact.**
- The accompanying reset **discarded uncommitted changes to tracked files**, costing part of the
  Phase 2 work, which was redone. Untracked new files were unaffected.
- `assets/` and `docs/screenshots/` are gone from the working tree. The founder has since restored
  the README logo (`ea061e6`). `frontend/public/` logos were never touched, so the app UI is fine.
- The pre-rewrite commit is still reachable at `refs/original/refs/heads/main` if anything is needed
  back.

**Lesson applied: commit at every phase boundary promptly, and do not leave large amounts of work
uncommitted in the working tree.**

---

### Phase 5 — realistic seed data → `c780dd4`

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

### Phase 6 — plain-language summary, reports, the LLM boundary → `688c767`

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

### Phase 7 — AI assistant, family + admin → `b477574`

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

### Phase 8 — public marketing site, lead capture, SEO → `817fb8e`

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

### Phase 9 — clinical features → `43693d9`

Eight feature areas, committed in six stages rather than one drop. **623 backend tests** (was 408)
and **121 Vitest** (was 87).

- **Decisions taken with the founder before any code (2026-08-22):** §4.2–4.9 was never supplied, so
  **proceed with `ASSUMED` values**; the care manager is a **profile on an admin user, not a fourth
  role**; and `Alert` gets its **resolution note now** rather than in Phase 10.
- **`backend/app/core/clinical.py` is the single source of every clinical constant** — the sibling of
  `core/pricing.py`, importing nothing from the app. Lab panels and reference ranges, safety weights
  and bands, SLA durations, the wearable range and its three actions, PHQ-2, the escalation ladder.
  Three provenance markers, not two: `RECORDED` · `INSTRUMENT` (PHQ-2 — a published instrument, and
  **not** an assumption for the founder to reconcile away) · `ASSUMED`.
  **Reconciliation table below.**
- **`services/safety_score.py` contains no clinical constant, and a test proves it** by asserting the
  module's numeric literals and `clinical.py`'s values are disjoint. The one-file promise is a test,
  not a convention.
- **A component with no data is dropped, never scored zero.** No PHQ-2 on file must not read as
  "worst possible mood". Missing components are excluded and the scale is rescaled across what did
  have data, with `covered_weight` stored so the rescaling is visible; below
  `SAFETY_MIN_COVERED_WEIGHT` **no score is published at all**, because a number derived from one
  component looks exactly as authoritative as a real one. This is the single most likely way the
  feature could silently defame a patient, and it is pinned by four tests.
- **Every safety score stores its components, and a seed test re-runs the arithmetic** over all 132
  seeded rows: the weighted points must add to the score over the weight it claims to cover. A
  second test asserts the newest stored score equals what the live calculator produces from the same
  data — so a seeded number the calculator could not reproduce fails rather than looking plausible.
- **`alert_service.create_alert` is now the general path** and `create_threshold_alert` a wrapper
  over it. Three new sources (abnormal lab, safety drop, wearable breach) have no `Vital` to point
  at. Nothing outside `alert_service` builds an `Alert` row — the Phase 5 seed's exact count and the
  family ever hearing about an alert both depend on that.
- **One alert per clinical event, never per measurement.** A panel with four values out of range is
  one alert; a wearable reporting eight low readings in a minute is one alert, one escalation and
  one task. Eight escalations would bury the finding they were raised about.
- **Every `LabResult` stores the reference range it was judged against.** `clinical.py` is *meant* to
  be edited, and a range that moves must not silently re-flag a result somebody has already read and
  acted on. The range travels to the client too, so a flag is arithmetic the reader can re-run rather
  than an opinion.
- **Labs are the first buyer of Phase 4's deferred add-on flow.** `lab_service.order` resolves
  payment in one place — the plan's allowance first, then the recorded ₹499 add-on. Past the
  allowance the panel is **billed, not refused**: the add-on price exists so more is purchasable, and
  refusing would make ₹499 unreachable. `billing_service.charge_addon` issues the add-on its own
  invoice at the moment of purchase, because an add-on is not a billing period.
- **Telemedicine is the first genuinely enforced quota**, and the split is evidence-led rather than
  preferential: its "2 per month on Premium" is the one entitlement quantity §3 actually recorded,
  and nothing contradicts it. **Visits stay unenforced** because §2.4's recorded 16.7 visits per
  patient per month is double the assumed top tier of 12 — enforcing it would refuse the visits the
  demo is specified to contain. That argument lives in `consult_service` beside the call, not only
  here.
- **A cancelled consult refunds; a cancelled lab order does not.** Opposite rules for opposite
  reasons — a consult that never happened cost nothing, while a lab panel's sample and laboratory are
  spent the moment it is ordered. A no-show is not refunded either: the doctor's time was held.
  `quota_released` is stored so a replayed request cannot refund twice, and the refund returns to the
  period the booking was **made** in.
- **The recorded 1:20 / 1:10 care-manager ratios are enforced**, including on the seed — every
  assignment goes through `auto_assign`, so a roster that exceeded its own ratio would be a demo of a
  broken promise. `auto_assign` returns `None` rather than raising when the roster is full:
  onboarding must not fail because staffing is stretched.
- **A positive PHQ-2 opens a task and never an alert.** A low mood score is not a threshold breach,
  and dressing it as one would be a diagnosis this platform is not entitled to make. Both answers are
  stored, not the sum — a 3 made of (3, 0) is not the picture a (1, 2) is.
- **A device stores a sha256 of its key and returns the plaintext once.** A test walks every `devices`
  row and proves none of them holds a usable credential. Ingest is capped, per-device rate limited
  through the existing limiter, and logs the device id and counts only — a test injects a marker into
  a serial and asserts it never reaches a log. The response carries counts and **nothing about the
  patient**: a stolen device key must not become a health-record reader.
- **⚠️ "The documented three actions" were never documented.** §4.8 names them and never lists them.
  All three are derived and `ASSUMED` in `clinical.WEARABLE_ACTIONS`, so the founder corrects them in
  one place: a critical alert, an escalation contacting family and admin in parallel, and a task for
  the covering nurse inside the critical SLA.
- **The escalation timeline is data, not prose.** One `EscalationStep` per recipient per channel;
  steps sent together share a `sequence` so the UI draws a fan-out rather than implying a queue
  worked one at a time. **Step 0 is the recorded 108 rung and is advisory** — status `skipped`, and
  its detail says in words that DoorDoctor does not place the call. A timeline that implied otherwise
  would be the most consequential lie this product can tell.
- **Critical contact is SMS + email, not SMS + push.** `PushChannel.address_for` returns `None` until
  a mobile client ships, so a "dual-channel" promise made of SMS + push is one channel wearing two
  names. An unreachable channel is recorded as an attempt that could not be made, never omitted.
- **The SLA clock is stored — both budget and deadline — and a breach is stamped when observed**, so
  a booking that breached last week still says so after somebody edits the constants.
- **The clinical seed is `FULL` only.** `SMALL` — which `tests/conftest.py` seeds — is untouched, so
  all 608 pre-existing tests passed unchanged. Lakshmi is in `FULL` too, so the demo account still
  gets everything: a normal panel, a care manager, a device, two mood checks and a full-coverage
  score. **Her three invariants held** — no open alert, Anitha's single open visit, and the threshold
  engine still accounting for exactly 30 resolved and 4 open.
- **Four seed tests were updated, deliberately.** Their alert assertions were written when a
  threshold breach was the only source, so "all alerts" and "threshold alerts" were the same set. The
  30/4 assertion is now scoped to `vital_threshold_breach` — its actual subject — and the
  notification test derives its count from the open alerts rather than pinning a literal that only
  records how many features raise alerts.

#### Bugs this phase found and fixed

- **Two untimestamped readings of one metric in a single batch 500'd the whole ingest.** Both
  defaulted to the same instant, passed the database duplicate check separately, and then violated
  `uq_device_reading` on flush. De-duplication now covers the batch as well as the table.
- **Both alert screens white-screened on an abnormal lab result** — found in the browser, not by any
  test. `AlertCard`, `AdminAlerts` and `FamilyAlerts` each assumed every breached parameter carried a
  `threshold`. `BreachedParameter` declared it required, so TypeScript could not catch it: API
  payloads are not checked at the boundary. `lib/breach.ts` now renders all three shapes in one
  implementation, and 8 tests pin them. **If you add a fourth alert source, declare its shape there.**
- **The seed reported three abnormal lab panels and the database held one.** Panels were assigned by
  rotating the catalogue, which handed two of the three abnormal slots a lipid profile containing
  none of the analytes the seed knows how to push out of range. An assert now makes that impossible.
- **Safety-drop alerts were stamped with the real clock**, so drops detected against sixty-day-old
  scores all arrived this morning — the same class of bug `business.py` fixes for `paid_at`. Eight of
  the nine are now resolved rather than suppressed; they are genuine output of the recorded rule.
- **The family dashboard scrolled horizontally at 375 and 768px.** A grid item defaults to
  `min-width: auto` and refuses to shrink below its content's intrinsic width, and a Recharts SVG's
  is wide. **Pre-existing** — it reproduces on the pre-Phase-9 dashboard — but it is the primary
  mobile screen. `min-w-0` on the chart container *and* the grid cell: the constraint has to be
  released at every level between the grid and the SVG.
- **Two demo-data faults only a demo would reveal.** The demo patient's PHQ-2 was three days old, so
  the nurse screen correctly hid the questionnaire and the founder's own account could never show it;
  and her only monthly consult was already spent, so the demo family could not book one.

#### ⚠️ Reconcile with the real §4.2–4.9 — everything below is invented

All of it lives in **one file**, `backend/app/core/clinical.py`.

| Value | Assumed | Confidence |
|---|---|---|
| Safety-score **weights** (30/25/15/15/10/5) and the six components themselves | invented | the *components* are defensible — they are what the data model can actually measure; the *weights* are arbitrary |
| Safety **bands** (80 / 65 / 50) and their labels | invented | |
| `SAFETY_MIN_COVERED_WEIGHT` 40 · `SAFETY_MIN_READINGS` 3 · `SAFETY_ALERT_SATURATION` 6 · `SAFETY_CRITICAL_MULTIPLIER` 2 · `SAFETY_MOOD_LOOKBACK_DAYS` 90 | invented | |
| Safety-drop alert wording and **severity** (warning) | invented | the **10 points in 30 days** trigger is recorded |
| **Lab panel contents** — three panels, fourteen analytes | invented | |
| **Reference ranges** | ordinary adult reference intervals | not from the founder; they exist so a flag can be *explained*, and nothing derives treatment from them |
| Which flags count as abnormal, and the critical bounds | invented | abnormal → alert **+ 24-hour task** is recorded |
| Lab turnaround hours (24 / 24 / 48) | invented | |
| Consult **duration** 20 min · **cancellation window** 4 h · **max lead** 30 d · **min lead** 30 min | invented | the **2/month on Premium** allowance is recorded |
| `CONSULT_PLACEHOLDER_DOCTOR` | invented | no doctor roster is modelled — inventing a staffed calendar would be inventing staff |
| PHQ-2 **cadence** 30 d and **follow-up window** 48 h | invented | the questions, the 0–3 scale, the 0–6 total and the **cutoff of 3** are the **instrument's** — do not "reconcile" them |
| Wearable **HR range** 45–120 | invented | **SpO2 < 90%** is recorded |
| The **three wearable actions** | invented — all three | §4.8 names them and never lists them. **Ask again if the section ever arrives.** |
| Wearable caps: batch 50 · backdate 24 h · offline after 90 min · `DEVICE_INGEST_PER_DEVICE` 120/hr | invented | |
| **SLA durations** — critical 15 min · warning 60 min · info 24 h · hospital 60 min | invented | the ladder **108 → nurse → admin** is recorded |
| `TASK_DEFAULT_HOURS` 24 | invented | the lab's 24-hour follow-up is recorded |
| Emergency block wording | written here | the **number 108** and the ladder are recorded |

#### Deliberately deferred out of Phase 9

- **No nurse-side lab ordering or consult booking.** Both spend a family's allowance or add ₹499 to
  their invoice, so both are family-or-admin. A nurse requesting a panel on a visit is reasonable and
  belongs with Phase 10's nurse ops screens.
- **No admin UI to create a care manager.** `POST /care-managers` exists and is tested; the roster
  screen reads. Creating one is a seed or an API call — Phase 10 owns the ops screens.
- **The pill organiser add-on still has no buyer.** Blood panel ₹499 now has one; pill organiser ₹199
  is priced and unsold. Phase 10's medication work is the natural place.
- **Safety scores are not recalculated on a schedule.** They are computed live on read and stored only
  when an admin presses recalculate or the seed runs. The recorded 10-point drop rule therefore only
  fires on a stored calculation. `app/scheduler.py` (Phase 6) is the seam — a nightly job belongs
  there, and it is a Phase 11 concern along with moving the scheduler out of process.
- **No family-facing device registration flow beyond the API.** `POST /patients/{id}/devices` returns
  the key once and is tested; there is no screen that walks a family through pairing. The readings
  and the breach path are fully wired, which is what the demo needs.
- **Escalations are admin-only to work.** A family sees their own patient's escalations and the
  timeline, but cannot acknowledge or resolve. Correct, and worth stating.
- **Hospital bookings have no cancellation route.** `CANCELLED` is in the enum and the service
  refuses to move a cancelled booking, but nothing sets it.

---

### Phase 10 — trust, operations and notifications → `dcbd711`

Nine feature areas over **ten commits**. **804 backend tests** (was 623) and **133 Vitest**
(was 121). §4.10–4.18 was never supplied, exactly as §3, §2.3 and §4.2–4.9 were not — four for
four — so every invented value lives in one new file and has a reconciliation table below.

**The idea the phase is built around:** *a promise the platform cannot evidence is a promise it
should not make.* It cuts both ways, and the second half did most of the work: it forbids the
confident lie **and** demands the honest negative. `unavailable` is a first-class outcome, a
suppressed message is a recorded decision, a retained invoice is stated with its reason.

- **`backend/app/core/ops.py` is the third constants file**, sibling to `pricing.py` and
  `clinical.py`, and it imports nothing from the application. It *reads*
  `clinical.SLA_DURATIONS_MINUTES` rather than restating it, and a test pins that
  `ops.ALERT_SLA_MINUTES is clinical.SLA_DURATIONS_MINUTES`. A geofence radius and a quiet-hours
  window are operational, not clinical: `clinical.py` is the file a clinician reconciles, `ops.py`
  is the file an operator reconciles, and keeping them apart keeps the two conversations apart.
- **The audit log is append-only in the mapper, not by convention.** `before_update` and
  `before_delete` listeners raise, and both are tested. It stores the actor's **name frozen at write
  time**, because an erasure can remove the account that requested it and the entry has to survive
  that. `audit_service.record` never commits — an audited action that rolls back must not leave an
  entry claiming it happened.
- **`services/storage.py` is the only code in the repo that writes a file**, and a test asserts the
  app mounts no `StaticFiles` at all. Content-addressed, so the same photo twice is one file. Every
  image is re-encoded on the way in — **not for size, but because a dose photo taken in the
  patient's living room carries the patient's home GPS in its EXIF**. Format is decided by what
  Pillow could decode, never by the client's declared content type.
- **A credential is verified only with a verifier and a date.** `NurseCredential.is_verified` is
  defined as all three, so hand-editing the enum produces no badge a family reads as checked, and a
  test proves the family projection agrees. The **two projections live side by side in one file** so
  the difference is visible at a glance: a family sees the issuing body and who checked it, never a
  registration number, and the visit count is scoped to *their own patient* — 240 visits this
  quarter is a fact about twenty other households.
- **GPS is measured, and `unavailable` is reachable three ways**, each a true sentence: no fix, no
  recorded home, or **a fix whose own accuracy is worse than the fence**. That last one is the case
  that would quietly turn the feature into decoration — coordinates 20 m from the door with a ±500 m
  error are inside the circle and prove nothing. `demo/unverified` is gone from the schema, the seed
  and the tests.
- **An out-of-range check-in does not block the visit.** Refusing it would make the honest thing —
  letting the phone report a real position — the thing that stops a nurse working, and turning
  location off the thing that lets them through. It opens an admin task and an audit entry instead.
- **The seed places coordinates and lets the classifier decide.** Nothing types `"verified"` into a
  column, so the demo's badge is the live arithmetic: **1,154 verified, 102 unavailable, 35 out of
  range** across ninety days. Change the geofence in `ops.py` and the seed changes with it.
- **The pill organiser is the ₹199 add-on's first buyer**, and it is priced *per month*: four weekly
  fills in March are one ₹199 line, not four. A fill nobody managed to make is not a purchase.
- **`MedicationChange` is append-only history and only `medication_service` writes one.** A stopped
  medication is a row, not a missing row. One edit that moves both the dose and the time writes
  **two** rows — merging them would make the history unreadable exactly when a family is reading it.
  A nurse records doses; changing a prescription is not theirs to do.
- **`care_circle_members` carries a nullable `user_id`, and that is the design.** The neighbour two
  doors down with the spare key has no login and never will, and she is frequently the most useful
  person to reach at 2am. **This is the table Phase 11 extends** — its `PatientFamilyMember` is this
  table with `user_id` populated. Nobody is told they will be contacted through a channel that does
  not exist: `receives_alerts` with no phone and no email is refused at the boundary rather than
  discovered at 2am.
- **Consent is never updated in place.** Granting is a row, withdrawing is another, and the current
  position is the newest. A consent recorded against an older policy version stays a consent and is
  **flagged for review** rather than silently reinterpreted as agreement to a document nobody saw.
  Withdrawing a required consent is refused with the honest sentence: that is leaving the service.
- **Export and erasure are built once, over a registry of twenty-one datasets.** Phase 7's assistant
  messages, Phase 8's leads and Phase 9's whole clinical layer are customers on day one.
  `test_every_patient_scoped_model_is_accounted_for` walks every mapped class carrying a
  `patient_id` and asserts it is exported or explicitly retained with a reason — **and it caught a
  real gap four stages after it was written** (see below).
- **Retention is stated, not hidden.** Issued invoices survive because they are financial records;
  the audit log survives because deleting it would remove the evidence the erasure happened. Both
  appear on the family's page with their reasons. The patient row is **anonymised rather than
  deleted** so invoices and audit entries do not dangle, and the stored photographs go from disk as
  well as from the table.
- **`notification_service.dispatch` is the single outbound path.** The in-app record is **always**
  written: quiet hours and channel switches govern what leaves the building, never whether a family
  can see the alert, and there is deliberately **no in-app switch** at all. Three distinct
  non-delivery outcomes reach `delivery_log` — `suppressed`, `unreachable`, and switched off — with
  no body stored, because nothing was transmitted. Dual-channel critical is honoured as *two
  channels that can actually reach somebody*, which is Phase 9's correction: push has no address, so
  SMS + push is one channel wearing two names, and push is therefore **off by default** rather than
  on and inert.
- **The nurse's day leads with what was left open yesterday.** A visit left open on Tuesday is
  Wednesday's most urgent item; a chronological sort buries it forever. The next-visit brief is
  assembled from rows other services wrote and **computes nothing new** — a brief that derived its
  own numbers would be a second opinion beside the first.
- **Offline-tolerant capture is a `client_token` on readings and doses.** A replay corrects its own
  row rather than recording a second reading, and — the part that matters — **does not raise a
  second alert**.
- **The visit board replaces `/visits`' newest-250 list**, the deferral STATE.md recorded against
  this phase by name. It is a window with a page, and its summary describes the **window**, not the
  page, so clicking "next" does not report a different business.
- **`Alert` gains the stored SLA clock `EscalationEvent` already had**, in the same shape and for
  the same reason. `alert_service.backdate` moves the clock with the alert — see the bug note below.
- **Outcomes and zones compute from rows on every read**; there is not a stored counter in the
  module. A rate with nothing to divide is `None`, never 0%: 0% reads as a failure and "no data" is
  not one. SLA attainment counts only alerts that have **had their chance** — an alert raised five
  minutes ago is neither met nor missed, and counting it as met would flatter every figure.
- **The zone view reports which side of the recorded 30–45 break-even band each zone is on and
  invents no margin**, because the cost model behind that band was never supplied. The caveat is
  served from the constant so it travels with the numbers. Worth knowing: **every seeded zone is
  below the band**, which is what a pre-launch business with 28 patients across six zones actually
  looks like. It was not adjusted to look healthier.
- **Onboarding reads the work instead of counting clicks.** Four of the five steps are derived from
  the table that would carry the result, so the checklist cannot drift from what it describes. Empty
  the care circle and that step goes back to incomplete — the checklist being honest, not broken.
  Only "check your relative's details" is stored, and asking to tick a derived step is refused with
  the reason.

#### Bugs this phase found and fixed

- **⚠️ The privacy page told a family that they themselves had been looking at their mother's
  record.** Every audit entry was correct; the sentence above them was not. Their four consent
  decisions rendered under "who has looked at this record", beside a caption promising their own
  visits were not logged. **Found by reading the rendered page at 375px, not by any assertion** —
  it lived entirely in the gap between correct data and the words around it. The family's own
  actions are excluded now and the heading says what the list is.
- **⚠️ `OnboardingProgress` would have survived its own erasure.** Added in stage 8, carrying a
  `patient_id`, never registered. The coverage test failed on the next run, named the class, and the
  fix was a five-line registration. **This is exactly why that test asserts against the mapper
  registry rather than a list somebody maintains** — it caught a gap four stages after it was
  written, in code written by the same person who wrote the test.
- **⚠️ The seed's ninety-day alert history would have read as freshly raised and never breached.**
  The seed rewrites `created_at` on every historical alert; without moving `sla_due_at` with it, the
  whole queue's deadlines sat fifteen minutes in the future. This is the **third** appearance of one
  bug family — `business.paid_at` (Phase 4), safety-drop alerts (Phase 9) — so it now has
  `alert_service.backdate` and an invariant test over every seeded alert rather than a third
  open-coded fix.
- **The first channel resolver returned SMS + push for a critical alert on an account with no
  phone**: zero reachable channels reported as two. It walks the preference order and keeps the ones
  with an address now, recording the rest.
- **Two credential states that would have produced a meaningless badge** — a `verified` enum with no
  verifier, and an expired credential accepted for verification — are refused at the model and at
  the service.
- **The medication `PATCH` route originally let a nurse change a prescription.**

#### ⚠️ Reconcile with the real §4.10–4.18 — everything below is invented

All of it lives in **one file**, `backend/app/core/ops.py`.

| Value | Assumed | Confidence |
|---|---|---|
| `GEOFENCE_ACCURACY_CEILING_M` 150 · `GEOFENCE_ASSUME_ACCURACY_WHEN_MISSING` | invented | the **150 m radius** and the **three classification names** are RECORDED |
| `GEOFENCE_BLOCKS_CHECKIN = False` and the 24-hour review task | invented | the *reasoning* is recorded above and is the part worth arguing with |
| `HUB_GEOFENCE_RADIUS_M` 250 and **all six `ZONE_HUBS` coordinates** | invented — published neighbourhood centres standing in for hub addresses | DoorDoctor's actual hub addresses were never supplied |
| Photo caps: 4 MB · JPEG/PNG/WEBP · 1600 px · quality 82 · **180-day retention** | invented | "under `backend/app/uploads/`, never served statically" is RECORDED. EXIF stripping is **not** configurable and should not become so |
| `PILL_ORGANISER_COMPARTMENTS` 28 · `_DAYS` 7 · `_LOW_DAYS` 2 | invented | the **₹199 price** is recorded; billing it *per month rather than per fill* is derived from the recorded "per month" unit |
| `CARE_CIRCLE_MAX_MEMBERS` 8 and the relationship vocabulary | invented | the vocabulary is a suggestion list, not a constraint — the field is free text on purpose |
| `CONSENT_POLICY_VERSION` and **all four consent kinds**, their wording and which is required | invented | |
| `AUDIT_RETENTION_DAYS` 7 years | invented | **append-only** is RECORDED |
| `ERASURE_DESTROYS` / `ERASURE_RETAINS` — the categories **and the reasons** | written here | a lawyer should read this before it is shown to a real customer. The *shape* — say what is kept and why — is the part to keep |
| `QUIET_HOURS_START` 21 · `QUIET_HOURS_END` 7 | invented | `QUIET_HOURS_NEVER_SUPPRESS_CRITICAL` is a safety rule, not a preference. **Do not make it configurable** |
| `CHANNEL_ORDER` per notification type · `CHANNEL_DEFAULT_ENABLED` | invented | **dual-channel for critical** is RECORDED; *which* two is not |
| Consent withdrawal silences **all** outbound channels including critical | invented, and load-bearing | the in-app record is always written. If the founder wants critical alerts to override a withdrawn consent, that is a one-line change and a genuine policy decision |
| `OUTCOME_WINDOW_DAYS` 30 · `VISIT_BOARD_PAGE_SIZE` 25 | invented | |
| All five **onboarding steps**, their wording and their order | invented | |
| Which four onboarding steps are derived vs acknowledged | derived from what the schema can prove | the *principle* is the part to keep |
| Nurse credential bodies, titles and languages (`seed/demo_data.py`) | invented — real state nursing councils, fictional registration numbers | seed data, not policy |
| `BREAK_EVEN_MIN/MAX_SUBSCRIBERS` | **RECORDED (30–45)** | the note beside it says the cost model was not supplied, and nothing estimates one |

#### Deliberately deferred out of Phase 10

- **No photo retention sweep.** `PHOTO_RETENTION_DAYS` is defined and nothing enforces it.
  `app/scheduler.py` is the seam and it belongs with Phase 11's move to a worker, alongside the
  safety-score recalculation deferred out of Phase 9.
- **No audit log pruning.** `audit_service.retention_cutoff()` exists so the privacy page computes
  its promise from the same constant an operator would edit; nothing calls it. The log is
  append-only and this build keeps everything.
- **No family-facing device pairing, still.** Unchanged from Phase 9.
- **`ShiftCheckIn` has no admin editing.** An admin sees the last fifty shifts; correcting one is
  a database change. Nobody asked for a correction flow and inventing one would be inventing a
  process.
- **The care circle has no invite flow.** That is Phase 11's, on this table, by design.
- **Notification preferences are per *account*, not per patient.** A family with two parents gets
  one set of channels. Correct for the recorded scope and worth stating.
- **Quiet hours are the server's wall clock.** Phase 11 owns timezone correctness; when it lands
  these become the account's own hours, which is what an NRI family actually needs.
- **No push channel.** `PushChannel.address_for` still returns `None`, so it is switched off by
  default rather than pretending. Unchanged from Phase 3, and now *visible* in the UI as
  "Available once the DoorDoctor mobile app is released" rather than a dead switch.
- **The offline queue is server-side only.** The `client_token` contract, the idempotency and the
  tests are all real; the frontend sends a token but does **not** yet queue in `localStorage` and
  drain on reconnect. The hard half — a replay that cannot double-record or double-alert — is done,
  and the browser half is a Phase 11 UI task.

---

## ▶ Starting Phase 11 — Multi-family, hardening, tests, docs (§5.1, §5.3–5.5)

**Read `docs/build-log/phase-10.md` for how the last phase was structured, then write
`docs/build-log/phase-11.md` before writing any code.**

Phase 10 closed the feature surface. **Phase 11 is the only phase with no new product in it** — it
is about making what exists survive contact with a second family member, a second replica, a real
database and a stranger reading the code in a year.

### What Phase 11 covers

`PatientFamilyMember` + invite flow, with every authorization path in `core/dependencies.py`
migrated to membership; refresh tokens with rotation (access token out of `localStorage`, into
memory + refresh cookie); rate limiting; structured JSON logging with a request id that never logs
a reading or an identifier; error boundaries; **Alembic** with an initial migration; Postgres-ready
`DATABASE_URL`; timezone correctness (store UTC, render Asia/Kolkata, render the account's own zone
for NRI); ≥80% coverage on `services/`; Vitest for the new components; **Playwright** for the three
demo journeys; GitHub Actions CI. Then rewrite `README.md` and `DESIGN.md` and add
`docs/DEMO_SCRIPT.md`.

### Start here — Phase 10 built the table you need

**`care_circle_members` is `PatientFamilyMember`.** It already carries a nullable `user_id`, and
every patient's `family_user` is already mirrored in as the primary member. The multi-family work is
therefore:

1. Populate `user_id` when somebody accepts an invite.
2. Migrate `core/dependencies.authorize_patient` from `Patient.family_user_id == user.id` to a
   membership lookup on this table.
3. Keep `Patient.family_user_id` populated as the primary contact — Phase 10's `ensure_primary`
   depends on it and so does the erasure request's `requested_by`.

**Do not build a second membership table.** If that looks necessary, something has been
misunderstood; read `models/care_circle.py`'s docstring first.

`Plan.entitlements[FAMILY_SEATS]` is the cap on members *with a login*. `ops.CARE_CIRCLE_MAX_MEMBERS`
is the cap on the circle overall. They are different limits and both should hold.

### Things that will bite

- **`authorize_patient` is called from every router.** Migrating it is a one-function change with a
  whole-suite blast radius. Do it first, alone, and commit it alone.
- **The access token is in `localStorage` and `api/client.ts` is the only reader.** That is the good
  news. The bad news is `attachmentObjectUrl` and `medicationDepthApi.uploadPhoto` both call `fetch`
  directly with `getToken()`, and so does `requestBlob` — **three call sites, not one**, and all
  three need whatever replaces it.
- **Alembic arrives into a schema that `create_all()` has been building since Phase 1.** The initial
  migration has to be generated *from the current models* and then verified against a database the
  seed built, not against an empty one.
- **Timezone correctness will touch `database.now()`**, which every model's `default=` points at.
  Phase 10 added `quiet_start_hour` / `quiet_end_hour` as **server wall-clock** integers; they
  become account-local when this lands, and `NotificationPreference.in_quiet_hours` is the one place
  that compares them.
- **Coverage on `services/` will find `payment_gateway.py` and the LLM paths.** Both are deliberately
  thin and mostly unexercised because no provider exists. Decide whether they are excluded or
  covered with fakes *before* chasing a percentage.
- **The suite is 804 tests and runs in ~9 minutes on an idle machine** (it was 62 minutes on a
  loaded one during Phase 10 — check `uptime` before blaming a change). bcrypt is still the dominant
  cost and a test-only cost factor is still the obvious fix, flagged since Phase 5.

### Reuse these — do not rebuild them

- **`core/ops.py`, `core/pricing.py`, `core/clinical.py`** are read, never written, unless the real
  spec sections arrive.
- **`privacy_service.REGISTRY`** — a new table with a `patient_id` is a **registration**, not a
  rewrite, and `test_every_patient_scoped_model_is_accounted_for` will fail until it is one.
- **`notification_service.dispatch`** is the only outbound path. Anything Phase 11 sends — an invite,
  a password reset — goes through it, not through `notification_delivery` directly.
- **`audit_service.record`** for anything worth being able to prove later. It never commits; it joins
  your transaction.
- **`location_service.classify`** for any new geofence question. It holds no numbers.
- **`alert_service.backdate`** whenever a seed or a fixture moves an alert in time.

### Do not break these

- Patient 1 is Lakshmi, nurse 1 is Anitha, **Anitha holds exactly one open visit today**, and
  **Lakshmi carries no open alert**.
- `tests/conftest.py` seeds `SMALL`. Phase 9's clinical layer and most of Phase 10's trust layer are
  `FULL` only — **except Anitha's credentials, which are in `core.py` on purpose** so the
  family-facing nurse profile renders in the suite.
- The autouse `clean_process_state` fixture resets every process-global. **Register any new one.**
- `/public/plans` and authenticated `/plans` stay byte-identical.
- Nothing outside `alert_service` builds an `Alert`. Nothing outside `storage` writes a file.
  Nothing outside `audit_service` writes an `AuditEvent`. Nothing outside `medication_service`
  writes a `MedicationChange`.
- **`UPLOAD_ROOT` must stay pointed at a temp directory in `tests/conftest.py`**, or the suite writes
  patient photographs into the source tree.
- Backend **804**, Vitest **133**. The counts only grow.

## Open items and deferrals

- ✅ **Clinical trust, operations and privacy** — done in Phase 10. `core/ops.py` is the single
  source of every operational constant, `privacy_service.REGISTRY` is the single definition of what
  is exported and erased, and `notification_service.dispatch` is the single outbound path. Every
  invented value is in the reconciliation table under the Phase 10 results. **§4.10–4.18 was never
  supplied** — the fourth section in a row.
- **README image links.** `README.md` references `docs/screenshots/*.png`, which the history rewrite
  deleted. Either regenerate the screenshots (the app now looks materially different anyway, so
  these are stale) or drop the links. Worth doing as part of Phase 11 docs, or sooner if the founder
  wants the README presentable.
- ✅ **Care manager role** — done in Phase 9, as a **profile on an admin user**, decided with the
  founder on 2026-08-22. `core/dependencies.py` is untouched, `UserRole` is still exactly three, and
  a test pins both. The recorded 1:20 / 1:10 ratios are enforced, including on the seed.
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
- ✅ **Clinical features** — done in Phase 9. `core/clinical.py` is the single source of every
  clinical constant, `services/safety_score.py` holds arithmetic and no numbers, and every invented
  value is in the reconciliation table under the Phase 9 results. **§4.2–4.9 was never supplied.**
- ⚠️ **"The documented three actions" (§4.8) are still undocumented.** The plan names them and never
  lists them. All three are derived and `ASSUMED` in `clinical.WEARABLE_ACTIONS`. Ask the founder
  again if §4.8 ever arrives — it is the one Phase 9 assumption where the *existence* of a specific
  answer is recorded and the answer is not.
- **Safety scores are not recalculated on a schedule.** Computed live on read, stored only on an
  admin recalculate or a seed run — so the recorded 10-point-drop rule only fires on a stored
  calculation. `app/scheduler.py` is the seam; it belongs with Phase 11's move to a worker.
  **Phase 10 added two more jobs to that same seam**: the dose-photo retention sweep
  (`ops.PHOTO_RETENTION_DAYS` is defined and nothing enforces it) and audit-log pruning
  (`audit_service.retention_cutoff()` exists and nothing calls it). Three deferred jobs, one worker.
- ⚠️ **Push notifications still have no address in this build.** `PushChannel.address_for` returns
  `None` until a mobile client ships. Phase 10's routing handles it honestly: push is **off by
  default** rather than on and inert, the resolver picks two channels that can *actually reach*
  somebody, and the settings screen says "Available once the DoorDoctor mobile app is released"
  instead of offering a dead switch. **The recorded dual-channel promise is being kept with SMS and
  email.** When a mobile client ships, `address_for` is the only thing that changes.
- ✅ **The pill organiser add-on (₹199) has a buyer** — done in Phase 10.
  `medication_service.record_fill` bills it **once per billing month, not once per fill**, because
  the recorded price is per month: four weekly fills in March are one ₹199 line. A fill nobody
  managed to make is not a purchase.
- ✅ **The newest-250 visit list has a replacement** — done in Phase 10. `/admin/visit-board` is a
  windowed, paginated query whose summary describes the **window** rather than the page.
  `GET /visits` still exists and still caps at 250 for the nurse's own list, which is a different
  question with a different answer.
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
- **Every seeded zone is below the 30–45 subscriber break-even band.** 28 patients across six zones
  is ~5 each, so the admin zone view is six rows of "Below the band". That is what a pre-launch
  business actually looks like and it was **not** adjusted to look healthier. If a demo needs one
  healthy zone to make the feature legible, that is a seed change and a conversation, not a bug.
- **The offline *queue* is not built; the idempotency under it is.** The nurse screen mints one
  token per pending submission and clears it on success, so a double-tap or a retry after a timeout
  that actually succeeded corrects the record rather than doubling it — which is the half that
  matters even with signal. What is missing is the `localStorage` queue that holds a submission
  while the device is offline and drains on reconnect. That is a Phase 11 UI task and the contract
  it needs already exists and is tested.
- **Notification preferences are per account, not per patient**, and quiet hours are the **server's**
  wall clock. Both become account-local when Phase 11 does timezones — which is what an NRI family
  in a different timezone actually needs.
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
