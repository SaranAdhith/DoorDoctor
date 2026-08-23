# Phase 11 — Multi-family, hardening, tests, docs (§5.1, §5.3–5.5)

**Goal:** the platform survives contact with a second family member, a second replica, a real
database, a stranger reading the code in a year — and a browser in London.

Phase 9 made it clinical. Phase 10 made it accountable. **Phase 11 is the only phase with no new
product in it.** Every stage below either removes an assumption the codebase has been quietly making
since Phase 1, or makes an existing promise testable.

---

## The one idea this phase is built around

> **Every assumption the code has been allowed to make about its own environment is now wrong.**

Four of them, and each is load-bearing:

| The assumption | Since | Why it is wrong now |
|---|---|---|
| *A patient has exactly one family member, and it is `Patient.family_user_id`.* | Phase 1 | §5.1. A patient has a **circle**, and Phase 10 already built the table. |
| *The server's wall clock is the only clock.* | Phase 1 | §5.4. An NRI family in London is the customer segment on the pricing page. |
| *There is one process, and it is trusted.* | Phase 1 | §5.3. One replica, one in-process scheduler, a token in `localStorage`, `create_all()` for a schema. |
| *A test suite that passes is a tested codebase.* | Phase 1 | §5.5. 804 tests and no coverage number, no browser journey, no CI. |

The work is to replace each with something the code states out loud and a test holds it to.

---

## Decisions taken before writing code

| Question | Decision | Consequence |
|---|---|---|
| A second membership table? | **No.** `care_circle_members` **is** `PatientFamilyMember` | Phase 10 built it with a nullable `user_id` for exactly this. `models/care_circle.py`'s docstring says so. The work is *populate `user_id` and migrate authorization*, and the model is renamed in prose only — the table keeps its name and its history |
| What does a linked member get? | **Read for every linked member; write for `PRIMARY` and `CONTRIBUTOR`** | `CareCircleRole` already says it is "what a circle member may do". A `VIEWER` who could cancel a visit or request an erasure would make the role a label. New `authorize_patient_write` beside `authorize_patient` |
| Is `Patient.family_user_id` retired? | **No — it stays authoritative as the primary contact** | `care_circle_service.ensure_primary`, `privacy_service`'s `requested_by`, `notification_service`, `escalation_service` and every billing join depend on it. Dropping it is a Phase 12 concern and buys nothing |
| Where does UTC live? | **A SQLAlchemy `TypeDecorator`, not 149 route serializers** | 143 routes carry a `response_model`; **57 return raw dicts** built by services. No Pydantic annotation reaches those. A column type that returns *aware* UTC makes both paths emit an offset with no route touched. It is also the Postgres-ready storage this phase needs anyway |
| Naive-UTC-on-the-wire, or an offset? | **An offset.** `2026-08-23T12:13:12Z` | The current contract is "naive server wall clock, parse as local", written into `lib/format.ts`. It works only while the server and the reader share a timezone, which is the assumption this stage exists to delete |
| Does the business day become UTC? | **No — the business day is IST** | "Today's visits" for a Bangalore care business is IST midnight to IST midnight, whatever the server's clock says. Storage is UTC; **day windows are computed in IST and converted**. One helper, `core/timezones.day_bounds` |
| `create_all()` or Alembic? | **Both, and a test asserts they agree** | `create_all()` is what makes `git clone && uvicorn` work with no migration step, and that is worth keeping for a demo. Alembic is the production path. Two schema definitions that can drift is the actual risk, so it is a test, not a promise |
| Coverage: exclude `payment_gateway.py` and the LLM paths, or cover them? | **Cover them.** Nothing is excluded | The brief asked for this to be decided before chasing a percentage. Both are thin seams whose *whole point* is being substitutable — a fake is three lines. An exclusion list is where a percentage goes to become a lie |
| Access token lifetime | **15 minutes**, down from 1440 | A refresh token that rotates is only worth building if the access token it replaces is short-lived. The login response keeps `access_token` in the body, so all 804 tests and every existing fixture keep working |

### New dependencies

