# Phase 9 — Clinical features (§4.2–4.9)

**Goal:** the platform stops being "visits and vitals with a business around it" and becomes a
clinical service. Labs get ordered and flagged, a doctor consult is booked against a real
entitlement, a care manager owns a caseload at a recorded ratio, every patient carries an
explainable Senior Safety Score, mood is screened with a real instrument, a wearable can push a
reading in on its own, and anything urgent opens an escalation with a visible timeline and a clock
running against it.

Phases 1–8 closed the "credible demoable platform" line. This is the first phase whose output a
clinician would recognise as clinical.

---

## The one idea this phase is built around

> **Every clinical claim must be explainable to the family it is about.**

A safety score a family cannot have broken down for them is worse than no score, because it looks
authoritative. A lab flagged "high" without the reference range beside it is a diagnosis by
implication. An escalation that says "we notified everyone" without saying who, on what channel, at
what time, is a promise, not a record.

So the rule for this phase, everywhere: **store the components, not just the conclusion.**

- `SafetyScore` stores every weighted component with its own value, points and one-line detail — the
  total is derived from stored parts, never the other way round.
- `LabResult` stores the reference range it was compared against, so "high" is arithmetic the reader
  can re-run.
- `EscalationStep` is one row per contact attempt, per channel, per recipient, with its own
  timestamp — the timeline is data, not prose.
- `Screening` stores the individual answers, not only the total, because PHQ-2's two questions mean
  different things.

---

## Decisions taken with the founder before writing code (2026-08-22)

| Question | Answer | Consequence |
|---|---|---|
| §4.2–4.9 was never supplied — including §4.8's "documented three actions" | **Proceed with `ASSUMED` values** | Same treatment as Phase 4's §3 and Phase 7's §2.3: every invented value lives in one file, is marked `ASSUMED` in the source, and gets a reconciliation table in STATE.md when the phase closes. |
| Care manager: profile on an admin user, or a fourth `UserRole`? | **Profile on an admin user** | `CareManager` points at an existing admin `User`. `core/dependencies.py` is untouched, the three-way route guard survives, and no existing authorization test changes. |
| `Alert` has no resolution note, and §8's journey 3 needs one | **Add the column now** | Phase 9 already adds three alert sources and is in this code. `alert_service.resolve` gains an optional note rather than Phase 10 revisiting alerts twice. |

---

## The one-file rule, applied from the start

Phase 4 put every price in `core/pricing.py`. Phase 7 put every intent in
`services/assistant_intents.py`. Both survived a missing spec section because reconciling stayed a
one-file edit. Phase 9 does the same:

**`backend/app/core/clinical.py`** — every clinical constant this phase invents. Lab panels and
their reference ranges, safety-score weights and bands, SLA durations, the wearable HR range and
SpO2 floor, the three wearable actions, PHQ-2 cadence, consult duration and cancellation window,
escalation ladder.

Like `core/pricing.py` it **imports nothing from the application**, so anything may read it and
nothing can circle back.

> **Deviation from the STATE brief, deliberate.** The brief suggested the safety-score weight block
> live in `services/safety_score.py`. It goes in `core/clinical.py` instead, and the service holds
> only the arithmetic. That is the same split as `core/pricing.py` (constants) against
> `subscription_service.py` (logic), and it means *one* file to hand the founder when §4 arrives
> rather than two. `services/safety_score.py` must not contain a number.

**Never inline an assumed value anywhere else.** The moment a weight is typed into a second file the
one-file promise is broken and reconciling stops being cheap.

### What is recorded vs what is invented

