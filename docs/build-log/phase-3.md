# Phase 3 — Forgot password + login rebuild (§2.1, §2.5)

**Goal:** a family member who has forgotten their password can get back in without a human, and the
first screen anyone sees looks like a product rather than a form.

**Constraint:** no email/SMS provider exists in this build and none will be bought. Delivery is a
real abstraction with real records, backed by simulated channels — so Phase 10's routing,
preferences and quiet hours plug into a seam that already exists rather than replacing a stub.

---

## Step 1 — `core/exceptions.py`: `TooManyRequestsError`

429 + `Retry-After`. Reused by Phase 8's lead form and Phase 11's global limiter.

## Step 2 — `core/ratelimit.py`

In-memory sliding window. `RateLimiter.check(scope, key, limit, per_seconds)` records the hit and
raises `TooManyRequestsError` when the window is full. Expired entries are pruned on read so the
dict cannot grow without bound.

Budgets for this phase: **5 per email per hour**, **20 per IP per hour**.

Per-process by design — one uvicorn worker is what this build runs. The docstring says so, and says
Redis is where this goes in production. A module-level `limiter` singleton plus `reset()` for tests
(an autouse fixture clears it, otherwise test order would decide test outcomes).

## Step 3 — `models/password_reset.py`

`PasswordResetToken`: `user_id`, `token_hash` (unique), `expires_at`, `used_at`, `requested_ip`,
`created_at`.

**The raw token is never stored.** `secrets.token_urlsafe(32)` → sha256 hex → the column. A token is
usable iff `used_at is None and expires_at > now`. Superseding a request stamps `used_at` on the
outstanding siblings, so the newest link is the only working link.

## Step 4 — `models/delivery.py` + `services/notification_delivery.py`

`DeliveryLog` (`delivery_log` table): channel, recipient, subject, body, status, `user_id`,
`created_at`, `detail`.

`EmailChannel | SmsChannel | WhatsAppChannel | PushChannel` behind one `DeliveryChannel` protocol.
Each formats the payload it *would* hand a provider and returns `SIMULATED`. `deliver()` writes the
`DeliveryLog` row and logs a line.

**Secrets never land in the log.** `deliver(..., sensitive=[reset_url])` replaces each sensitive
value with `[redacted]` in the persisted body. Without this, `delivery_log` would be a table of live
password-reset links — a DB reader could take over any account inside 30 minutes. The real link goes
to the application log (dev convenience) and to the API response in development only.

## Step 5 — `core/security.py`: one password rule

`password_problem(password) -> str | None` — ≥8 characters, ≤128, at least one letter and one
number. One function so the reset schema, and later signup, cannot drift apart. `frontend/src/lib/password.ts`
mirrors it for inline feedback; the server is still the authority.

## Step 6 — `services/password_reset_service.py`

`request_reset` · `validate_token` · `is_token_valid` · `reset_password`. Separate from
`auth_service.py`, matching the per-concern service naming already in the tree.

`reset_password` sets the new hash, stamps the used token, invalidates every other outstanding token
for that user, and sends a "your password was changed" notice through the delivery layer — a reset
you did not ask for should be visible.

## Step 7 — `routers/auth.py` endpoints

| Endpoint | Behaviour |
|---|---|
| `POST /auth/forgot-password` | **Always 200**, same body whether or not the account exists. `debug_reset_url` is populated only when `settings.environment == "development"`. Rate limited on email and IP. |
| `POST /auth/reset-password` | 422 on a weak password, 400 on an expired/used/unknown token — one message for all three so the response cannot be used to probe tokens. IP rate limited. |
| `GET /auth/reset-token/{token}/valid` | `{"valid": bool}` so the reset page can show "this link has expired" before the user types a password. |

## Step 8 — Backend tests (`tests/test_password_reset.py`)

happy path · expired · reused · sibling invalidated · unknown email (200, no token row, no leak) ·
weak password · email rate limit · IP rate limit · token validity probe · delivery log written ·
**raw reset URL absent from `delivery_log`** · password-changed notice sent.

## Step 9 — Frontend

- `lib/password.ts` — the mirrored rule.
- `components/layout/AuthLayout.tsx` — the two-pane shell (brand story left, card right) shared by
  all three auth screens, so they are one thing and not three.