| Where | Package | For |
|---|---|---|
| backend | `alembic` | Migrations (planned since the stage map) |
| backend | `pytest-cov` | The ≥80% number on `services/` |
| backend | `psycopg[binary]` | Postgres-ready `DATABASE_URL`. Not used by the demo, which stays SQLite |
| frontend | `@playwright/test` (dev) | The three demo journeys |

`playwright-core` is already installed in `frontend/` with `--no-save` for the visual verification
scripts. `@playwright/test` is the runner and goes into `package.json` properly.

---

## Internal order — nine stages, committed as they land

| # | Stage | Touches | Why here |
|---|---|---|---|
| 0 | Make the suite affordable | `core/security.py`, `conftest.py` | Every later stage runs the suite a dozen times. Flagged since Phase 5 |
| 1 | Membership authorization | `core/dependencies.py` **alone** | Whole-suite blast radius. Committed by itself |
| 2 | The invite flow | `models/invite.py`, `care_circle_service` | Needs stage 1's membership to mean something |
| 3 | Refresh tokens with rotation | `core/security`, `routers/auth`, `api/client.ts` | Independent of 1–2; touches every frontend fetch |
| 4 | Time | `database.py`, `core/timezones.py`, 97 columns | The widest change. After auth so a re-login is not also a clock change |
| 5 | Logging, limits, boundaries | `core/logging.py`, `main.py`, `components/ErrorBoundary` | Wants stage 4's request-scoped plumbing in place |
| 6 | Alembic and Postgres | `alembic/`, `database.py`, `config.py` | After every column change, or the initial migration is stale on arrival |
| 7 | Coverage, Vitest, Playwright, CI | `tests/`, `e2e/`, `.github/workflows/` | Last, because it pins whatever the eight stages before it produced |
| 8 | README, DESIGN, DEMO_SCRIPT | `README.md`, `DESIGN.md`, `docs/` | Written against the finished thing, not against the plan for it |

Each stage ends green and is committed before the next begins.

---

## Stage 0 — make the suite affordable

**804 tests, ~9 minutes on an idle machine, and bcrypt is almost all of it** — ~180 logins at
0.73 s per verify. Flagged in STATE.md since Phase 5 and deferred to "Phase 11's hardening". This is
that.

- **`core/security.py`** gains `BCRYPT_ROUNDS`, from `settings.bcrypt_rounds` (default **12**, the
  bcrypt default this codebase has always used). `conftest.py` sets `BCRYPT_ROUNDS=4`.
- **4, not 1.** A cost factor low enough to be *free* invites a test that accidentally proves
  nothing. 4 is ~60× faster than 12 and still a real bcrypt hash.
- **A test asserts the production default is 12**, so the setting cannot quietly become a weak
  hash in a deployment. The setting exists for the suite and nothing else, and the source says so.
- The seeded `Demo@123` digest is still computed once and shared (Phase 5), so this is only the
  ~180 `checkpw` calls on the login path.

**Acceptance:** 804 passing, suite under 3 minutes.

## Stage 1 — membership authorization, alone

The one-function change with a whole-suite blast radius. **Committed by itself.**

- **`core/dependencies.py`**
  - `_family_membership(db, user, patient_id) -> CareCircleMember | None` — one query on
    `care_circle_members` where `user_id == user.id`.
  - `authorize_patient` stops asking `Patient.family_user_id == user.id` and asks for a membership.
    The 404-not-403 disclosure rule is unchanged.
  - **`authorize_patient_write`** — new, beside it: membership *and* a role of `PRIMARY` or
    `CONTRIBUTOR`. A `VIEWER` gets a **403 with a reason**, not a 404: they can already see the
    patient, so hiding the record's existence protects nothing and an unexplained failure is worse.
  - `authorize_visit`'s family branch takes the same path.
- **Six list queries** currently filter on `family_user_id` and each becomes a membership join:
  `routers/patients.py:29`, `visit_service.py:47`, `alert_service.py:142` and `:165`,
  `assistant_context.py:213` (whose comment already predicts this change by name), and
  `report_service`'s family scoping.
- **`ensure_primary` is the invariant this rests on.** Every patient must have a primary member row
  or its own family user loses access. A **seed test walks every patient and asserts one exists**,
  and `population.py` gets a backstop call.