| Recorded — enforce as-is | Invented — `ASSUMED` in `core/clinical.py` |
|---|---|
| Care manager **1:20 shared / 1:10 dedicated** | Which tier gets which (already assumed in Phase 4) |
| Safety score is **0–100 and deterministic** | Every weight, every band boundary |
| **10+ point drop in 30 days** raises an alert | The alert's wording and severity |
| Labs: abnormal → alert **+ 24-hour follow-up task** | Panel contents, reference ranges, which flags count as abnormal |
| Telemedicine **2/month on Premium** | Consult duration, cancellation window, the doctor |
| Wearables: **SpO2 <90% or HR out of range** | The HR range, and the "three actions" themselves |
| Escalation is **108 → nurse → admin** (Phase 7 pinned it) | SLA durations |
| Blood panel **₹499**, pill organiser **₹199** (`core/pricing.py`) | How one is ordered |

**PHQ-2 is a published instrument.** The two questions, the 0–3 answer scale, the 0–6 total and the
**cutoff of 3** come from the instrument itself, not from the founder and not from me. They are
marked `INSTRUMENT`, not `ASSUMED` — reconciling §4 must not "correct" them. Only the *cadence*
(how often to screen) is assumed.

---

## Two structural changes everything else depends on

### 1. `alert_service` gains a general creation path

Three new alert sources arrive this phase (abnormal lab, safety-score drop, wearable breach) and
none of them has a `Vital` to point at. `create_threshold_alert(db, patient, vital, breaches)`
cannot serve them.

```python
def create_alert(db, *, patient, alert_type, severity, title, message,
                 breaches=None, vital=None) -> Alert
```

`create_threshold_alert` becomes a thin wrapper over it, so the threshold path's behaviour is
unchanged and still the only thing that computes `severity_for_breaches`. The rule that
**nothing outside `alert_service` constructs an `Alert` row** holds — the Phase 5 seed depends on it.

### 2. `Alert.resolution_note`

`resolve(db, alert, user, note=None)`. Nullable `Text`, capped in the schema. Existing callers pass
nothing and behave identically.

---

## Internal order — seven stages, committed as they land

Phase 9 is the largest remaining scope and the Phase 2 incident note is what an uncommitted pile of
work costs. Each stage below ends green and is committed before the next begins.

| # | Stage | New models | New service | Routes |
|---|---|---|---|---|
| 0 | Foundations | — | — | — |
| 1 | Senior Safety Score | `SafetyScore` | `safety_score` | 3 |
| 2 | Labs + follow-up tasks | `LabOrder`, `LabResult`, `FollowUpTask` | `lab_service`, `task_service` | 7 |
| 3 | Telemedicine | `Consult` | `consult_service` | 5 |
| 4 | Care manager | `CareManager`, `CareAssignment`, `CareInteraction` | `care_service` | 6 |
| 5 | PHQ-2 screening | `Screening` | `screening_service` | 3 |
| 6 | Wearables + ingest | `Device`, `DeviceReading` | `device_service` | 6 |
| 7 | Hospital booking, escalations, timeline | `HospitalBooking`, `EscalationEvent`, `EscalationStep` | `escalation_service` | 8 |
| 8 | Frontend, seed, verification | — | — | — |

---

## Stage 0 — foundations

- `core/clinical.py` — the constants module described above.
- `models/enums.py` — `LabOrderStatus`, `LabFlag`, `TaskStatus`, `TaskKind`, `ConsultStatus`,
  `CareManagerKind`, `CareChannel`, `ScreeningInstrument`, `DeviceKind`, `EscalationTrigger`,
  `EscalationStatus`, `EscalationStepStatus`, `HospitalBookingStatus`, `SafetyBand`.
- `alert_service.create_alert` + `Alert.resolution_note` (above).
- `subscription_service.release_quota(db, subscription, quota, amount=1, as_of=None)` — a cancelled
  consult inside the cancellation window gives the allowance back. Floors at zero; it is the exact
  inverse of `consume_quota` and lives beside it so the pair cannot drift.

## Stage 1 — Senior Safety Score

`services/safety_score.py` holds arithmetic and no numbers. Six components, weights in
`core/clinical.SAFETY_WEIGHTS`, summing to 100 — a test re-runs that sum so a future edit cannot
silently produce a 94-point scale.

