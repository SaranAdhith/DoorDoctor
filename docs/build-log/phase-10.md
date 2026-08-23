# Phase 10 — Trust, operations and notifications (§4.10–4.18)

**Goal:** the platform stops asking to be believed and starts producing evidence. The nurse at the
door has a credential a family can read and a verification record behind it. The visit that says it
happened at the patient's home says how far away the phone actually was. The dose that was given has
a photograph. The alert that says "we told the family" says on which channel, at what time, and which
channel could not be reached. The family that asks what DoorDoctor holds about their parent can
download it and can ask for it to be destroyed. And both nurses and admins get a day they can
actually work, rather than a table.

Phase 9 made the platform clinical. Phase 10 makes it accountable.

---

## The one idea this phase is built around

> **A promise the platform cannot evidence is a promise it should not make.**

Phase 9's rule was *store the components, not just the conclusion*. Phase 10's is its operational
twin, and it cuts both ways — it forbids the confident lie **and** it demands the honest negative:

- `verified` is earned by arithmetic against a stored distance, not asserted. And **`unavailable` is a
  first-class outcome**, not a failure state, because "we do not know where the nurse was" is a true
  sentence the platform must be able to say out loud.
- A notification that could not be sent is a **recorded attempt that could not be made**, never an
  omission. Phase 9 already found the shape of this bug: a "dual-channel" promise made of SMS + push
  is one channel wearing two names.
- A credential is a row with a verifier and a date on it, or it is not shown as verified.
- Consent is a stored decision with a version, a timestamp and an actor — and withdrawing it is the
  same kind of record, not the absence of one.
- The audit log is **append-only in the engine, not by convention**, and it records the erasure that
  empties every other table.

Everything below is a consequence of that one sentence.

---

## Decisions taken before writing code

| Question | Decision | Consequence |
|---|---|---|
| §4.10–4.18 will be missing, like §3, §2.3 and §4.2–4.9 | **Proceed with `ASSUMED` values**, same as three phases running | One file, marked in the source, reconciliation table in STATE.md when the phase closes |
| `core/clinical.py` or a new constants module? | **New `core/ops.py`** | A geofence radius, a photo retention window, a quiet-hours window and a channel-routing table are *operational*, not clinical. `clinical.py` is the file a clinician reconciles; `ops.py` is the file an operator reconciles. Keeping them apart keeps the two conversations apart. Same rule as its siblings: **imports nothing from the application** |
| Care Circle now, `PatientFamilyMember` in Phase 11 — two tables? | **One table.** `care_circle_members` carries a **nullable `user_id`** | Phase 11's multi-family work becomes *populate `user_id` and migrate authorization onto this table*, not *build a second membership table beside it*. Recorded here so Phase 11 does not duplicate it |
| Does an out-of-range check-in block the visit? | **No — it opens a task** | A nurse in a stairwell with a bad fix must still be able to work. Refusing the check-in would make the honest thing (letting the phone report a real position) the thing that stops the nurse working, and the dishonest thing (turning location off) the thing that lets them through |
| Who executes an erasure? | **Family requests, admin executes** | It is irreversible and it destroys a named person's health record. One click by one member of a shared account is not a good design for that. It also makes the audit log demonstrably load-bearing rather than decorative |
| Alert SLA — new clock or the Phase 9 one? | **The Phase 9 one** | `EscalationEvent` already stores budget + deadline + observed breach. `Alert` gains the same three columns and the same `_refresh_sla` shape. Two SLA implementations would drift within a phase |

### One new dependency, and it is already installed

`pillow` — 12.3.0, already on this machine as a WeasyPrint transitive. Phase 10 imports it
**directly** (magic-byte validation and EXIF stripping on dose photos), so it goes into
`requirements.txt` explicitly rather than being borrowed. Nothing to install.

---

## The one-file rule: `backend/app/core/ops.py`

Every operational constant this phase invents, and nothing else may restate one.