- `pages/Login.tsx` **rebuilt**: two-pane, trust row, segmented Family · Nurse · Admin picker,
  show/hide password (already in the `Input` primitive), collapsed `<details>` demo access, footer.
- `pages/ForgotPassword.tsx` — submits, then shows the same confirmation for any email. In
  development the returned `debug_reset_url` renders as a "Open reset link" button, clearly labelled
  as a development affordance.
- `pages/ResetPassword.tsx` — validates the token on mount, live strength feedback, confirm field,
  success → `/login` with a banner.
- `App.tsx` — `/forgot-password`, `/reset-password`.
- `api/auth.ts` + `types/index.ts` — three new calls, three new types.

**The segmented role picker is not an auth control.** It tailors the copy and picks which demo
account the `<details>` block fills. The server decides the role; signing in as a nurse with
"Family" selected still works and still routes to `/nurse/visits`. Commented in the source so it is
not mistaken for a security boundary later.

**Trust row wording** stays inside what the product actually does — verified nurse credentials
(`Nurse.verification_status` exists), threshold alerts worked by a care team (the alert queue
exists), role-scoped access to every record (`core/dependencies.py` enforces it). No certifications,
no customer counts, no logos.

## Step 10 — Frontend tests

`test/password.test.ts` (rule parity with the backend) and `test/forgotPassword.test.tsx` (the
confirmation is identical for a known and an unknown email — the anti-enumeration promise, asserted
in the UI as well as the API).

## Acceptance

```bash
cd backend  && .venv/bin/python -m pytest        # 73 → 90
cd backend  && .venv/bin/python -m app.seed      # clean
cd frontend && npx tsc -p tsconfig.json --noEmit # zero errors
cd frontend && npm run build                     # clean
cd frontend && npx vitest run                    # 11 → 18
```

Plus a live browser pass at 375 / 768 / 1024 / 1440: request a reset for `family@doordoctor.in`,
follow the dev link, set a new password, sign in with it.

Commit: `feat(auth): password reset flow, delivery channels and rebuilt login`

---

## Executed

Everything above shipped as planned. Three things came out differently:

### `SegmentedControl` became a primitive

The role picker was first written inline on the login page as a `role="radiogroup"` of buttons. That
announces correctly and then ignores the arrow keys a screen-reader user presses next — a radio
group is one tab stop with arrow-key movement inside it, not N tab stops. Rather than fix it in
place, it moved to `components/ui/SegmentedControl.tsx` with roving tabindex, Arrow/Home/End
handling and six tests, per §7: a control that does not exist yet is added to the primitives layer.
Phase 4's monthly/annual billing toggle and Phase 6's 7d/30d/90d window picker are the same control.

### `api.get` now takes request options

`api.post` accepted `{ skipAuthRedirect }` and `api.get` did not, so `checkResetToken` could not opt
out of the global session-expiry handler. One-line signature change in `api/client.ts`; no caller
needed updating.

### `FRONTEND_BASE_URL` was added

Reset links point at the frontend, and the API had no setting that knew where that is. Defaults to
`http://localhost:5173`. `settings.is_development` was added alongside it as the single gate for
development-only affordances, replacing a scattered `environment == "development"` comparison.

### Verified live

Backend and Vite running, Chrome via `playwright-core`, at 375 / 768 / 1024 / 1440:

- No horizontal overflow on any of the three auth screens at any width.
- Full journey: forgot password → development link → weak password refused → mismatch refused →
  strength meter → set password → redirect to login with the success banner → sign in with the new
  password → `/family/dashboard`.
- The rate limiter was confirmed against the running server, not just in tests: the sixth request
  for one address returned `429` with `retry-after: 3248`.

The throwaway Playwright script was deleted after the run and the demo database re-seeded, so the
`Demo@123` credentials in `STATE.md` still hold.

### Results

| Check | Before | After |
|---|---|---|
| Backend tests | 73 | **96** |
| Frontend tests | 11 | **29** |
| `tsc --noEmit` | clean | clean, no `any`, no `@ts-ignore` |
| `npm run build` | clean | clean |
| `python -m app.seed` | clean | clean |