- **Which routes become write-scoped:** schedule/cancel a visit, order a lab, book or cancel a
  consult, edit medications and thresholds, manage the care circle, request an erasure, change the
  subscription. Reading anything stays membership-only.

**Acceptance:** 804 passing untouched — the demo family is the primary member of Lakshmi, so every
existing test takes the same path it did before. Plus new tests: a viewer reads and cannot write, a
contributor writes, a removed member loses access immediately, and `other_family` is still a 404.

## Stage 2 — the invite flow

`user_id` gets populated. **An invite is not a membership** — it is a pending token, and it is built
the way Phase 3 built password resets, because that is the same problem.

- **`models/invite.py` — `FamilyInvite`**: `patient_id`, `email`, `role`, `invited_by`,
  `token_hash` (sha256 of `secrets.token_urlsafe(32)`, **never the token**), `expires_at`
  (**7 days** — an invite is read at leisure, unlike a reset), `accepted_at`, `revoked_at`,
  `member_id`. Unique on `(patient_id, email)` while pending.
- **Two caps, and both hold.** `Plan.entitlements[FAMILY_SEATS]` caps members **with a login**;
  `ops.CARE_CIRCLE_MAX_MEMBERS` caps the circle overall. The brief says they are different limits;
  the service checks both and the error says which one was hit.
- **Accepting has two paths**: an email that already has an account **links** it (no password
  involved, and it must be a `family` role account); an unknown email **creates** one, through
  `core.security.password_problem` — the same single rule, not a second one.
- **The invite email goes through `notification_service.dispatch`**, per the brief. Not
  `notification_delivery` directly.
- **The token is redacted before it is stored**, `sensitive=[link]`, exactly as Phase 3's reset link
  is — and the same test shape asserts the raw token never appears in any `delivery_log` body.
- **Revoking an invite and removing a member are different actions and both are audited.** Removing
  a member with a login revokes their access immediately; `remove_member`'s existing primary
  protection is unchanged.
- **`debug_invite_url` only when `settings.is_development`**, same as `debug_reset_url`.
- Rate limited: `INVITE_PER_PATIENT = (10, 3600)` through the existing limiter.
- Frontend: the Care Circle screen gains **Invite**, a pending-invites list with revoke, and a
  public `/invite/:token` accept page on `AuthLayout` beside the reset page.

**Acceptance:** invite → accept as a new user → the new account sees the patient and cannot see any
other; accept as an existing user; expired, revoked, reused and unknown tokens; both caps refused
with distinguishable messages; a seat freed by removal is reusable.

## Stage 3 — refresh tokens with rotation

The access token leaves `localStorage`.

- **`models/refresh_token.py`**: `user_id`, `token_hash`, `family_id` (the rotation chain),
  `issued_at`, `expires_at` (**30 days**), `rotated_at`, `revoked_at`, `user_agent_hint`.
- **Rotation with reuse detection.** Presenting a token that has already been rotated means the
  cookie was stolen and replayed, so **the whole `family_id` chain is revoked** and the user is
  signed out everywhere. Any other behaviour makes rotation decoration.
- **The cookie is `httpOnly`, `SameSite=Lax`, `Secure` outside development, and scoped to
  `/api/v1/auth`** — it is presented to exactly three endpoints and nothing else needs it.
- **`POST /auth/refresh`** returns a new access token and sets a new cookie. **`POST /auth/logout`**
  revokes the chain and clears it. Login issues both.
- **The login response keeps `access_token` in the body.** Every one of the 804 tests and every
  fixture uses it, and a bearer token is still the API's authentication — the cookie carries the
  *refresh* token only. This is why the stage does not have a whole-suite blast radius.
- **Frontend — the token moves into a module variable in `api/client.ts`.** The brief names the
  three call sites and it is right: `request`, `requestBlob`, and `trust.ts`'s
  `attachmentObjectUrl` + `medicationDepthApi.uploadPhoto`. All four now read the same in-memory
  accessor.
- **A single-flight refresh.** A 401 triggers one refresh and retries the request once; concurrent
  401s share that one in-flight promise rather than starting five rotations that invalidate each
  other. This is the bug that makes rotation unusable in practice, so it is built in from the start.
- `AuthContext`'s startup path calls `/auth/refresh` before `/auth/me` — a returning visitor with a
  live cookie is signed in without re-entering a password, which is what dropping the 24-hour access
  token would otherwise cost them.
