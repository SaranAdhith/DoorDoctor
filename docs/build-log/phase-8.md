# Phase 8 — Public marketing site + lead capture (§2.6)

**Goal:** a stranger arrives at `/`, understands what DoorDoctor is, sees what it costs, and leaves
their details — and an admin sees that enquiry in-app minutes later. This closes the "credible
demoable platform" line: everything before this phase is behind a login, and a product nobody can
find is not a business.

---

## The one idea this phase is built around

> **The public site is the same product, not a brochure beside it.**

There is a real temptation to start a parallel marketing stylesheet — its own colours, its own
buttons, its own idea of a heading — because marketing pages "look different". That produces two
design systems and the visitor notices the seam the moment they sign in. So:

- Public pages compose from `components/ui/` (28 primitives) and the Phase 2 tokens. No new palette,
  no second button, no marketing-only type scale.
- `PublicLayout` is `AuthLayout`'s **sibling**: a third shell alongside `AppShell` and `AuthLayout`,
  not a replacement for either.
- What *is* new is layout rhythm — wide hero sections, a marketing header and a fat footer. Those go
  in `components/public/`, built out of the same primitives.

---

## Decisions taken with the founder before writing code (2026-08-22)

| Question | Answer | Consequence |
|---|---|---|
| §3 was never supplied — how should the pricing page treat the `ASSUMED` values? | **Ship them as they stand, label nothing** | Tier names and entitlement counts go public exactly as `core/pricing.py` has them. The `ASSUMED` markers stay in the source and in STATE; they do not appear on the page. |
| §2.4 records 16.7 visits/patient/month against assumed tiers of 4/8/12 — change them? | **Leave 4 / 8 / 12 as-is** | `core/pricing.py` is **not edited this phase**. The mismatch stays documented under Phase 5; quota enforcement stays deferred. |

Both answers mean the same thing operationally: **Phase 8 does not touch `core/pricing.py`.** It
reads it. That was always the rule — "import those constants, never restate a number" — and the
founder's answer removes the only reason this phase might have needed to write to that file.

### What that does *not* license

The locked decision at the top of STATE.md still holds and this is the phase that breaks it by
accident if anyone is careless:

> **No invented social proof.** No traction numbers, no testimonials, no customer counts, no
> certifications, no partner logos, no "trusted by" strip, no press mentions, no star ratings.

