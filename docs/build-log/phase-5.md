# Phase 5 — Seed a real operating business (§2.4)

**Goal:** the demo stops being one patient and one nurse. Every screen that today renders a single
row renders an operating home-care business: 28 patients across six Bangalore zones, 14 nurses, 90
days of visit history, vitals that read as clinical trajectories rather than noise, and an alert
queue with real resolution times behind it.

**Constraint that shapes everything below:** `tests/conftest.py` seeds a template database *once per
session* and copies it per test, and 183 tests assert against the Phase-4 dataset by hand
(`total == 15` logged doses, `percentage == 87`, `paid_months == 14`, `active_subscriptions == 4`).
A realistic dataset would break most of them for no gain — they are testing the *application*, not
the population. So Phase 5 ships **two profiles from one code path**, and the suite keeps the small
one.

---

## The two profiles

| | `SMALL` | `FULL` |
|---|---|---|
| Used by | `tests/conftest.py` | `python -m app.seed` (default) |
| Content | **exactly the Phase-4 dataset** | the Phase-4 dataset **plus** the wider population |
| Users | 3 + Meera | 3 admins, 14 nurses, 18 families (+ Meera) |
| Patients | 1 (Lakshmi) | 28 |
| Visits | 6 | ~1,440 over 90 days + a forward week |
| Alerts | 0 | 30 resolved + 4 active |
| Business | full 14-month history | same, plus 16 more subscriptions on a spread of tenures |

`FULL` is `SMALL` **plus** a population, never a different construction. The demo core — Darren,
Anitha, Ravi, Lakshmi, her thresholds, her three medications, the four HISTORY readings, the 87%
adherence and today's 10:30 visit — is built by the same function in both. That is why the existing
suite passes untouched, and it is also why the live demo path (record 148/92 → alert → family and
admin see it → admin resolves) is preserved by construction rather than by care.

## Invariants the seed must not break

Extracted from the suite before writing a line. Every one of these is asserted somewhere today:

1. **Patient 1 is Lakshmi D'Souza**, owned by `family@doordoctor.in`.
2. **Nurse 1 is Anitha Kumar**, and today's 10:30 visit is hers.
3. **Anitha has exactly one open visit today** — `scheduled_visit_id` takes `scheduled[0]` from her
   board, so a second scheduled visit today (or any open visit from an earlier day) would silently
   point the alert tests at the wrong patient.
4. **Lakshmi has zero active alerts in the seed** — `test_resolved_alert_leaves_the_dashboard`
   asserts the dashboard empties to `Stable` after the one alert the test raises is resolved.
5. **The demo family's subscription is the first family subscription created** — the loyalty test
   selects it with `select(Subscription).where(family_user_id.is_not(None))`, i.e. by id order.
6. **The demo family has exactly one converted referral and no pending ones** (Meera).
7. Adherence for Lakshmi is 13/15 = 87%.

`tests/test_seed.py` (new) asserts 1–4 against the **FULL** profile, so the wider population cannot
quietly break the demo it exists to surround.

---

## File-by-file

### `backend/app/seed.py` → `backend/app/seed/` (`git mv`, history preserved)

| File | Contents |
|---|---|
| `__init__.py` | barrel — `seed`, `reset_database`, `demo_reset`, `SMALL`, `FULL`. `from app.seed import seed` keeps working, which is what `tests/conftest.py` imports. |
| `__main__.py` | the CLI, so `python -m app.seed` keeps working. `--keep` (Phase 4), `--small`, `--demo-reset`. |
| `demo_data.py` | every fixed roster: `SeedProfile`, zones, nurses, admins, families, patients, medication sets, threshold table, excursion table, subscription tenures. No logic. |
| `generators.py` | pure deterministic functions: vitals trajectories, visit schedules, adherence plans. No database, no clock — everything takes its inputs and returns values, so they can be tested directly. |
| `core.py` | the Phase-4 demo core, carried across intact. |
| `population.py` | the wider population, `FULL` only. |
| `reset.py` | `--demo-reset`. |
| `business.py` | `_seed_business()` carried across intact — it builds billing history by *calling* `billing_service` and `subscription_service`, which is what proves the loyalty and credit arithmetic on every run. Extended, not rewritten. |