- **Login gains a rate limit**: `LOGIN_PER_EMAIL = (10, 900)`, `LOGIN_PER_IP = (50, 900)`. It has
  been unmetered since Phase 1 and it is the credential-stuffing endpoint.

**Acceptance:** refresh rotates and the old token is dead; a replayed token kills the chain; logout
revokes; an expired refresh returns 401 and the app lands on `/login`; the PDF fetch and the photo
upload both still carry a token; five concurrent 401s produce one rotation.

## Stage 4 — time

The widest change in the phase, and it has **one seam**.

- **`core/timezones.py`** — `UTC`, `IST = ZoneInfo("Asia/Kolkata")`, `utcnow()`, `to_utc(dt)`,
  `in_zone(dt, tz)`, `day_bounds(day, tz) -> (utc_start, utc_end)`, `local_hour(dt, tz)`,
  `is_valid_zone(name)`. It holds no business rule and imports nothing from the app — the fourth
  file with that property, after `pricing.py`, `clinical.py` and `ops.py`.
- **`database.UtcDateTime(TypeDecorator)`** — binds aware → UTC → naive for storage, and returns
  naive → **aware UTC** on read. **97 column declarations across 31 model files** change from
  `DateTime` to `UtcDateTime` by scripted substitution, then audited by grep, exactly as Phase 1's
  terminology refactor was. The 4 `Date` columns are dates and are untouched.
  - Storage stays naive UTC, so **the SQLite file is unchanged on disk and no migration is needed**
    for it. Postgres gets `TIMESTAMP WITH TIME ZONE` from the same type.
  - Because the values are *aware* in Python, **Pydantic serializes an offset with no route
    touched** — which is what makes this a 97-line change instead of a 149-route one.
- **`database.now()` returns aware UTC.** 66 files import it and none of them change.
- **Aware/naive comparison is a `TypeError`, and that is the point** — it fails loudly at the few
  places that build a datetime by hand rather than silently comparing two different clocks. The
  known ones: `admin_service:14`, `ops_service:76`, `nurse_ops_service:50/64/336`,
  `visit_service:30`, `report_service:50/68`, `medication_service:440`, `nurse_service` ×4, and the
  seed's date arithmetic.
- **The business day is IST.** Every one of those day-window sites goes through
  `timezones.day_bounds(day, IST)`. `report_service`'s weekly/monthly periods likewise — the
  scheduler already fires on IST cron and the periods must agree with it.
- **`User.timezone`** — an IANA name, default `Asia/Kolkata`, validated against `zoneinfo`. On
  `/auth/me`, editable from account settings. This is the NRI feature: the London daughter reads
  "9:30 pm" as her own 9:30 pm, or as IST, and knows which.
- **Quiet hours become account-local.** `NotificationPreference.in_quiet_hours` is the one place
  that compares them (STATE.md says so) and it now compares in the account's zone.
  `QUIET_HOURS_NEVER_SUPPRESS_CRITICAL` is untouched — it is a safety rule, not a preference.
- **Frontend:** `lib/format.ts`'s `toDate` is the single seam and its docstring is rewritten. A
  `TimezoneProvider` supplies the account's zone; every `toLocale*` call renders in it and **times
  carry a zone label** where a mistake would matter (visit times, alert times, check-ins).
- **`billing.py:51`'s `datetime.now()`** and `security.py:33`'s already-aware clock are reconciled
  to the same helper.

**Acceptance:** a test freezes the clock at 23:30 IST (18:00 UTC) and asserts "today's visits"
returns the IST day, not the UTC one; a London account sees a visit at its own local time and an IST
account at IST; quiet hours suppress against the account's zone; the API emits `Z`; the seed still
produces the same relative history; `test_seed`'s four invariants hold.

## Stage 5 — logging, limits, boundaries

- **`core/logging.py`** — a JSON formatter (`ts`, `level`, `logger`, `msg`, `request_id`, plus
  extras), a `request_id` `ContextVar`, and a middleware that mints one per request, puts it in the
  response as `X-Request-Id`, and logs one line per request: method, path **template**, status,
  duration. **The path template, not the path** — `/patients/42` in a log line is an identifier.