| Block | Contents | Provenance |
|---|---|---|
| Geofence | `GEOFENCE_RADIUS_M = 150` · accuracy ceiling · earth radius for the haversine | radius **RECORDED**; the rest `ASSUMED` |
| Location | The three classification names | **RECORDED** |
| Photos | max bytes, allowed types, retention days, upload root name | `ASSUMED` |
| Quiet hours | window start/end in IST, and the rule that critical overrides | `ASSUMED` |
| Channel routing | per-notification-type channel order, and the critical dual-channel rule | dual-channel for critical is **RECORDED**; the order is `ASSUMED` |
| Care circle | member cap, the relationship vocabulary | `ASSUMED` |
| Consent | the consent kinds and the current policy version | `ASSUMED` |
| Privacy | what erasure destroys, what it retains, and why | `ASSUMED` — but the *reasons* are written out in the source, because a family reads them |
| Zones | the break-even band **30–45 subscribers** | **RECORDED** |
| Ops SLAs | alert-queue budgets (reuse `clinical.SLA_DURATIONS_MINUTES` — do **not** restate) | see note |

> `ops.py` may not restate a clinical SLA. Where the alert queue needs one it imports
> `core.clinical.SLA_DURATIONS_MINUTES`. `ops.py` importing `clinical.py` is fine — both import
> nothing from the *application*, and the dependency runs one way only.

---

## Internal order — nine stages, committed as they land

| # | Stage | New models | New/extended service | Routes |
|---|---|---|---|---|
| 0 | Foundations | `AuditEvent` | `audit_service`, `storage` | — |
| 1 | Nurse trust + GPS classification | `NurseCredential` | `nurse_service`, `visit_service` | 5 |
| 2 | Medication depth | `Attachment`, `PillOrganiserFill`, `MedicationChange` | `medication_service`, `attachment_service` | 8 |
| 3 | Care Circle | `CareCircleMember` | `care_circle_service` | 5 |
| 4 | Consent, audit, privacy | `Consent`, `ErasureRequest` | `consent_service`, `privacy_service` | 9 |
| 5 | Notification routing | `NotificationPreference` | `notification_service`, `notification_delivery` | 3 |
| 6 | Nurse ops | — | `nurse_ops_service` | 5 |
| 7 | Admin ops | `Alert` SLA columns | `ops_service`, `admin_service` | 7 |
| 8 | Onboarding | `OnboardingProgress` | `onboarding_service` | 3 |
| 9 | Frontend, seed, verification | — | — | — |

Each stage ends green and is committed before the next begins. The Phase 2 incident note is what an
uncommitted pile of work costs.

---

## Stage 0 — foundations

- **`core/ops.py`** as above.
- **`models/enums.py`** — `LocationStatus`, `CredentialKind`, `AttachmentKind`, `MedicationChangeKind`,
  `PillOrganiserStatus`, `CareCircleRole`, `ConsentKind`, `ConsentStatus`, `AuditAction`,
  `ErasureStatus`, `ChannelPreference`, `OnboardingStep`.
- **`models/audit.py` — `AuditEvent`, append-only in the engine.** Columns: `at`, `actor_user_id`,
  `actor_role`, `action`, `subject_type`, `subject_id`, `patient_id`, `detail`. Append-only is
  enforced by a SQLAlchemy `before_update` / `before_delete` mapper event that raises, **not** by
  nobody happening to write the code — and a test proves an `UPDATE` and a `DELETE` both raise.
- **`services/audit_service.py`** — `record(db, *, actor, action, subject_type, subject_id, ...)`.
  It never commits: it joins the caller's transaction, so an audited action that rolls back does not
  leave a log entry claiming it happened.
- **`services/storage.py`** — the only code in this repo that writes a file. Content-addressed
  (`uploads/<yyyy>/<mm>/<sha256>.<ext>`), so re-uploading the same photo does not duplicate it.
  `UPLOAD_ROOT` is a setting; `tests/conftest.py` points it at the temp directory it already builds,
  so the suite never writes into the source tree.