| Component | Weight | Reads |
|---|---|---|
| Vital stability | 30 | share of readings inside the patient's own thresholds |
| Medication adherence | 25 | `medication_service.adherence_for_patient` |
| Care continuity | 15 | completed vs scheduled visits |
| Alert burden | 15 | alerts raised in the window, by severity |
| Mood | 10 | most recent PHQ-2, inverted |
| Connected monitoring | 5 | device readings present and in range |

Each stores `{key, label, weight, value, points, detail}`. `detail` is one plain sentence a family
can read — it goes through `summary_service.plain_metric_label()` wherever it names a measurement,
so Phase 6's vocabulary rule is not quietly broken by a new surface.

**A component with no data does not score zero.** No PHQ-2 on file must not read as "worst possible
mood". Missing components are dropped and the total is rescaled across the weights that *did* have
data, with `covered_weight` stored so the rescaling is visible. A test pins this — it is the single
most likely way this feature silently defames a patient.

The **10-point drop in 30 days** (recorded) is checked on every recalculation against the newest
score at least 30 days old, and raises an alert through `alert_service.create_alert`.

Routes: `GET /patients/{id}/safety-score`, `GET /patients/{id}/safety-score/history`,
`POST /patients/{id}/safety-score/recalculate` (admin).

## Stage 2 — Labs and follow-up tasks

`core/clinical.LAB_PANELS` defines each panel: code, name, which add-on it bills as, and its
analytes with reference low/high and unit.

`lab_service.order()` resolves payment in one place: consume the `lab_panels` quota if the plan has
one left, otherwise raise an `ADDON` invoice line at `pricing.ADD_ONS_BY_CODE["blood_panel"]` —
**Phase 4's deferred add-on flow, and labs are its first buyer, exactly as planned.** The order
records which route it took.

`lab_service.record_results()` flags each analyte against its stored range. Any abnormal flag →
one alert via `create_alert` **and** a `FollowUpTask` due in 24 hours (both recorded). One alert per
order, not per analyte — a panel with four high values is one clinical event.

`FollowUpTask` is general from the start (`source_type` + `source_id`), because Stage 6 and Stage 7
both create tasks too and a lab-specific table would be rewritten twice.

## Stage 3 — Telemedicine

**The first genuinely enforced quota.** `consult_service.book()` calls
`subscription_service.consume_quota(db, sub, "telemedicine")`, which raises `ConflictError` → 409.
Essential's allowance is 0, so booking on Essential is refused by the entitlement, not by a tier
check. Cancelling inside the window calls `release_quota`.

**Visits stay unenforced**, and this is the phase to say why in the source rather than only in
STATE: §2.4 records 16.7 visits per patient per month against an assumed top tier of 12, so
enforcing that limit would refuse the visits the demo is specified to contain. Telemedicine and lab
panels have no such contradiction. The comment goes in `consult_service` next to the call, where the
next person to wonder will be standing.

## Stage 4 — Care manager

`CareManager` is a row pointing at an admin `User` with a `kind` (`shared` | `dedicated`) and a
capacity taken from `pricing.RATIO_SHARED` / `RATIO_DEDICATED` — **recorded, so enforced.** Assigning
past capacity is refused with the count in the message.

Which kind a patient is entitled to comes from `subscription_service.entitlement(sub, CARE_MANAGER)`
— never from a tier name. `CareInteraction` logs calls, visits, messages and notes against the
patient with a channel and a duration.

## Stage 5 — PHQ-2

Real instrument, real wording, real scoring, cutoff 3. `Screening` stores both answers and the total.
A positive screen creates a `FollowUpTask` (cadence and due window `ASSUMED`) and **never** an alert
— a low mood score is not a threshold breach and dressing it as one would be a diagnosis. The nurse
records it from the visit screen.