- **The rule is enforced by a test, not by care.** `test_logging.py` drives a representative set of
  requests through a capturing handler and asserts no patient name, email, phone, or reading value
  appears in any record. Phase 6 already proved this shape works for `llm_client`; this generalises
  it.
- Error responses gain the request id so a user can quote it and it can be found.
- **`components/ErrorBoundary.tsx`** — one boundary around the shell (so a crash keeps navigation)
  and one per route element (so a crash keeps the shell). It renders an apology, the request id if
  there is one, and a retry — Phase 2's error-with-retry rule, applied to the crash case.
- `main.tsx` keeps a top-level boundary for a render error before the app mounts.

## Stage 6 — Alembic and Postgres

- **`alembic/` with an initial migration generated from the current models**, then verified against
  a database the **seed** built — not against an empty one, which is the failure mode the brief
  names.
- **`test_migrations.py` asserts the two schema definitions agree**: migrate an empty database, and
  compare its metadata to `Base.metadata` with Alembic's own comparison. A drift is a failed test,
  not a production surprise.
- `create_all()` stays in the lifespan for SQLite so `git clone && uvicorn` still needs no step, and
  the source says which path is which.
- **`config.py`** — `DATABASE_URL` accepts `postgresql+psycopg://`; pool settings applied only for
  non-SQLite; `check_same_thread` applied only for SQLite (already true).
- A **documented** Postgres run in the README. The demo stays SQLite.

## Stage 7 — coverage, Vitest, Playwright, CI

- **`pytest-cov`, `--cov=app/services --cov-fail-under=80`** in `pyproject`/`setup.cfg`, so the
  number is enforced rather than reported. Nothing excluded, per the decision above; `payment_gateway`
  and the LLM paths get fakes.
- **Vitest for the new components**: the invite form and accept page, the error boundary, the
  timezone renderer, the refreshing client's single-flight behaviour.
- **Playwright — the three journeys from §8**, as `frontend/e2e/`: the visitor→lead journey, the
  family journey (reset → summary → assistant with **no API key** → My Plan → report PDF), and the
  nurse→alert→admin journey. Driven against a seeded backend on a throwaway database.
- **`.github/workflows/ci.yml`** — backend (`pytest` + coverage gate), frontend (`tsc`, `vitest`,
  `build`), and Playwright as its own job. Both matrix-pinned to the local versions: Python 3.13,
  Node 20.

## Stage 8 — README, DESIGN, DEMO_SCRIPT

- **`README.md` is rewritten, not patched.** It describes a Phase-1 MVP. It also links
  `docs/screenshots/*.png`, which the Phase 2 history rewrite deleted — STATE.md has carried that as
  an open item since. **The links go**, and the screenshots are regenerated only if they earn it;
  stale screenshots of an app that has changed eleven times are worse than none.
- **`DESIGN.md`** — the architecture, the layering rule, the four constants files and why they are
  four, the single-seam list (`alert_service`, `storage`, `audit_service`, `medication_service`,
  `notification_service.dispatch`, `llm_client`), the authorization model after stage 1, and the
  time model after stage 4.
- **`docs/DEMO_SCRIPT.md`** — the four §8 journeys as a script someone else can run: what to seed,
  which account, what to click, what to point at, and what to say about the parts that are honestly
  incomplete (no payment gateway, no real provider behind the LLM, pre-launch).

---

## What this phase does not do

Stated here so the next reader does not go looking:

- **Does not reconcile §3, §2.3, §4.2–4.9 or §4.10–4.18.** Four sections were never supplied. The
  invented values stay in their four files with their four reconciliation tables.
- **Does not move the scheduler to a worker.** Three jobs are queued for one (report generation,
  safety-score recalculation, photo retention, audit pruning — four, in fact). Alembic and Postgres
  are the prerequisites and they land here; the worker is the next phase's first task.
- **Does not build the `localStorage` offline queue.** The idempotency under it is done and tested
  (Phase 10); the queue is a UI task and it is smaller than it looks now that `client_token` exists.
- **Does not prerender the public site.** Flagged in Phase 8 as a Phase-11-scale decision; it is an
  SSR decision, and it is not hardening.