- **Schema additions:** `Patient.zone`, `Patient.home_lat`, `Patient.home_lng`; `Nurse.zone`.
  The zone comes out of `demo_data.ZONES`, which Phase 5 deliberately left as a table and Phase 5's
  own comment says to lift when something needs to *query* by it. The zone view is that something.
- **`requirements.txt`** — add `pillow==12.3.0`.
- **`.env.example`** — `UPLOAD_ROOT`.

## Stage 1 — nurse credential transparency, and real GPS

- **`models/nurse.py`** — `NurseCredential(nurse_id, kind, registration_number, issuing_body,
  issued_on, expires_on, verification_status, verified_by, verified_at, note)`. `Nurse` gains
  `zone`, `joined_on`, `languages`, `bio`, `photo_attachment_id`.
- **`services/nurse_service.py`** — profile assembly, credential CRUD, and the **family-facing
  projection**, which is a different object from the admin one: a family sees name, photo, credential
  kind, issuing body, verified-on date, languages, years of experience and the visits they have made
  to *this* patient. It does **not** see a registration number, a phone number, or any other
  patient's name. The two projections live side by side in one file so the difference is visible.
- **A credential is `verified` only with a `verified_by` and a `verified_at`.** A model-level check
  and a test; anything else is a badge that means nothing.
- **`visit_service.check_in`** takes `lat`, `lng`, `accuracy_m` and classifies:
  - `verified` — distance ≤ `GEOFENCE_RADIUS_M` **and** accuracy ≤ the ceiling.
  - `out_of_range` — distance > radius, with a good fix.
  - `unavailable` — no fix, no recorded home coordinates for the patient, or a fix whose own accuracy
    is worse than the fence. **A ±500 m fix cannot verify a 150 m circle, and reporting it as
    verified would be the platform lying about the one thing this feature exists to prove.**
  - Stores `location_status`, `location_distance_m`, `location_accuracy_m` and keeps `location_source`
    for the *provenance* of the fix (`browser` / `none`). `demo/unverified` is gone.
  - `out_of_range` opens a `FollowUpTask` for the admin. It does not block the check-in.
- **Touches:** `seed/population.py`, `tests/test_seed.py`, `tests/test_visits.py`, every visit fixture.

## Stage 2 — medication depth

- **`models/attachment.py` — `Attachment`** (`kind`, `path`, `sha256`, `content_type`, `bytes`,
  `uploaded_by`, `patient_id`, `created_at`). One table for every uploaded file, so the authenticated
  fetch route and the retention sweep are written once.
- **`POST /visits/{id}/medication-logs/{log_id}/photo`** — multipart. Validates by **decoding the
  bytes with Pillow, not by trusting the declared content type**, re-encodes to strip EXIF (a dose
  photo taken in the patient's living room carries the patient's home GPS), caps at the configured
  size, and writes through `storage`.
- **`GET /attachments/{id}`** — streams the bytes after the same `authorize_patient` check as
  everything else. **Nothing under `uploads/` is ever mounted as a static route**, and a test asserts
  the app exposes no `StaticFiles` mount at all.
- **`PillOrganiserFill`** — the ₹199 add-on finally gets a buyer. A fill records the compartments
  filled, by whom, on which visit, and the next due date; `medication_service.record_fill` resolves
  payment the way `lab_service.order` does — entitlement first, then the recorded add-on price
  through `billing_service.charge_addon`.
- **`MedicationChange`** — append-only history of every edit to a medication: started, dose changed,
  time changed, stopped. Written by `medication_service`, never by a router. A family looking at
  "why is she on half the dose now" gets a dated answer instead of a current-state row.

## Stage 3 — Care Circle

- **`CareCircleMember(patient_id, user_id NULL, name, relationship, phone, email, role, is_primary,
  receives_alerts, receives_reports, created_at)`**, unique on `(patient_id, email)`.
- The patient's existing `family_user_id` is **kept authoritative** and seeded in as the primary
  member, exactly as Phase 11's brief requires for its own migration.