### Determinism

- One module constant `RANDOM_SEED`. Every generator takes its own `random.Random(RANDOM_SEED + n)`.
  **The global `random` module is never touched** — one library call to `random.seed()` anywhere else
  in the process would otherwise change the dataset.
- Dates are relative to `now().date()` deliberately: the demo must look current on any day it is
  opened. "Deterministic" here means *same day, same database* — asserted by hashing the generated
  values, not by freezing the clock.
- STATE.md flagged `payment_gateway.charge()` minting `MAN-<random>` via `secrets`. Seeded invoices
  now pass an explicit `reference=`, so payment references are stable too.

### bcrypt — measured at 0.729 s per hash

35+ demo users would be **~25 s of every seed run**, and the test suite pays it once per session.
Every demo account shares `Demo@123`, so the digest is computed **once** and reused. Identical
`password_hash` values across demo accounts are fine here — the password is published in STATE.md —
and would not be in production. The reason is written at the call site.

### Vitals as trajectories, not noise

Each patient gets an **arc** over the 90 days, not a random walk:

| Arc | Shape |
|---|---|
| `stable` | flat, with a smooth physiological wobble |
| `improving` | starts high, drifts down — a medication change that worked |
| `drifting` | creeps up across the window — the reason three of the four active alerts exist |
| `episodic` | flat, with discrete named events (a fever, a glucose excursion) |

The wobble is a sine over the visit index plus a small jitter, so a chart shows a *line with a
shape*. Every generated reading is then **clamped inside the patient's thresholds**, which is what
makes the alert count exact: a reading only breaches when an excursion puts it out of range.

### Alerts — 30 resolved + 4 active, by construction

`demo_data.EXCURSIONS` is a table of exactly 34 entries: `(patient slot, visits-from-latest, kind,
resolved?)`. Each one overrides one or two metrics on one visit's reading. The alerts are then
raised by **`alert_service.create_threshold_alert`**, the real engine, over the real readings — so
"every breaching reading has an alert" is true of the seed for the same reason it is true in
production. `test_seed.py` asserts exactly that, plus the 30/4 split.

Resolved alerts get realistic acknowledgement and resolution timestamps (median ~40 minutes to
acknowledge), because an alert queue where everything resolved instantly is not a demo of an SLA.
Their notifications are backdated and marked read; the four active ones stay unread, so the bell
shows four items rather than 136.

### Today's board — 6 scheduled / 1 unassigned / 1 in-progress

Today is built **explicitly**, not by the cadence generator, because its exact shape is specified.
Seven completed visits (07:00–10:00) fill the day out to the ~15 that the 90-day rate implies, then
10:00 in-progress, then the open block from 10:30. Lakshmi's is at 10:30 with Anitha and is the only
scheduled visit Anitha has, preserving invariant 3.

### `--demo-reset`

Rewinds **exactly what a demo run changes**: Lakshmi's visit today goes back to `scheduled`, the
readings and dose logs captured against it are deleted, and the alerts it raised today go with their
notifications. Between two investor meetings you want the 148/92 path back without rebuilding
fourteen months of billing history and renumbering every invoice.

The first draft deleted and rebuilt the *whole* board, which meant reconstructing the twenty-eight
patient slots from row order so it could re-derive who was scheduled when. That is a second copy of
the seed's structure, living in a module whose only job is to undo things, and it would rot the
first time the roster changed. Nobody touches the other fourteen visits during a demo, so nothing
needs to restore them.

---

## Changes outside `seed/`

Two of these are bugs the dataset exposes rather than seed work.

1. **`visit_service.list_today_visits` queried the newest 100 visits and then filtered to today.**
   With a forward week on the schedule, more than 100 visits are dated in the future and *today
   falls out of the window* — the admin dashboard's board would render empty. It now queries the day
   bounds directly. Real bug, only visible at scale.