## Stage 6 — Wearables

`Device` carries a **sha256 of its API key**, never the key — the same discipline as Phase 3's reset
tokens, for the same reason. The plaintext key is returned exactly once, at registration.

`POST /ingest/device-readings` with `X-Device-Key`. Treated with the same suspicion as `POST /leads`:
payload capped in the schema, batch size capped, rate limited per device through the existing
`core/ratelimit` (`DEVICE_INGEST_PER_DEVICE`), and **no device-supplied string ever reaches a log** —
only the device id and a count.

Recorded trigger: **SpO2 < 90% or heart rate outside range**. The range itself is `ASSUMED`.

**The three actions.** §4.8 names "the documented three actions" and never lists them. Derived, and
marked `ASSUMED` in `core/clinical.WEARABLE_ACTIONS` so the founder can correct all three in one
place:

1. Raise a **critical alert** on the patient (`alert_service.create_alert`).
2. Open an **escalation event** and notify family and admin **in parallel** on two channels through
   `notification_delivery` — the Phase 3 seam, not a second one.
3. Create a **follow-up task for the assigned nurse** to check on the patient, due inside the
   critical SLA.

`scripts/simulate_wearable.py` posts against a registered device so the path can be demonstrated
without hardware.

## Stage 7 — Hospital booking, escalations, the timeline

`EscalationEvent` + `EscalationStep`. Steps are written **one per recipient per channel**, in
parallel (same `sequence`, so the UI can render them as a fan-out rather than a queue), following
the recorded **108 → nurse → admin** ladder Phase 7 pinned.

`HospitalBooking` sits in an admin queue with `sla_due_at` computed from
`core/clinical.SLA_DURATIONS` and a stored `breached_sla` flag. The clock is stored, not computed at
render time, so a booking that breached last week still says so.

## Stage 8 — Frontend, seed, verification

New screens, all built from `components/ui/` and `chartTheme.ts`:

| Role | Route | Screen |
|---|---|---|
| family | `/family/labs` | Lab orders, results with reference ranges, order a panel |
| family | `/family/consults` | Book and cancel a doctor consult, allowance remaining |
| family | `/family/care-team` | Care manager, recent interactions, safety score breakdown |
| admin | `/admin/escalations` | SLA queue: escalations + hospital bookings, timeline drawer |
| admin | `/admin/labs` | Orders awaiting results, record results |
| admin | `/admin/care` | Care managers, caseloads against capacity, assignment |
| nurse | (visit detail) | PHQ-2 form, safety score context, device readings |
| family | (dashboard) | `SafetyScoreCard` above the detailed record, below the plain summary |

`components/clinical/EmergencyBlock.tsx` — the permanent **"In an emergency, call 108"** block,
rendered on every clinical screen listed above. One component so the number and the wording cannot
drift, and so Phase 10 can change the ladder in one place.

**Seed.** All Phase 9 drama goes in `FULL` (`population.py`). `SMALL` (`core.py`) gets only what the
demo family needs and **nothing that raises an alert**: one completed lab order with normal results,
a care manager, two PHQ-2 screenings below cutoff, a device with in-range readings, and a computed
safety score. `tests/test_seed.py` pins that **Lakshmi carries no open alert** and this phase adds
three ways to break that.

---

## Phase 9 acceptance

```bash
cd backend  && .venv/bin/python -m pytest                  # 408 + new, all green
cd backend  && .venv/bin/python -m app.seed                # clean
cd backend  && .venv/bin/python -m app.seed --small        # clean
cd frontend && npx tsc -p tsconfig.json --noEmit           # zero errors
cd frontend && npx vitest run                              # 87 + new
cd frontend && npm run build                               # clean
```