- `receives_alerts` is honoured by Stage 5's routing — a circle member with no login still gets the
  SMS. That is the whole point of the feature for an NRI family whose uncle in Bangalore is the
  person who can actually drive over.
- Family and admin manage the circle; a nurse **reads** it (they need the emergency contact) and
  cannot edit it.

## Stage 4 — consent, the audit log, privacy and data

- **`Consent(user_id, patient_id NULL, kind, version, status, decided_at, decided_by, source)`** —
  granted and withdrawn are both rows. Nothing is ever updated in place, so the history is the record.
- **`GET /privacy/me`** — what is held, what each consent currently says, and the audit trail of who
  looked at this patient's record.
- **`GET /privacy/me/export`** — a JSON export assembled from a **registry**. Every service that owns
  user- or patient-scoped rows registers an exporter and an eraser once; `privacy_service` walks the
  registry. Phase 7's assistant messages, Phase 8's leads and Phase 9's labs, screenings, device
  readings and care interactions are all customers of it on day one, and Phase 11 adding a table is a
  registration rather than a rewrite. **A test asserts every patient-scoped model is registered**, so
  a future table cannot silently escape the export.
- **`POST /privacy/me/erasure`** (family requests) and **`POST /erasure-requests/{id}/execute`**
  (admin executes). The page states plainly **what is destroyed and what is retained and why** —
  issued invoices are financial records and survive with the patient's name replaced; the audit log
  survives and gains an entry recording the erasure itself. Writing "we delete everything" and then
  keeping the invoices would be exactly the unevidenced promise this phase exists to stop.
- Every read of a patient record by someone who is not that patient's family is audited.

## Stage 5 — notification routing, preferences, quiet hours

- **`NotificationPreference(user_id, channel, enabled, quiet_hours_enabled, quiet_start, quiet_end)`**.
- **`notification_service.dispatch(db, *, recipients, type_, severity, subject, body, ...)`** becomes
  the single outbound path. It writes the in-app record **always** — quiet hours govern outbound
  channels, never whether the family can see it when they open the app — then resolves channels:
  1. Critical → the two highest-preference channels that **have an address**. Push has none in this
     build, so a rule that returns SMS + push returns one channel wearing two names.
  2. Quiet hours suppress non-critical outbound and record the suppression as a `DeliveryLog` row
     with status and reason. A suppressed message is a recorded decision, not a gap.
  3. Unreachable channels are recorded as an attempt that could not be made.
- Existing callers (`notify_alert_recipients`, password reset, escalations) route through it. Phase
  9's `escalation_service` already writes its own steps — it keeps doing that and gains preferences,
  it does not get a second delivery path.

## Stage 6 — nurse operations

- **`GET /nurse/my-day`** — the day as a worklist: unfinished from yesterday first, then today in
  time order, each with travel zone, the patient's flags, and what is due.
- **`GET /visits/{id}/brief`** — the next-visit brief: last visit's readings, open alerts, medications
  due, the safety score band, the last note. Assembled server-side from what Phases 5–9 already store.
- **Hub check-in** — `POST /nurse/hub-checkin`, the start-of-shift equivalent of a visit check-in,
  classified by the same geofence code against the zone hub.
- **Roster** — the nurse's own week.
- **Offline-tolerant capture** — a `client_token` on vitals and medication logs makes submission
  idempotent, so a queued reading replayed after signal returns cannot double-record. The frontend
  queues in `localStorage` and drains on reconnect.

## Stage 7 — admin operations

- **Visit board** — replaces `/visits`' newest-250 with a **windowed, paginated** query
  (`from`/`to`/`status`/`nurse_id`/`zone`, page + page_size), which is the deferral STATE.md records
  against Phase 10 by name.
- **Nurse management** — roster, credentials and their verification, zone, workload.
- **Alert queue with SLA** — `Alert` gains `sla_minutes`, `sla_due_at`, `sla_breached_at`, stamped
  when observed, exactly like `EscalationEvent`. Sorted the way an operator works it: breached first,
  then soonest deadline.