2. **`visit_service.list_visits_for_user` limit 100 → 250.** Same cause: with a forward schedule the
   first 100 rows are all future-dated and the admin visit table shows no history. 250 is a
   stopgap; Phase 10's visit board replaces this list with a windowed one.
3. **`tests/conftest.py`** — seeds `profile=SMALL` explicitly. One line.

## Deliberately deferred

- **Quota enforcement at the point of use** stays deferred (Phase 4 deferred it here). The recorded
  §2.4 dataset is ~1,400 visits over 90 days for 28 patients — **16.7 visits per patient per
  month**. The Phase-4 entitlements are 4 / 8 / 12 per month, and those numbers are `ASSUMED`.
  Enforcing an invented limit against a recorded volume would refuse the visits the demo is
  specified to contain. The contradiction is itself evidence about the real §3 and is recorded in
  STATE.md; enforcement waits until the numbers are reconciled.
- **A real `zone` column** on `Patient` / `Nurse`. Zones exist in this seed as addresses and as the
  nurse→zone assignment table in `demo_data.py`, which is enough for six recognisable Bangalore
  areas across the patient list. Phase 10 owns the zone view and the ~30–45 subscriber break-even,
  and should lift that table into a column then.


---

## Executed — what actually happened

Shipped as planned, with three findings worth recording.

### The dataset exposed two real bugs, both in `visit_service`

Neither was reachable with six visits in the database, and both fail silently.

1. **`list_today_visits` returned an empty board for admins.** It pulled the newest 100 visits and
   *then* filtered to today. A forward week of scheduling puts more than 100 visits after today, so
   today fell off the end of the page and the operations dashboard rendered nothing. The day window
   is now in the query. Measured before the fix: `admin today count: 0`, against a database holding
   fifteen visits scheduled for that day.
2. **`list_today_visits` also kept a nurse’s *future* visits on their board**, contradicting its own
   docstring ("still-open visit from an earlier day"). Anitha’s board came back with ten visits
   stretching a week out. It now keeps unfinished work from before today and nothing after it.

`list_visits_for_user`’s cap went 100 → 250 for the same reason: newest-first ordering meant the
admin visit table was entirely future-dated. That is a stopgap and is written down as one.

### The clamp was flattening the charts

Readings are clamped inside each patient’s thresholds so that only `EXCURSIONS` can breach — that is
what makes the alert count exact. But the first amplitudes put a treated hypertensive’s baseline at
132 against a ceiling of 136, so **27% of systolic readings came out pinned to the clamp** and every
such patient’s chart drew a flat line with the trajectory sheared off. The arc was in the arithmetic
and never reached the database.

Baselines were re-sized against the clamp rather than chosen freely, and lowered to what a patient
*under treatment* actually reads — they are on amlodipine and metformin, which is the point of the
medication. Pinned readings: **336 → 29 of 1,256**. Two tests hold it there.

### `_bill_history` could not bill an annual subscriber

`ConflictError: This invoice has already been paid.` Ten months into a twelve-month term there are
no *ended* periods to settle, so the loop billed the period still running and the current-period
invoice then came back as that same paid row. It now bills only periods whose end has passed. This
was latent in Phase 4 — nothing was sold annually until Rohit Verma’s NRI account.

### Numbers as built

```
28 patients · 14 nurses (13 active) · 18 families · 3 admins · 6 zones
1,453 visits · 1,290 readings · 3,490 logged doses · 34 alerts (30 resolved, 4 open)
20 subscriptions · 182 invoices · MRR ₹2,30,250
seed runtime 5.4 s   ·   tests 183 → 210, all green
```

Today’s board came out exactly as §2.4 specifies: 7 completed, 1 in progress, 1 unassigned, 6
scheduled — Lakshmi’s 10:30 with Anitha among them, and the only open visit Anitha holds.

Verified live in Chrome at 375 / 768 / 1024 / 1440 across all three roles and twelve screens, with
zero console errors.