Plus, live in Chrome at 375 / 768 / 1024 / 1440:
a lab ordered against an entitlement and again as a ₹499 add-on; an abnormal result raising one
alert and one 24-hour task; a consult booked on Care Plus and the **second one refused with a 409**;
a PHQ-2 recorded by the nurse; `simulate_wearable.py` pushing an SpO2 of 88 and all three actions
firing; the escalation timeline showing parallel notification; and the safety score breaking down
into components that add up to what it says.

## Do not break

- Patient 1 is Lakshmi, nurse 1 is Anitha, **Anitha holds exactly one open visit today**, and
  **Lakshmi carries no open alert.**
- `/public/plans` and authenticated `/plans` stay byte-identical.
- `core/pricing.py` is read, never written.
- Any new process-global goes in `clean_process_state`.
- Backend **408**, Vitest **87**. The counts only grow.

---

# As executed

Written after the phase closed. The plan above is what was intended; this is what happened and where
the two differ. **The differences are the useful part** — a plan that matched its execution exactly
would mean nothing was learned.

## Staging changed once, on the first day

The plan put `SafetyScore` in stage 1 and each other model in its own stage. That does not work: the
safety score reads **screenings** (stage 5) and **device readings** (stage 6), so its service cannot
be written before those tables exist.

**All twelve Phase 9 tables therefore landed together in stage 1** — one schema pass, one
`models/__init__.py` edit, one re-seed. Services then followed stage by stage as planned. If a
future phase has a component that reads across its own stages, do the same: models are cheap and
interdependent, services are not.

Committed as six commits rather than eight — stages 4+5 (care manager, PHQ-2) and 6+7 (wearables,
escalations) each landed together, because in both cases the second depended on the first and
splitting them would have committed a half-wired feature.

| Commit | Stage(s) | Tests after |
|---|---|---|
| `9a88b6d` | 0–1 — clinical.py, general alert path, all models, safety score | 434 |
| `8fe3299` | 2 — labs and follow-up tasks | 469 |
| `375a42b` | 3 — telemedicine | 492 |
| `19d4ce5` | 4–5 — care managers, PHQ-2 | 544 |
| `3063c17` | 6–7 — wearables, escalations, hospital | 608 |
| `3a1833a` | 8a — the clinical seed | 623 |
| `3fe4e7a` | 8b — six screens, the emergency block | 623 · Vitest 113 |
| `43693d9` | fixes found in the browser | 623 · Vitest 121 |

## Where the plan was wrong, or too thin

- **The plan said "`services/safety_score.py` (the weight block)".** The weights went in
  `core/clinical.py` instead and the service holds only arithmetic — the same split as `pricing.py`
  against `subscription_service.py`. That means **one** file to hand the founder when §4 arrives, not
  two. A test now asserts the two files' numeric literals are disjoint, so the split is enforced.
- **The plan did not anticipate a heterogeneous `breached_parameters`.** It assumed the three new
  alert sources would slot into the existing alert rendering. They do not: a threshold has a bound
  and a direction, a lab result has a *range*, a wearable breach has a sentence. This was the phase's
  most serious bug (both alert screens blank) and it was invisible to 623 backend tests.
  `lib/breach.ts` is the fix and the place a fourth source declares itself.
- **The plan's acceptance list said "a consult booked on Care Plus and the second one refused with a
  409".** Care Plus includes **one** consult a month, so there is no second to refuse through the UI —
  the button correctly disables. The 409 was verified against the API directly, and its sentence is
  what the toast renders. Worth knowing before writing a similar acceptance line.
- **Nothing in the plan protected the demo account's *demonstrability*.** Two seed choices were
  correct behaviour and dead demos: a PHQ-2 recorded three days ago (so the nurse screen correctly
  hid the form) and the month's only consult already spent. **When seeding a feature, check that the
  demo account can still perform it**, not just that the data exists.

## What the tests could not have caught

Five of the six bugs were found by driving the real app. The backend suite was green throughout.
That is not an argument for more backend tests — it is the reason the live pass is in the
per-phase verification list, and it has now earned its place in four consecutive phases.