- **Outcome metrics** — computed from stored rows: alerts raised and resolved, median time to
  resolve, visits completed vs scheduled, adherence, escalations, SLA attainment. **No stored
  counters** — a metric that can drift from the rows it describes is worse than no metric.
- **Zone view** — subscribers, nurses, visits and alerts per zone against the **recorded 30–45
  break-even band**. It shows *where a zone sits against the band* and invents no margin, because the
  unit economics behind that band were never supplied.

## Stage 8 — onboarding

- **`OnboardingProgress(user_id, step, completed_at)`** — one row per completed step, so the record is
  what happened rather than a counter.
- Steps: confirm the patient, set thresholds, build the care circle, choose notification channels,
  grant consent. Each maps to something that already exists, so completing a step is a real action
  and not a tick.
- A checklist on the family dashboard until it is done, then it disappears.

## Stage 9 — frontend, seed, verification

**New family screens:** `FamilyNurseProfile`, `FamilyCareCircle`, `FamilyPrivacy`, `FamilyOnboarding`,
plus notification preferences inside `MyPlan`'s account area and the medication history and organiser
on `FamilyMedications`.
**New nurse screens:** `NurseMyDay`, `NurseRoster`, `NurseVisitBrief` (inside the visit detail), photo
capture on the medication rows, and the offline queue indicator.
**New admin screens:** `AdminVisitBoard` (replacing `AdminVisits`' table), `AdminNurseDetail`,
`AdminAlertQueue` (SLA columns on `AdminAlerts`), `AdminOutcomes`, `AdminZones`, `AdminPrivacy`
(erasure requests), `AdminAudit`.

**Seed:** credentials for all 14 nurses with a spread of verification states; home coordinates and
zones for all 28 patients; check-ins classified across all three states including at least one
`out_of_range` and one `unavailable` so the demo shows the honest case; a care circle for Lakshmi
including one member with no login; consents granted; notification preferences with one family on
quiet hours; a pill-organiser fill; three medication changes on Lakshmi; one erasure request in
`requested` state for the admin to execute live; an audit trail with real entries.

**Verification:** the full suite, `tsc`, `npm run build`, Vitest, a seed run, and a browser pass at
375 / 768 / 1024 / 1440 on every new screen in both auth states.

---

## Phase 10 acceptance

```bash
cd backend  && .venv/bin/python -m pytest              # green, count only grows from 623
cd backend  && .venv/bin/python -m app.seed            # clean
cd backend  && .venv/bin/python -m app.seed --small    # clean
cd frontend && npx tsc -p tsconfig.json --noEmit       # zero errors
cd frontend && npm run build && npx vitest run         # green, count only grows from 121
grep -rn "demo/unverified" backend/app frontend/src    # → 0 hits
grep -rn "StaticFiles" backend/app                     # → 0 hits
```

Plus, in the browser: a family opens their nurse's profile and sees a verified credential; a nurse
checks in and the visit shows a measured distance; an admin works the alert queue by SLA and executes
an erasure request; and the family's Privacy page downloads an export that contains their own data
and nobody else's.

## Do not break

- Patient 1 is Lakshmi, nurse 1 is Anitha, **Anitha holds exactly one open visit today**, and
  **Lakshmi carries no open alert** and a clean clinical record.
- `tests/conftest.py` seeds `SMALL`, which has **no clinical layer**. Keep it that way — and the new
  trust layer follows the same rule wherever it can.
- The autouse `clean_process_state` fixture resets every process-global. **Register any new one.**
- `core/pricing.py` and `core/clinical.py` are **read, never written**.
- `/public/plans` and authenticated `/plans` stay byte-identical.
- Nothing outside `alert_service` constructs an `Alert`. Nothing outside `storage` writes a file.
  Nothing outside `audit_service` writes an `AuditEvent`.

---

# As executed

**Ten commits, 623 → 804 backend tests, 121 → 133 Vitest.** The nine planned stages
landed as ten commits (the plan doc got its own), in the planned order, with no stage abandoned.

## Where the plan held

The three decisions taken before any code were all still the right ones at the end:

- **`core/ops.py` rather than more `core/clinical.py`.** It ended at ~300 lines and is read by
  eleven services. Keeping the operator's file separate from the clinician's is the difference
  between two short reconciliation conversations and one long one. A test pins that it imports
  nothing from the application and that it *points at* `clinical.SLA_DURATIONS_MINUTES` rather than
  copying it.
- **One `care_circle_members` table with a nullable `user_id`.** Phase 11's `PatientFamilyMember`
  is this table. Nothing had to be un-built.
- **Family requests, admin executes.** This turned out to matter more than expected once the
  registry existed: erasure walks twenty datasets and destroys files on disk. It is not a button a
  shared account should have.

## Where the plan was wrong, or too thin

- **The plan said "nine stages, committed as they land" and stage 4 was two stages.** Consent, the
  audit log, the export registry and the erasure flow are one *feature* and four *mechanisms*; the
  registry alone is 577 lines. It went in as one commit anyway, and it is the largest in the phase.
- **The plan did not anticipate `alert_service.backdate`.** It was written as "Alert gains the SLA
  columns", which is true and useless: the seed rewrites `created_at` on every historical alert, so
  without moving the deadline with it the entire ninety-day queue reads as freshly raised and never
  breached. This is the **third** time this phase family of bug has appeared — `business.paid_at`
  in Phase 4, safety-drop alerts in Phase 9 — so it now has a named function and an invariant test
  rather than a third open-coded fix.
- **`ops.ZONE_HUBS` was not in the plan at all.** Hub check-in needs a point to measure against, and
  the zone centres already existed in `seed/demo_data.py`. Rather than duplicate them, `ops.py`
  became the single source and the seed reads from it. That is the one-file rule applied to a
  constant the plan had not noticed was a constant.
- **`MedicationLogRow` already owned its `<li>`.** The plan said "photo capture on the nurse's
  medication rows" as if it were a sibling element. It is a `footer` slot on the existing row —
  nesting an `<li>` inside an `<li>` would have been invalid markup for no gain.
- **`EmailStr` needed a dependency.** `schemas/lead.py` had already met and solved this in Phase 8;
  the care circle reuses its shape check rather than adding `email-validator`.

## What the tests could not have caught

- **The privacy page told a family that they themselves had been looking at their mother's record.**
  Every audit entry was correct; the sentence above them was not. Their four consent decisions were
  rendered under "who has looked at this record", next to a caption promising their own visits were
  not logged. Found by reading the rendered page at 375px, not by any assertion, and it is the kind
  of bug that only exists in the gap between data and the words around it.

## What the tests *did* catch

- **`test_every_patient_scoped_model_is_accounted_for` earned its keep four stages after it was
  written.** Stage 8's `OnboardingProgress` carries a `patient_id` and was never registered, so a
  family's setup progress would have survived their own erasure. The test failed on the next run
  after that stage, named the class, and the fix was a five-line registration. This is exactly why
  it asserts against the mapper registry rather than a list somebody maintains.

## Bugs found and fixed during the phase

- Two `NurseCredential` states that would have produced a badge meaning nothing — a `verified` enum
  with no verifier, and an expired credential accepted for verification — are both refused, at the
  model and at the service.
- The medication `PATCH` route originally let a nurse change a prescription. A nurse records doses;
  changing the dose is not theirs to do.
- The first `plan_channels` returned SMS + push for a critical alert on an account with no phone,
  which is zero reachable channels reported as two. It now walks the preference order and keeps the
  ones with an address, recording the rest.

## Numbers

| | Before | After |
|---|---|---|
| Backend tests | 623 | **804** |
| Vitest | 121 | **133** |
| Model files | 27 | **34** |
| Service files | 30 | **40** |
| Router files | 22 | **27** |
| `<Route>` elements | 47 | **57** |

Seed adds: 28 nurse credentials, 87 medication changes, 18 organiser fills, 39 care circle members,
112 consent decisions, 18 notification preferences, 66 shift check-ins and one erasure request
waiting for an admin to carry out live.