DoorDoctor is pre-launch. A marketing site is *made of* the things that rule forbids, so the trust
sections are built from **what the platform verifiably does** — the same discipline `AuthLayout`'s
`TRUST_SIGNALS` already applies ("Nurse credentials verified before assignment", not "10,000 happy
families"). Both founders — **Saran Adhith (Founder & CEO)** and **Darren D'Souza (Co-Founder)** —
appear together, as an equal pair, with equal billing and equal card size.

---

## Where the prices come from — one source, one code path

`core/pricing.py` is authoritative, and the seed already writes those constants into `Plan` rows.
The public pricing page could read either. Reading a *third* copy typed into a `.tsx` is the failure
mode this section exists to prevent.

**Decision: a new unauthenticated `GET /public/plans` that calls
`subscription_service.list_plans` + `serialize_plan` — the exact functions `/plans` already uses.**

- Not a second serializer. Not a static JSON blob. The same two functions, minus the auth dependency.
- A test asserts `/public/plans` and `/plans` (authenticated) return **identical** payloads, so the
  two routes cannot drift.
- A second test asserts the served monthly prices equal `pricing.PLANS` — the DB round-trip is
  verified, not assumed.
- Consequence: the pricing page is a **loading** page. It gets `Skeleton` and `ErrorState` with
  retry like every other list in this codebase (Phase 2's rule). A marketing page that renders
  prices from an API is worth the spinner; a marketing page whose prices are wrong is not.

Prices recorded verbatim in the build prompt, published as-is:
₹2,500 / **₹3,500 Recommended** / ₹4,500 monthly · ₹25,000 / ₹35,000 / ₹45,000 annual ("2 months
free") · corporate ₹2,800/employee/month · institutional ₹38,000 / ₹58,000 / ₹78,000 led by
**₹84 / ₹77 / ₹65 per resident per day** · add-ons blood panel ₹499, pill organiser ₹199.

Add-ons are not on `Plan` rows — they are `pricing.ADD_ONS`. `/public/plans` returns them in the
same payload so the page still never states a number of its own.

---

## Lead capture — the only unauthenticated write in the codebase

`POST /leads` is the first endpoint in this build that a stranger can write to. Everything below is
because of that sentence.

| Defence | How | Why not the obvious alternative |
|---|---|---|
| **Rate limit** | `core/ratelimit.limiter`, `LEADS_PER_IP = (10, 3600)` and `LEADS_PER_EMAIL = (3, 3600)` | Phase 3 built the limiter and Phase 7 reused it. A second limiter would need its own reset in `clean_process_state` and would drift. |
| **Honeypot** | A `company_website` field the real form renders hidden and never fills. Non-empty → **return 200 and store nothing** | A 400 tells a bot its script was detected. A 200 tells it nothing and costs it a retry. |
| **Field caps** | Every string capped in the Pydantic schema, message at 2,000 | Follows `schemas/assistant.py`'s `MAX_QUESTION_CHARS` note — an uncapped public text column is an unbounded free-text store someone else fills. |
| **No enumeration** | The response is a fixed message. It never says whether this email already enquired | Same rule as `POST /auth/forgot-password`. |
| **No admin notification** | New leads appear on **Admin → Leads** with an unworked count. No `Notification` row, no delivery | An unauthenticated endpoint that writes to every admin's notification bell is a spam amplifier. The limiter caps the table; it should not also cap the bell. |

Lead reads are admin-only (`AdminUser`). A family member or nurse hitting `GET /leads` is a 403, and
a test pins it — a lead list is a list of named strangers' phone numbers.

---

## File-by-file

### Backend — new files

| File | Contents |
|---|---|
| `app/models/lead.py` | `Lead`. Columns: `name`, `email`, `phone`, `city`, `kind`, `message`, `source_page`, `status`, `handled_by_user_id`, `handled_at`, `admin_note`, `created_at`. Docstring records the retention stance (a lead is contact data volunteered by a stranger; it is admin-only and erasure lands with Phase 10's consent work). |
| `app/schemas/lead.py` | `LeadCreate` (with the honeypot field + caps), `LeadAccepted` (fixed message), `LeadOut`, `LeadUpdate` (status + note), `LeadSummaryOut` (counts by status). |
| `app/services/lead_service.py` | `create`, `list_leads(status=None)`, `update`, `summary`. `create` returns `None` when the honeypot is tripped so the router's response shape does not depend on whether the caller was a bot. |
| `app/routers/leads.py` | `POST /leads` (public), `GET /leads` (admin), `GET /leads/summary` (admin), `PATCH /leads/{id}` (admin). |
| `app/routers/public.py` | `GET /public/plans` — plans + add-ons, unauthenticated. |
| `tests/test_leads.py` | happy path · honeypot stores nothing but answers 200 · per-IP 429 · per-email 429 · caps 422 · admin list · status filter · admin update · **family 403 · nurse 403 · anonymous 401** · summary counts. |
| `tests/test_public.py` | `/public/plans` unauthenticated 200 · payload identical to authenticated `/plans` · prices equal `pricing.PLANS` · add-ons equal `pricing.ADD_ONS` · no entitlement key leaks that `/plans` does not already expose. |

### Backend — edits

- `app/models/enums.py` — `LeadKind` (`family | corporate | institution | nri | other`),
  `LeadStatus` (`new | contacted | qualified | closed`).
- `app/models/__init__.py` — register `Lead`, `LeadKind`, `LeadStatus`.
- `app/core/ratelimit.py` — `LEADS_PER_IP`, `LEADS_PER_EMAIL`, beside the existing budgets.
- `app/main.py` — include `leads.router` and `public.router`; extend `DESCRIPTION` with one sentence.
- `app/seed/population.py` — seed a handful of leads in `FULL` only, so Admin → Leads is not an
  empty screen in the demo. `SMALL` gets none, so all 365 existing tests stay untouched.

### Frontend — new files

`components/public/`:

| File | Contents |
|---|---|
| `PublicLayout.tsx` | Skip-link, sticky header (logo, nav, "Sign in", accent "Get started"), mobile drawer nav, fat footer with the four column groups, disclaimer and both founders' company line. Renders `<Outlet/>`. |
| `Seo.tsx` | `<Helmet>` wrapper: title, description, canonical, Open Graph, and optional JSON-LD. One component so no page hand-writes a meta tag. |
| `Section.tsx` | `Section` + `SectionHeading` — the vertical rhythm and max-width every public page shares. |
| `PageHero.tsx` | Eyebrow, headline, sub, CTA row. |
| `PlanCard.tsx` | One plan, priced from a `PlanOut`. Recommended treatment driven by `plan.recommended`, never by a hard-coded code. |
| `PricingGrid.tsx` | Fetches `/public/plans` once, owns skeleton/error/retry, renders a filtered audience. Reused by all three pricing pages. |
| `EntitlementList.tsx` | Turns a plan's entitlement JSON into readable lines. **Reuses `lib/plan.ts`** (Phase 4 already maps entitlement keys to labels) rather than a second mapping. |
| `LeadForm.tsx` | Name, email, phone, city, enquiry type, message, hidden honeypot. Posts to `/leads`, renders success inline, handles 429 by message. |
| `FaqList.tsx` | Accessible `<details>`-based Q&A, also used on `/pricing`. |
| `FounderPair.tsx` | Both founders, equal cards, one component so they cannot be rendered apart. |
| `CtaBand.tsx` | The closing "talk to us" band shared by most pages. |

`pages/public/` — 14 routes plus a 404:

`Home` `/` · `WhatIsDoorDoctor` `/what-is-doordoctor` · `WhoItsFor` `/who-its-for` ·
`Pricing` `/pricing` · `PricingCorporate` `/pricing/corporate` ·
`PricingInstitutions` `/pricing/institutions` · `Nri` `/nri` · `HowItWorks` `/how-it-works` ·
`About` `/about` · `TrustAndSafety` `/trust-and-safety` · `Faq` `/faq` · `Contact` `/contact` ·
`Privacy` `/privacy` · `Terms` `/terms` · `NotFound` `*`.

`api/public.ts` (plans + lead submission) · `api/leads.ts` (admin) · `pages/admin/AdminLeads.tsx` ·
`public/robots.txt` · `public/sitemap.xml`.

### Frontend — edits

- `package.json` — `react-helmet-async`. (Frontend installs with plain `npm`; the **backend** venv is
  the one with no `pip`.)
- `main.tsx` — wrap in `HelmetProvider`.
- `App.tsx` — public routes under `PublicLayout`; `*` → public `NotFound`; **`RootRedirect` is
  deleted** (see below).
- `pages/Login.tsx` — the footer back-link §2.5 asked for, deferred from Phase 3 because `/`
  redirected to `/login` and the link would have been a loop.
- `components/layout/navigation.ts` — `Leads` under admin → Business.
- `types/index.ts` — `Lead`, `LeadKind`, `LeadStatus`, `AddOn`, `PublicPlans`.
- `index.html` — the default `<title>`/description become the marketing ones; per-route tags come
  from Helmet.

---

## `/` changes owner — decided explicitly

`RootRedirect` currently sends everyone at `/` to `/login`, or to their role home if signed in.
Phase 8 makes `/` the public home. The question STATE.md asked to settle: **what happens when a
signed-in user visits `/`?**

**Decision: `/` renders the public home for everyone, signed in or not.** The header swaps "Sign in"
for "Go to dashboard".

Why not keep bouncing signed-in users to their dashboard: a signed-in family member who clicks a
link to `/pricing` or `/about` — or a footer link from inside the app — must be able to read it. A
redirect at `/` and not at `/pricing` is an inconsistency someone would have to remember. Marketing
pages are public; the product is behind `ProtectedRoute`; that line does not move.

**`ProtectedRoute` behaviour does not change at all.** Its unauthenticated redirect still goes to
`/login`, not to `/`.

---

## Order of work

1. `core/ratelimit.py` budgets, enums, model, schemas, service, routers, `main.py`. **Backend tests
   green before a line of TSX.**
2. `npm install react-helmet-async`; `HelmetProvider`; `Seo`; `PublicLayout`; routing skeleton with
   all 15 routes stubbed — verify navigation and the 404 before writing copy.
3. `PricingGrid` + `PlanCard` + `EntitlementList` against the live `/public/plans`.
4. `LeadForm` → `/leads`; `AdminLeads` reads it. **Journey 1 end to end at this point.**
5. Write the 14 pages' copy.
6. `robots.txt`, `sitemap.xml`, JSON-LD, skip-link, `Login` back-link.
7. Vitest, live browser pass at 375/768/1024/1440, STATE.md, commit.

---

## Acceptance

```bash
cd backend  && .venv/bin/python -m pytest            # > 365, all green
cd backend  && .venv/bin/python -m app.seed          # clean
cd frontend && npx tsc -p tsconfig.json --noEmit     # zero errors, no `any`, no @ts-ignore
cd frontend && npm run build                         # clean
cd frontend && npx vitest run                        # > 71
```

Live, in Chrome, at 375 / 768 / 1024 / 1440:

1. All 15 public routes render, every header and footer link resolves, `/nonsense` shows the 404.
2. `/pricing` shows ₹2,500 / ₹3,500 (Recommended) / ₹4,500 with the annual toggle showing
   ₹25,000 / ₹35,000 / ₹45,000, and the numbers match `core/pricing.py`.
3. Submit `/contact` → sign in as admin → the lead is on **Admin → Leads** → mark it contacted.
4. Submit repeatedly → 429 with a human message, not a stack trace.
5. Signed-in user opens `/` → public home with "Go to dashboard"; `/family/dashboard` still guarded.
6. `/login` footer link returns to `/` and does not loop.

## Do not break

- Patient 1 is Lakshmi, nurse 1 is Anitha, Anitha holds exactly one open visit today, Lakshmi
  carries no open alert. `tests/test_seed.py` pins all four.
- `SMALL` gains **no** leads, so the 365 existing tests are untouched.
- Any new process-global goes in `clean_process_state`. (This phase adds none — it reuses `limiter`.)
- `core/pricing.py` is read, never written.
