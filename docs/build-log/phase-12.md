# Phase 12 — The three intelligence layers

**Goal:** DoorDoctor stops only *reacting* to fixed cutoffs. It reads the documents families and
admins hand it, writes three different summaries for three different readers, proposes who should
visit whom and in what order, and tells admins who is likely to need attention next.

**Status (2026-11-11):** design approved 2026-11-05. **Stages 0, 1 and 2 are built.** Stage 0–1
is committed (`3ad8c97`); everything since is **uncommitted, at the founder's request**: the Stage 1
live-testing fixes, Stage 2 (facts + admin verification), document notifications, the Groq model
switch, a dialog typing fix and a Windows launcher (see "Stage 2: how it went" at the end).
**Next: Stage 3**, planned at the end ("Stage 3 plan"): the nurse brief, the admin summary, and
Ask DoorDoctor reading verified document facts. Stages go one at a time, each on the founder's
go-ahead.

**Order:** numbered 12 so `phase-11.md` stays as written, but **built before Phase 11**. Everything
here is additive, so Phase 11's Alembic stage adopts these tables in its first migration, and its
`authorize_patient_write` replaces `authorize_patient` on the upload routes when it lands.

---

## The one idea this phase is built around

> **The intelligence layers sit beside the platform, never inside it.**

Every layer is a new package that *reads* the existing models and services and *writes only to its
own tables* — until a human approves something. The existing code does not import the new package,
with two named exceptions (listed below), and a test enforces that. Three consequences:

1. **Turning a layer off is a config flag**, and the platform behaves exactly as it does today.
2. **Every layer has a deterministic fallback.** No GPU, no API key, no network, no trained model:
   the demo still runs, and the test suite still runs on a laptop in the same time it does now.
3. **Nothing an AI component produces reaches a family, a visit or a nurse's day without an admin
   approving it**, with one deliberate exception: the family summary, which is already gated by
   Phase 6's banned-vocabulary check and keeps that gate.

| Layer | What it produces | Who sees it | What a human must approve |
|---|---|---|---|
| **1. Documents & summaries** | Text + structured facts from uploads; nurse brief, admin summary, family summary in their language | Nurse, admin, family | Every extracted fact, before it counts as part of the record |
| **2. Caseloads & routes** | Proposed home-nurse caseloads; proposed daily routes | Admin | The whole proposal, before any assignment changes |
| **3. Deterioration risk** | 7-day risk probability, tier, and the factors behind it | Admin (tier only in the nurse brief) | Nothing is applied — it ranks; admins decide |

```
                ┌─────────────────────── Layer 1 ───────────────────────┐
 upload ──► text layer / OCR ──► fact extraction ──► ADMIN VERIFIES ──► summaries
                                                          │              (nurse / admin / family)
                                                          ▼
                ┌─────── Layer 3 ───────┐          verified lab facts
 vitals, doses, visits, alerts ──────────► features ──► risk model ──► tier + factors
                                                                          │
                ┌─────── Layer 2 ───────┐                                 ▼
 homes, nurses, visits, hubs ──► caseloads / routes (high tier first) ──► ADMIN APPROVES
```

---

## Non-breaking rules (each one is checked, not promised)

| Rule | How it is held |
|---|---|
| **New tables only. No column added to, or changed on, an existing table.** | `create_all()` creates missing tables but never alters existing ones, so a new column would break every existing local `doordoc.db` until a reseed. Alembic is Phase 11 Stage 6 and not built yet. New tables are safe under both |
| **Existing modules don't import `app.intelligence`** — except `scheduler.py` and `services/privacy_service.py` (plus the new Phase 12 routers). `main.py` registers the routers but imports the router modules, not the package | `tests/test_intelligence_boundary.py` walks every module under `app/` with `ast` and fails on any other import |
| **No existing function signature or response shape changes** | New behaviour gets new endpoints. Existing endpoints, including `/visits/{id}/brief` and the family summary, are untouched |
| **The existing 804 backend + 133 frontend tests stay green at every commit** | Same rule as every phase. New tests are added on top |
| **The seed is not changed** | Training data for Layer 3 comes from a *separate* generator that writes a *separate* database (see Layer 3). The seed counts the suite asserts on (34 excursions, Anitha's one open visit, …) cannot move |
| **Heavy dependencies are imported lazily** | `ortools`, `lightgbm`, `pypdfium2` are imported inside the functions that use them, so app start-up and test collection time don't change, and a missing package degrades to the fallback rather than an `ImportError` at boot |
| **Tests never need a GPU, a key or the network** | A `FakeOcrEngine`, the existing "`GROQ_API_KEY` is empty in tests" rule, and straight-line distances. Real-engine tests are marked `@pytest.mark.live` and skipped by default |

---

## Package layout

Models stay in `app/models/` and routers in `app/routers/`, because `Base.metadata`, the privacy
coverage test and the router wiring all look there. All the *logic* lives in one new package:

```
backend/app/
├── core/
│   └── intelligence.py              NEW  every constant for all three layers (no numbers in services,
│                                         same rule as core/clinical.py and core/ops.py)
├── intelligence/                    NEW  the package
│   ├── __init__.py
│   ├── documents/                   Layer 1a — ingestion
│   │   ├── intake.py                validate + store an upload, create the Document row
│   │   ├── pdf_text.py              pypdf text layer, per page
│   │   ├── render.py                pypdfium2: page → image for OCR
│   │   ├── ocr_engine.py            OcrEngine protocol; ChandraEngine; FakeOcrEngine; NullEngine
│   │   ├── extraction.py            text → structured facts (LLM, JSON schema, verbatim-number check)
│   │   ├── verification.py          admin confirm / edit / reject; document → verified
│   │   └── worker.py                the queue: picks `uploaded` documents and runs the pipeline
│   ├── summaries/                   Layer 1b — the three readers
│   │   ├── facts.py                 gathers numbered facts with provenance (visits, vitals, doses,
│   │   │                            alerts, nurse notes, verified document facts)
│   │   ├── grounding.py             validates an LLM answer: every sentence cites facts, every
│   │   │                            number appears in a cited fact
│   │   ├── nurse_brief.py           pre-visit brief (clinical wording)
│   │   ├── admin_summary.py         full clinical summary, unverified items flagged
│   │   └── family_language.py       wraps the EXISTING family summary in hi / kn / ta, with gates
│   ├── routing/                     Layer 2
│   │   ├── distance.py              haversine × detour factor; OSRM table API when configured
│   │   ├── workload.py              visits/month per patient → minutes of work
│   │   ├── caseload.py              capacitated k-means on OR-Tools min-cost flow + continuity cost
│   │   ├── baselines.py             current, plain k-means, DBSCAN — for the evaluation only
│   │   ├── routes.py                OR-Tools VRP with time windows, per zone per day
│   │   └── proposals.py             create / approve / reject; staleness check
│   └── risk/                        Layer 3
│       ├── features.py              ONE feature function, used by training and by scoring
│       ├── scorer.py                loads the model; falls back to the rule-based scorer
│       ├── rules.py                 transparent fallback scorer (weights in core/intelligence.py)
│       ├── explain.py               per-patient factor contributions (LightGBM pred_contrib)
│       ├── tiers.py                 capacity-based low / medium / high
│       ├── synth.py                 synthetic longitudinal patients → separate SQLite file
│       ├── train.py                 `python -m app.intelligence.risk.train`
│       └── artifacts/               model-v1.txt (LightGBM) + model-card.json, committed
├── models/
│   ├── document.py                  NEW  Document, DocumentPage, ExtractedFact
│   ├── routing.py                   NEW  RoutingProposal, ProposedAssignment, RouteStop, HomeNurseAssignment
│   ├── risk.py                      NEW  RiskScore
│   └── language.py                  NEW  SummaryLanguagePreference
└── routers/
    ├── documents.py                 NEW
    ├── intelligence_summaries.py    NEW
    ├── routing.py                   NEW
    └── risk.py                      NEW
```

Why a package rather than more files in `services/`: `services/` already holds 44 modules, and the
boundary test needs a single prefix to check. `services/summary_service.py` and
`services/llm_client.py` stay exactly where they are; the new package *calls* them.

---

## Changes to existing files — the complete list

| File | Change | Risk |
|---|---|---|
| `app/main.py` | `include_router` × 4 | None — additive |
| `app/models/__init__.py` | Import + export the new models | None — additive |
| `app/models/enums.py` | New enums (`DocumentStatus`, `DocumentType`, `FactKind`, `FactStatus`, `ProposalKind`, `ProposalStatus`, `RiskTier`). **`AttachmentKind` gains `DOCUMENT_PDF` and `DOCUMENT_IMAGE`**. New `AuditAction` values: `DOCUMENT_UPLOADED`, `DOCUMENT_VERIFIED`, `DOCUMENT_REJECTED`, `PROPOSAL_APPROVED`, `PROPOSAL_REJECTED` | Low. SQLite stores enums as strings with no CHECK constraint (SQLAlchemy 2 default), so existing rows and DBs are unaffected. Under Postgres (Phase 11) this is one `ALTER TYPE` in the migration — noted for that phase |
| `app/config.py` | New settings, all with safe defaults (table below) | None |
| `app/scheduler.py` | Two jobs: document worker (every 30 s) and nightly risk recompute, both behind `INTELLIGENCE_WORKER_ENABLED` | Low — the scheduler is already disabled in tests |
| `app/services/storage.py` | New `store_document(data, content_type)` beside `store_image()`. **`store_image()` is not touched** | Low |
| `app/services/privacy_service.py` | `REGISTRY` gains `documents`, `routing`, `risk`, `language` DataSets (export + erase) | Low, and *required*: the existing registry-coverage test fails if a patient-scoped model is missing — that test is what guarantees the new tables are erasable |
| `app/core/ops.py` | `CONSENT_KINDS` gains `document_processing` (optional): "Documents you upload may be read by software to pull out results and medicines." Required only when the OCR engine is external | Low. If a test counts consent kinds it gets updated in the same commit, and that's recorded |
| `backend/requirements.txt` | `pypdf`, `pypdfium2`, `ortools`, `scikit-learn`, `lightgbm` | Medium — install size. All have Windows + Linux wheels for Python 3.11/3.12 |
| `docker-compose.yml` | Optional `chandra` (vLLM, GPU) and `osrm` services under a `profiles: ["ai"]` key. `docker compose up` without the profile behaves exactly as now | None |
| `frontend/src/App.tsx` + sidebar nav config | New routes and nav items | Low |
| `frontend/src/pages/nurse/<visit brief page>` | One new card that fetches `/visits/{id}/ai-brief` **separately**; if it fails the card hides and the existing brief is unchanged | Low |
| `frontend/src/pages/family/FamilyDashboard.tsx` | Language picker on the summary card; calls the new translated-summary endpoint, falls back to the current one | Low |
| `README.md`, `DESIGN.md`, `docs/build-log/STATE.md` | Documentation | None |

**Deliberately *not* changed:** `seed/*`, `services/summary_service.py`, `services/llm_client.py`,
`services/nurse_ops_service.py`, `services/safety_score.py`, `services/lab_service.py`,
`routers/attachments.py`, every existing model's columns.

### New settings (`app/config.py`)

| Env var | Default | Meaning |
|---|---|---|
| `DOCUMENTS_ENABLED` | `true` | Upload + extraction endpoints exist |
| `OCR_ENGINE` | `none` | `none` → scanned pages become "needs manual entry"; `chandra_local` → self-hosted vLLM; `chandra_api` → Datalab hosted API |
| `CHANDRA_BASE_URL` / `CHANDRA_API_KEY` / `CHANDRA_MODEL` | empty | Engine endpoint |
| `OCR_TIMEOUT_S` | `120` (laptop `.env`: `300`) | Per page. On the laptop GPU a page takes 15–20 s; 300 s is headroom for long handwritten pages |
| `ROUTING_ENABLED` | `true` | Layer 2 endpoints |
| `OSRM_BASE_URL` | empty | Empty → straight-line × detour factor |
| `RISK_ENABLED` | `true` | Layer 3 endpoints + nightly job |
| `RISK_MODEL_PATH` | `app/intelligence/risk/artifacts/model-v1.txt` | Missing file → rule-based scorer |
| `INTELLIGENCE_WORKER_ENABLED` | `true` (`false` in tests) | Background jobs |

---

## Layer 1 — Documents and summaries

### 1a. Ingestion pipeline

```
POST /patients/{id}/documents  (family or admin)
POST /visits/{id}/documents    (nurse — strict rule below)
  └─ intake.py        magic bytes (PDF / JPEG / PNG / WEBP), ≤ 15 MB, ≤ 30 pages,
                      encrypted PDF → 400, store original bytes, Document(status=uploaded) → 202
worker.py (scheduler, every 30 s, one document at a time)
  ├─ per page:
  │    pdf_text.py    text layer; if ≥ 50 chars → method=text_layer   (exact, instant, free)
  │    else render.py → 200 dpi image → ocr_engine.extract()          (method=ocr)
  │    engine None/failed → method=none, page flagged "needs manual entry"
  ├─ extraction.py    LLM (existing llm_client) → JSON → Pydantic schema
  │                   reject any fact whose number is not verbatim in the page text
  │                   no LLM available → document goes to the admin queue with text only
  └─ status → extracted | needs_manual | failed
```

**Who may upload.** Family and admin, through `authorize_patient` (unchanged). **Nurses only under
all of these conditions**, checked by the existing `authorize_nurse_visit` plus three checks of its
own:

1. the visit is assigned to this nurse;
2. the visit is **in progress**: checked in, not yet checked out. No uploads from the car
   afterwards, and none for a patient they merely visited last month;
3. the check-in's location status is not `out_of_range` (Phase 10's geofence). `unavailable` is
   allowed, because a phone without a GPS fix shouldn't block a prescription photo;
4. the document is stored with `visit_id`, so every nurse upload traces to one visit.

Nurses can't delete documents and can't verify them. They see verified documents for patients with
a visit assigned to them, plus their own uploads. Every upload is audited.

**OCR engine interface** — the only file that knows Chandra exists, same pattern as `llm_client`:

```python
class OcrEngine(Protocol):
    name: str
    def extract(self, image: bytes, *, content_type: str) -> OcrResult | None: ...  # never raises

@dataclass(frozen=True)
class OcrResult:
    text: str              # as built: Chandra returns layout HTML (<div data-label=…>, <table>)
    engine: str            # e.g. "chandra-ocr-2"
    elapsed_ms: int
```

The timeout is the engine's own setting (`OCR_TIMEOUT_S`), not a per-call argument.

`ChandraEngine` talks to any OpenAI-compatible vision endpoint with `httpx` (already a dependency,
so no new client library). Nothing about the page or the output is logged, the same rule as
`llm_client`.

**Where Chandra runs now: the founder's laptop.** RTX 4050 Laptop GPU with **6 GB VRAM**, 16 GB RAM.
The full-precision 4B model (~8 GB of weights) won't fit, and vLLM doesn't run natively on Windows.
So:

- **Runtime, as built: LM Studio** (its llama.cpp **CUDA** runtime), serving the OpenAI-compatible
  `/v1/chat/completions` the engine already speaks, at `http://127.0.0.1:1234/v1`. `llama.cpp`'s own
  `llama-server` (port 8080) works identically. Either needs a recent build, because older ones
  reject the `qwen3vl` architecture.
- **Weights, as built: `prithivMLmods/chandra-ocr-2-GGUF`**, `Q4_K_M` (3.07 GB) plus `mmproj-f16`
  (0.68 GB, the vision projector): about 3.6 GB loaded, 8192 context. Quantization costs some accuracy, so Stage 1
  includes a small check: ~20 real-looking pages (printed lab report, typed prescription,
  handwritten prescription, discharge summary), compared by hand against the original.
- **Licence:** a quantization inherits the original weights' modified OpenRAIL-M terms.
- `OCR_ENGINE=chandra_local`, `CHANDRA_BASE_URL=http://127.0.0.1:1234/v1`,
  `CHANDRA_MODEL=chandra-ocr-2`. With the laptop server off, pages fall back to "needs manual
  entry" and nothing else breaks.
- Moving to a GPU server later is a change to `CHANDRA_BASE_URL`, not to code.

**Why the queue is a DB status column, not `BackgroundTasks`:** a Chandra page can take tens of
seconds. A status-driven worker survives a restart, can be retried with
`POST /documents/{id}/reprocess`, and is visible in the admin queue. It's single-process, which
matches Phase 11's current single-replica assumption; a crash mid-document leaves it in
`extracting`, and the worker treats an `extracting` row older than 10 minutes as `uploaded` again.

### 1b. Admin verification

- `GET /admin/documents/queue`: documents in `extracted` / `needs_manual`, oldest first.
- Side-by-side screen: page image (served by the existing `/attachments/{id}` route) next to the
  proposed facts. Per fact: **Confirm / Edit / Reject**. The admin can also add a fact by hand (that
  is what "needs manual entry" means for a handwritten page Chandra couldn't read).
- `POST /documents/{id}/verify` only succeeds once every fact is decided → `verified`, audited.
- **Family uploads show "Waiting for the care team to check"** until verified.

**Decision: verified document facts do not raise alerts in this phase.** A flagged lab value
appears at the top of the nurse brief and the admin summary. Alerts stay the threshold engine's and
`lab_service`'s job. Promoting external reports into `LabResult` would need a `LabOrder`, which
carries billing, so that's out of scope.

### 1c. Three summaries, one grounding rule

`facts.py` builds one numbered list per patient and window. Each fact carries its source:

```json
{"id": "F7", "kind": "document_fact", "text": "HbA1c 8.1 % (ref 4.0–5.6)", "date": "2026-11-02",
 "source": {"document_id": 41, "page": 1, "verified": true}}
```

The LLM is asked to return `[{"text": "...", "cites": ["F7", "F3"]}, ...]`. `grounding.py` accepts
the answer only if:

1. it parses as that schema;
2. every sentence cites at least one existing fact ID;
3. every number in a sentence appears in one of the facts it cites;
4. (family only) it passes the existing `summary_service.contains_clinical_language()`.

Any failure → the **deterministic version**, which is the facts themselves, grouped and templated.
This is also the faithfulness metric for the report: the share of LLM sentences that pass 2–3, and
a hand audit of a sample.

Nurse notes are inside the fact list as quoted data. The system prompt says text inside facts is
never an instruction, and rule 2 means an injected instruction can't produce an uncited sentence
anyway.

| Reader | Endpoint | Inputs | Wording | Fallback |
|---|---|---|---|---|
| **Nurse** | `GET /visits/{id}/ai-brief` (assigned nurse, admin) | Changes since last visit, open alerts, med changes, verified document facts, last notes, risk tier | Clinical, ≤ 8 bullets, action-first | Deterministic bullets |
| **Admin** | `GET /patients/{id}/clinical-summary?window=30d` | Everything; **unverified facts included and flagged** | Clinical, every line cited | Deterministic grouped list |
| **Family** | `GET /patients/{id}/summary/translated?language=hi&window=7d` | The **existing** Phase 6 summary output | Plain, chosen language | The existing English summary + "not available in Hindi yet" |

**Languages: two separate questions.**

- **Reading documents:** every language Chandra reads. There is no list to maintain, because an
  admin verifies every fact anyway.
- **Writing the family summary:** this is done by the *summary* model (Groq, `llama-3.3-70b`), not
  Chandra. Llama 3.3 officially supports only eight languages (English, Hindi, German, French,
  Italian, Portuguese, Spanish, Thai). It writes Kannada, Tamil and others, but less reliably. So
  the language list is configuration (`SUMMARY_LANGUAGES` in `core/intelligence.py`), and the gates
  below decide per summary whether the translation is shown.

The existing summary is *translated*, not regenerated, so it can't gain facts. Gates on the
translation:

1. every number in the translation must match the English source (works in any language);
2. a back-translation to English must pass `contains_clinical_language()` (works in any language);
3. *optionally*, a per-language banned-word list, added when a native speaker reviews that
   language.

Gates 1 and 2 don't depend on the language, so any language the model can write can be enabled.
Gate 3 is extra protection for the most-used ones. Proposed initial list: `en`, `hi` (officially
supported), plus `kn`, `ta`, `te`, `ml`, `mr`, `bn`, `gu` marked *beta* in the picker. Any failed
gate falls back to English with a note.

The language choice is stored in the new `SummaryLanguagePreference(user_id, language)` table,
because adding a column to `users` breaks existing databases (see the rules above).

---

## Layer 2 — Caseloads and routes

### What exists and what is assumed

- Patients have `home_lat/home_lng` (nullable) and a `zone`. Nurses have a `zone`. Six zones, each
  with a hub in `core/ops.ZONE_HUBS`.
- **There is no "home nurse" today.** Continuity is derived: the nurse who completed the most of the
  patient's visits in the last 60 days. Once an admin approves a caseload, the new `HomeNurseAssignment`
  table records it explicitly.
- Workload per patient = the plan's `VISITS_PER_MONTH` × `VISIT_DURATION_MIN` (new constant, 45 min
  assumed) + travel. Caseloads are balanced on **minutes**, not head count. A 12-visit plan isn't
  the same load as a 4-visit plan.

### 2a. Caseload proposals (monthly, per zone)

Capacitated k-means, implemented on OR-Tools' min-cost flow (≈ 80 lines). That replaces a
`k-means-constrained` dependency whose wheels for newer Pythons are uncertain.

```
k = active verified nurses in the zone
init centroids = centroid of each nurse's current patients    (starts from today, not random)
repeat until assignments stop changing (≤ 20 iterations):
    assign patients to nurses by min-cost flow:
        cost(p, n) = distance(p, centroid_n) + CONTINUITY_PENALTY_KM × [n ≠ current nurse of p]
        capacity(n) = zone workload / k × (1 ± CASELOAD_TOLERANCE)       (tolerance 15%)
    recompute centroids
```

Patients with no coordinates are listed as "needs location" and left with their current nurse.
Clustering happens **within a zone**. Zones are business units with hubs and break-even targets.
If a patient sits closer to another zone's hub, the proposal says so as information and moves
nothing.

**Evaluation** (`baselines.py`): the same metrics for the current assignment, plain k-means, DBSCAN
and the capacitated version:

- total travel km per month
- workload spread (max − min minutes)
- share of patients who keep their nurse
- unassigned patients (DBSCAN noise)

That table is the report's Layer 2 result.

### 2b. Daily route proposals (per zone, per date)

OR-Tools vehicle routing with time windows:

- **vehicles** = nurses in the zone with a shift that day (existing roster)
- **depot** = the zone hub
- **stops** = that day's visits; window = `scheduled_at ± 30 min`; service time = visit duration
- **soft costs:** a penalty for not using the home nurse; a high-tier (Layer 3) visit can't be
  dropped and gets a narrower window
- a visit that can't fit is returned as **"unassignable"**, never silently dropped

**`scheduled_at` is never changed.** Families were told a time. A route only decides *which nurse*
and *in what order*.

### 2c. Approval

- `RoutingProposal` stores the inputs it was computed from (a hash of visit IDs, statuses and nurse
  assignments). `POST /admin/routing/proposals/{id}/approve` returns **409** if anything changed
  since, and the admin re-runs it.
- Approving a caseload → writes `HomeNurseAssignment` rows. Future scheduled visits are reassigned **only
  if the admin ticks "also move upcoming visits"**.
- Approving a route → sets `Visit.nurse_id` on that day's visits and stores order + ETA in
  `RouteStop`.
- Both are audited. Rejecting is one click with an optional note.

At today's seed size (6 zones, ~2 nurses each) the gains will be small. The report should say so,
and run the comparison on a scaled synthetic population too (generated by Layer 3's `synth.py`).

---

## Layer 3 — Deterioration risk

### How it differs from the Safety Score (which stays untouched)

| | Safety Score (Phase 10) | Risk layer |
|---|---|---|
| Question | How have the last 30 days gone? | Who is likely to need attention in the next 7 days? |
| Reader | Family | Admin; tier only in the nurse brief |
| Method | Fixed weighted rules | Trained model + fallback rules |

### Features (`features.py` — the single function for training and scoring)

- **Vital trends:** slope, standard deviation and last-vs-baseline for BP, glucose, SpO2, weight and
  heart rate, over 7 and 30 days
- **Readings out of range:** share in the last 7 and 30 days
- **Medicine-taking:** rate over 7 and 30 days, and the change between them
- **Visits:** missed or cancelled in the last 30 days, days since the last completed visit
- **Alerts:** count and days since the last alert, by severity
- **Other:** latest mood screen, latest Safety Score, flagged verified document facts (from
  Layer 1), age

One function for both training and scoring is the main defence against training/serving skew.

### Label, data and training

- **Label:** a HIGH or CRITICAL alert in the 7 days after the scoring date. The platform produces
  this label itself, so no clinician has to label synthetic cases, which removes the circularity
  flagged in the review.
- **`synth.py`** generates ~500 patients × 180 days into **`ml_synth.db`** (never the demo DB),
  using the **real models, the real `visit_service` and the real threshold engine**, so alerts arise
  exactly as they do in production. Each patient follows a latent trajectory:
  - stable
  - slow decline (BP or glucose creeping up over 2–4 weeks)
  - non-adherence spiral (doses missed, then readings drift)
  - acute event (sudden change)
  - recovery

  This is the part the current seed can't provide: precursors that come *before* the alerts.
- **`train.py`:**
  - split by patient (no patient in both train and test) and by time (train on earlier days, test
    on later ones)
  - logistic-regression baseline, then LightGBM
  - writes `model-v1.txt` and `model-card.json`: data description, metrics, feature list, date
- **Metrics:**
  - AUROC
  - calibration (Brier score + reliability table)
  - **precision@k** at admin capacity (if admins can act on 5 patients, how many of those 5 had an
    event)
  - all of the above compared with the Safety Score used as a predictor

### Scoring, tiers and explanations

- Nightly job (and `POST /admin/risk/recompute`) → one `RiskScore` row per active patient.
- **Tiers by capacity, not a fixed cutoff:** high = top 10% (at least one patient, at least p 0.2),
  medium = the next 20%, low = the rest. Constants in `core/intelligence.py`.
- **Explanations:** LightGBM's built-in `pred_contrib=True` gives SHAP values without the `shap`
  package and its heavy dependencies. The top 3 factors are rendered in plain words ("BP rising
  over 2 weeks", "4 doses missed this week").
- **Fallback:** no model file or no `lightgbm` → `rules.py`, a hand-weighted logistic over the same
  features, with `model_version = "rules-v1"` on every row so nobody mistakes it for the trained
  model.
- Families never see the risk layer.

**The honesty line for the report:** results on synthetic data show the method works and the
system is built correctly, not that it predicts real patients. Real validation needs real,
consented data, and is future work.

---

## New tables

| Table | Key columns | Patient-scoped (erasable) |
|---|---|---|
| `documents` | patient_id, visit_id (nurse uploads), attachment_id, uploaded_by, uploader_role, title, doc_type, document_date, status, page_count, error, verified_by, verified_at, created_at | ✅ |
| `document_pages` | document_id, page_no, method, text, char_count, engine, elapsed_ms | ✅ via document |
| `extracted_facts` | document_id, patient_id, page_no, kind, label, value_text, value_num, unit, ref_low, ref_high, observed_on, source_quote, status, reviewed_by, reviewed_at | ✅ |
| `summary_language_preferences` | user_id (unique), language | user-scoped |
| `home_nurse_assignments` | patient_id, nurse_id, effective_from, proposal_id, created_by | ✅ |
| `routing_proposals` | kind, zone, for_date, input_hash, params_json, metrics_json, status, created_by, decided_by, decided_at, note | no (operational) |
| `proposed_assignments` | proposal_id, patient_id, current_nurse_id, proposed_nurse_id | ✅ |
| `route_stops` | proposal_id, nurse_id, visit_id, sequence, eta, leg_km | ✅ via visit |
| `risk_scores` | patient_id, calculated_at, horizon_days, probability, tier, model_version, factors_json, features_json | ✅ |

---

## API surface (all new)

| Method & path | Role |
|---|---|
| `POST /patients/{id}/documents` | family (own patient), admin |
| `POST /visits/{id}/documents` | nurse: assigned, visit in progress, check-in not out of range |
| `GET /patients/{id}/documents` | family, admin, assigned nurse (verified only) |
| `GET /documents/{id}` | same as above; facts filtered by role and verification |
| `DELETE /documents/{id}` | admin; uploader while still unverified |
| `POST /documents/{id}/reprocess` | admin |
| `GET /admin/documents/queue` | admin |
| `PATCH /documents/{id}/facts/{fact_id}` · `POST /documents/{id}/facts` | admin |
| `POST /documents/{id}/verify` · `POST /documents/{id}/reject` | admin |
| `GET /visits/{id}/ai-brief` | assigned nurse, admin |
| `GET /patients/{id}/clinical-summary` | admin |
| `GET /patients/{id}/summary/translated` | family, admin |
| `GET · PUT /me/summary-language` | any user |
| `POST /admin/routing/caseload-proposals` · `POST /admin/routing/route-proposals` | admin |
| `GET /admin/routing/proposals` · `GET /admin/routing/proposals/{id}` | admin |
| `POST /admin/routing/proposals/{id}/approve` · `…/reject` | admin |
| `GET /admin/risk` · `GET /admin/risk/patients/{id}` · `POST /admin/risk/recompute` · `GET /admin/risk/model` | admin |

Every patient-scoped route goes through the existing `authorize_patient` (or `authorize_patient_write`
once Phase 11 Stage 1 lands). Unauthorized access returns 404, not 403, the same as today.

---

## Frontend (all new pages, existing pages get one additive card each)

| Where | New |
|---|---|
| Family | `FamilyDocuments.tsx`: upload, list with status chips, view; language picker on the dashboard summary card |
| Admin | `AdminDocuments.tsx` (verification queue, side-by-side), `AdminRouting.tsx` (proposal list, before/after metrics table, per-nurse assignment diff, approve/reject), `AdminRisk.tsx` (ranked list, tier, top factors, history sparkline); a "Clinical summary" panel on the patient page |
| Nurse | "Brief" card on the visit brief page |
| Shared | `src/api/{documents,routing,risk,summaries}.ts`, `src/types/intelligence.ts` |

No map library in this phase; routes show as an ordered table with leg distances. A Leaflet + OSM
map can come later as its own change.

---

## Build order — seven stages, one commit each, full suite green before each

| # | Stage | Ships | Depends on |
|---|---|---|---|
| 0 | Foundations | `core/intelligence.py`, package skeleton, settings, enums, boundary test, privacy registry entries, requirements | — |
| 1 | Ingestion | upload, PDF text layer, `OcrEngine` + `FakeOcrEngine` + `ChandraEngine`, worker, family documents page | 0 |
| 2 | Facts + verification | extraction, admin queue + side-by-side screen | 1 |
| 3 | Nurse brief + admin summary + the assistant reads documents | `facts.py`, `grounding.py`, two endpoints, two UI cards; verified facts in Ask DoorDoctor's context pack, two new intents (see "Stage 3 plan" at the end) | 2 |
| 4 | Risk layer | features, rules scorer, `synth.py`, `train.py`, committed model + card, admin risk page, tier in nurse brief | 0 (uses 2's facts if present) |
| 5 | Routing layer | distance, workload, caseload + baselines, VRP, proposals + approval, admin routing page | 0 (uses 4's tiers if present) |
| 6 | Family languages — **optional** | translation gates, language preference, dashboard picker | 3 |
| 7 | Docs + evaluation | README, DESIGN, STATE; the evaluation tables for all three layers in `docs/build-log/phase-12.md` | all |

Stages 4 and 5 don't depend on Layer 1 and can be built first if a deadline needs results from
them sooner.

**Stage 6 is optional** (decided 2026-11-11, for time). Stages 0–5 and 7 deliver all three AI layers
from the proposal; Stage 6 only adds family summaries in languages other than English. If it is
skipped, family summaries stay in English, exactly as v1 shows them today, and nothing else
changes. The language design in Layer 1c stays in this document so it can be picked up later.

---

## Decisions

| # | Question | Decision |
|---|---|---|
| 1 | Before or after Phase 11? | ✅ **Before.** Numbered 12, built first; additive, so Phase 11's first migration adopts these tables |
| 2 | Can nurses upload? | ✅ **Yes, under strict authorization:** assigned nurse, visit in progress, check-in not out of range, upload tied to the visit, no delete or verify (Layer 1a) |
| 3 | Where does Chandra run? | ✅ **The founder's laptop for now:** LM Studio (CUDA runtime) + `prithivMLmods/chandra-ocr-2-GGUF` Q4_K_M on the RTX 4050 (6 GB). A GPU server later is a URL change. Licence to be checked before any commercial use |
| 4 | Languages | ✅ **Documents: everything Chandra reads. Family summary: a configurable list,** `en` + `hi` fully supported, seven more Indian languages as *beta*, every translation gated (Layer 1c). **Stage 6, which builds this, is optional** (2026-11-11); without it family summaries stay in English |
| 5 | Should a verified abnormal document value raise an alert? | ✅ **Not in this phase:** shown at the top of the nurse brief and admin summary |
| 6 | **Risk tier sizes.** How many patients per week can the admin team actually follow up on? | ✅ **High = top 10%, medium = next 20%** (approved with the design). One constant in `core/intelligence.py` |

### Environment note

The machine has Python 3.14 and 3.12. **The backend venv (`backend/.venv`) uses Python 3.12.** `ortools`, `lightgbm` and `pypdfium2` all publish 3.12 wheels for Windows, while 3.14
wheel coverage is less certain, and the repo states 3.11+.

---

## Stage 0–1: how it went (2026-11-05)

Built as one unit, at the founder's request ("only stage 1"): Stage 1 can't exist without Stage
0's foundations, so Stage 0 was scoped to **what Layer 1 needs** rather than all three layers.
Routing, risk and language tables, settings and constants arrive with their own stages.

### What shipped

| Area | Files |
|---|---|
| Constants | `core/intelligence.py` (Layer 1a section only; imports nothing from the app) |
| Models | `models/document.py`: `Document`, `DocumentPage`. Verification columns (`verified_by`, `verified_at`) included now, so Stage 2 adds no column to a table that already exists |
| Pipeline | `intelligence/documents/`: `intake`, `access`, `pdf_text`, `render`, `ocr_engine`, `worker`, `service` |
| API | `routers/documents.py`: 7 routes (table above) |
| Worker | scheduler job every 30 s, plus `python -m app.intelligence.documents.worker --once` / `--loop` for running beside the laptop's Chandra server |
| Frontend | `FamilyDocuments`, `AdminDocuments` (pages + how each was read), a self-fetching `VisitDocumentsCard` on the nurse visit screen, nav items, `types/intelligence.ts`, `api/documents.ts` |
| Tests | backend `test_documents.py` (46) + `test_intelligence_boundary.py` (4); frontend `documents.test.tsx` (4) |

### Results

- **Backend: 856 passed, 3 failed. All 3 failures predate this work** and fail identically on a
  clean checkout of `9fa2848` on this machine:
  - `test_billing::test_invoice_renders_as_a_pdf` and `test_reports::test_the_pdf_is_a_real_document`:
    WeasyPrint can't find its GTK/Pango libraries on Windows (`OSError: cannot load library`);
  - `test_subscriptions::test_quota_usage_from_a_previous_period_is_kept_not_reset`:
    date-dependent, left for Phase 11's time stage.
- **Frontend:** `tsc` clean, `npm run build` clean, **141 vitest passing**.
- **Seed:** `python -m app.seed` runs clean and creates `documents` and `document_pages`.
- **Live smoke** (uvicorn + worker CLI, scratch DB): a two-page PDF, one text page and one blank
  page, uploaded as the family → `202` → worker → `needs_manual`, pages `[text_layer, none]`. The
  family view has no page text; the file streams as `application/pdf` through the existing
  attachment route.

### Deviations from the design, and why

| Design said | Built | Why |
|---|---|---|
| `CareAssignment` table for Layer 2 | renamed **`HomeNurseAssignment`** (`home_nurse_assignments`) | `CareAssignment` / `care_assignments` already exists (Phase 10 care managers). Caught before Stage 5, fixed in this doc |
| Optional consent kind `document_processing` in Stage 0 | **deferred** | Chandra runs on our own hardware (`chandra_local`); no document leaves our control. It returns when `OCR_ENGINE=chandra_api` is used |
| — | `ERASURE_DESTROYS` gains "Uploaded documents, and the text read from them" | The erasure promise shown to families must name what it now covers |
| — | `tests/conftest.py` sets `INTELLIGENCE_WORKER_ENABLED=false`, `OCR_ENGINE=none` | Same reason as the report scheduler: no thread per test client, no real engine |
| `scheduler.py` adds a job | `start()` now runs when *either* reports or the document worker is enabled | With both off it takes exactly the old "disabled by configuration" path, so test behaviour is unchanged |
| `app.main` on the boundary allowlist | not on it | It imports `routers.documents`, not `app.intelligence`; the test's allowlist must not carry stale entries |

### Known gaps, deliberately left

- **The existing `/attachments/{id}` route** lets any nurse with a visit for the patient fetch a
  document's *file* by id, including an unverified family upload, because that route uses
  `authorize_patient`. The documents API itself hides unverified family documents from nurses. A
  nurse on the patient's care team is authorized for that patient anyway; tightening the shared
  route would change Phase 10 behaviour, so it's recorded here instead.
- **PDFs are served `inline`**, like photos. A browser's PDF viewer runs any embedded scripts in its
  own sandbox; serving documents as downloads is a one-line header change if that's preferred.
- **The OCR prompt** (`core/intelligence.OCR_PROMPT`) is a plain transcription instruction. Live
  testing showed Chandra answers in its own trained layout-HTML format whatever the prompt asks
  for, and reads accurately in it, so the prompt was left as is.

### To run OCR on the laptop (LM Studio, as used)

1. LM Studio → Settings → Runtime: select the **CUDA** llama.cpp runtime, not CPU.
2. Download `prithivMLmods/chandra-ocr-2-GGUF` → `Q4_K_M`, with its `mmproj` file. The model must
   show LM Studio's vision badge.
3. Load with GPU offload at max and context 8192; Developer tab → **Start server** (port 1234).
4. `backend/.env`: `OCR_ENGINE=chandra_local`, `CHANDRA_BASE_URL=http://127.0.0.1:1234/v1`,
   `CHANDRA_MODEL=chandra-ocr-2` (must match the id at `/v1/models`).
5. Upload a scanned document; the scheduler picks it up within 30 s, or run
   `python -m app.intelligence.documents.worker --once`.

`llama-server -m <model>.gguf --mmproj <mmproj>.gguf --port 8080 -ngl 99 -c 8192` works the same,
with `CHANDRA_BASE_URL=http://127.0.0.1:8080/v1`.

---

## Stage 1 live testing (2026-11-07)

Run on the founder's laptop: backend and frontend locally, Chandra OCR 2 in LM Studio, uploads
made through the UI.

### Environment set up

- `backend/.env` and `frontend/.env` created (gitignored). Random per-machine `JWT_SECRET`, OCR
  pointed at LM Studio, `OCR_TIMEOUT_S=300`. `GROQ_API_KEY` is still empty, so every LLM path runs
  its deterministic fallback until a key is added.
- `backend/doordoc.db` seeded with the full demo population.
- `.env.example` and `backend/.env.example` document both LM Studio (1234) and llama-server (8080).

### What happened

| # | Test | Result |
|---|---|---|
| 1 | Synthetic printed lab report (PNG), first run | Read **perfectly** (every value, unit and range), but at ~9 tokens/s it overran the 120 s timeout. **Cause: LM Studio was on its CPU-only runtime** (log: "llama.cpp was compiled without support for GPU offload"). Fixed by switching to the CUDA runtime |
| 2 | Same report, on the GPU | **16.5 s** warm (≈ 43–55 tokens/s), 4 GB of GPU memory in use, output correct |
| 3 | Real **handwritten prescription** photo (720×1280 JPEG), family upload | First marked `needs_manual` although Chandra had read it. **Cause: LM Studio filed the whole transcription under `reasoning_content` and left `content` empty.** Fixed in `ocr_engine.py`; re-read in 19.7 s → `extracted` |
| 4 | Admin view of the page text | Showed raw layout HTML. Fixed with a readable view (below) |

### What Chandra read from the handwritten prescription

Hospital header, date, patient name and age, UHID, complaint, impression, BP 110/70, PR 60 bpm,
the advice lines, and a **Kannada** footer in Kannada script. Two misreads: **"DRS 2 sachets"**
(almost certainly *ORS*) and **"Emp:"** (*Imp:*, impression). This is exactly the failure Stage 2's
side-by-side verification exists to catch: plausible, fluent, and wrong.

### Fixes made during testing (uncommitted)

| Change | Files | Tests |
|---|---|---|
| Read `reasoning_content` (or `reasoning`) **only when `content` is empty**; `content` still wins when both are filled | `intelligence/documents/ocr_engine.py` | 2 new in `test_documents.py` |
| Readable OCR view: Chandra's HTML is **parsed with `DOMParser`, never injected**. Paragraphs, line breaks, lists, tables and emphasis become React elements; images become `[Image: alt]`; scripts, links and live images are dropped. A "Show raw OCR output" toggle for admins | new `components/documents/OcrText.tsx`, `pages/admin/AdminDocuments.tsx` | 4 new in `documents.test.tsx`, including a hostile page with `<script>`, `onerror` and a `javascript:` link |

### Test results after the fixes

- **Stage 1 backend** (`test_documents.py` + `test_intelligence_boundary.py`): **52 / 52**.
- **Suites Stage 1 touches** (privacy, ops foundations, location, medication depth): **87 / 87**.
- **Full backend: 859 / 861.** The two failures are the WeasyPrint PDF tests (GTK missing on
  Windows), which predate Phase 12. The date-dependent subscription test passed on this date.
- **Frontend:** `tsc` clean, build clean, **145 / 145** vitest (8 for documents).
- `test_screenings::test_the_score_feeds_the_safety_score_mood_component` failed once in one full
  run and passed on every re-run, alone and in the suite. Recorded as flaky, not investigated.

### Still open for Stage 1's quality check

The planned ~20-page hand comparison (printed lab reports, typed and handwritten prescriptions, a
discharge summary) has two pages so far. The rest can run alongside Stage 2, whose verification
screen is the natural place to compare text against the page.

---

## Stage 2: how it went (2026-11-11) — uncommitted

### What shipped

| Area | Files |
|---|---|
| Model | `ExtractedFact` (`extracted_facts`) in `models/document.py`; enums `FactKind`, `FactStatus` (proposed / confirmed / edited / rejected / added), `FactSource` (table / llm / manual); `AuditAction.DOCUMENT_VERIFIED`, `DOCUMENT_REJECTED` |
| Reading Chandra's HTML | `intelligence/documents/text.py`: stdlib `html.parser` → plain text (tables as `a \| b \| c` rows) and tables as cells. Never executes anything |
| Extraction | `intelligence/documents/extraction.py`: **(1) lab tables, no model**, by column headers (reference before result, so "Normal value" is a range); **(2) the LLM** for everything else, only with a key. An LLM fact is **dropped if any number it carries isn't on the page**; a paraphrased quote is blanked. Re-extraction keeps every decided fact and won't re-propose one an admin corrected or renamed |
| Decisions | `intelligence/documents/verification.py`: confirm / edit / reject / reopen per fact; add a manual fact; verify only when **no fact is still proposed**; reject with a reason (to the audit log); a decided document is closed. An edit keeps the original proposal in `original_json` |
| API | `GET /admin/documents/queue`, `PATCH /documents/{id}/facts/{fact_id}`, `POST /documents/{id}/facts`, `POST /documents/{id}/verify`, `POST /documents/{id}/reject`, `POST /documents/{id}/extract` |
| Visibility | Admins see every fact with its source and quote. Family and nurses see only confirmed / edited / added facts, and only once the document is verified |
| Frontend | `AdminDocumentReview.tsx` (page image and read text on the left; facts with Confirm / Correct / Reject and "Originally read as" on the right; Add a fact; Verify with a pending count; Reject with a reason); `FactReview.tsx`; the admin list opens on **To review** with "N to decide" per document; the family list shows "N details added to the record" |
| Privacy | `extracted_facts` erased with the document; the export lists only facts in the record |

### Follow-ups done in the same working session

| Change | Why |
|---|---|
| **Groq model → `openai/gpt-oss-120b`** (`backend/.env`, default in `config.py`, `.env.example`) | `llama-3.3-70b-versatile` is retired on Groq (HTTP 404). Every LLM path, v1's summary rewrite and assistant included, had been silently on its fallback. Tested on the handwritten prescription: all 5 facts in 3.0 s, all grounded. `qwen/qwen3.8-27b` also worked, with raw labels ("Emp", "PR") |
| **Document notifications** (`intelligence/documents/notify.py`, `NotificationType.DOCUMENT`) | In-app only, the same table as the bell. Recipients follow `access.py`; the actor is never told about their own action; messages name the document and the patient's first name, never its content. Routes `GET /documents/notifications/unseen` and `POST /documents/notifications/seen`; a count on the family and admin **Documents** menu item (`NavBadge`, one shared poller in `useDocumentUpdates`), cleared on opening the page. Nurses have no Documents page and see them in the bell |
| **Dialog typing fix** (`hooks/useFocusTrap.ts`) | The focus trap re-ran on every render for any caller passing an inline `onClose`, pulling focus to the close button after each keystroke. First seen in the reject dialog, latent in every dialog with a text field. `onClose` now lives in a ref |
| **`start-doordoctor.bat`** | One-click start: LM Studio server, first-run seed, backend and frontend in their own windows, browser once both answer |

### Results

- **Backend: 913 passed, 2 failed.** The two are the WeasyPrint PDF tests (GTK missing on Windows),
  unchanged since before Phase 12. New: `test_document_facts.py` (45), `test_document_notifications.py` (9).
- **Frontend:** `tsc` clean, build clean, **153 / 153** vitest, including a focus-trap regression
  test that fails on the old hook. jsdom has no layout, so the test has to make elements "visible"
  to reproduce the bug.
- **Live:** with the Groq key, the handwritten prescription yields 5 grounded proposals; "DRS 2
  sachets" comes through as read, for the admin to correct to ORS.

### Known gaps after Stage 2

- **Verified facts are barely displayed yet.** Admins see them on the review page; the family sees
  only a count; no nurse screen shows them. Stage 3 is where they get used.
- **Ask DoorDoctor doesn't know about documents.** Its context pack predates Phase 12. Planned in
  Stage 3.

---

## Stage 3 plan — nurse brief, admin summary, and the assistant reads documents

**The idea:** every reader gets the same verified facts, in their own register, and every sentence
an AI writes must point at the fact it came from.

### 3a. One fact list (`intelligence/summaries/facts.py`)

`gather(db, patient, *, audience, window)` returns numbered facts `F1…Fn`, each with its source:

| Source | Included |
|---|---|
| Visits | Last completed visit (date, nurse, notes as **quoted data**), next scheduled visit |
| Readings | Latest reading per measure, and its direction over the window (reusing Phase 6's trend logic) |
| Medicines | Current schedule; doses missed in the last 7 days; medication changes in the window |
| Alerts | Open alerts; alerts in the window |
| **Documents** | **Verified facts only** (confirmed / edited / added), newest first, with document title, date and page; out-of-range ones flagged. The admin audience also gets unverified proposals, **labelled unverified** |

Capped at about 40 facts so a prompt stays small. The same list feeds 3b, 3c and 3d.

### 3b. Nurse brief — `GET /visits/{id}/ai-brief` (assigned nurse, admin)

- **Window: everything since the patient's last completed visit** (30 days if there is none yet).
  Documents verified in that window are included even if the document itself is older.
- **At most 8 bullets, action first, clinical wording.** For example: *"New lab report (2 Nov):
  HbA1c 8.1 %, above 4.0–5.6. Recheck sugar."*
- **LLM path:** Groq returns `[{"text": …, "cites": ["F3", …]}]`. `grounding.py` accepts it only if
  every bullet cites at least one real fact and **every number in a bullet appears in a fact it
  cites**. Anything else → the deterministic brief.
- **Deterministic brief:** the facts themselves, grouped (documents, alerts, medicines, readings),
  within the same 8-bullet limit. This is what ships with no key, and what the tests pin down.
- **UI:** a self-fetching **"Brief"** card at the top of the nurse visit screen, each bullet able
  to show its sources. If the endpoint fails, the card hides and the existing "Before you knock"
  card is unchanged.

### 3c. Admin summary — `GET /patients/{id}/clinical-summary?window=30d` (admin)

The same machinery, clinical and complete, every line cited, **unverified document facts included
and marked "unverified"**. Shown as a panel on the admin patient page. The nurse brief never
includes unverified facts.

### 3d. Ask DoorDoctor reads verified documents

| Piece | Change |
|---|---|
| Family context pack (`services/assistant_context.py`) | A new `documents` section: verified facts from the last 90 days (at most 20), in family wording, e.g. *"A blood test on 2 Nov showed HbA1c 8.1 %, above the expected range of 4.0–5.6."* Their numbers join `pack.numbers()`, so the existing "no invented numbers" gate covers them with no new code |
| Admin context pack | One line: how many documents are waiting for review, and how long the oldest has waited |
| Intents (`services/assistant_intents.py`) | `test_results` ("report", "blood test", "lab result", "what did the test say") and `prescription` ("prescription", "what did the doctor say", "what did the doctor write") |
| Rule-based answers (`services/assistant_fallback.py`) | One template each, so both work with no key |

**Rules for 3d:**

1. **Verified facts only.** Raw OCR text and proposals never reach the assistant.
2. **A prescription is not the medicine schedule.** Answers say *"the prescription uploaded on
   22 Dec lists ORS, 2 sachets"*, never *"she takes ORS"*. The schedule nurses give doses from
   stays the admin-managed medication list.
3. **The family jargon gate stays.** A fact whose label contains a banned word ("Systolic BP") is
   reworded through Phase 6's plain-label helper, or left out of the family pack.
4. **The boundary holds.** `assistant_context.py` reads `ExtractedFact` and `Document` through
   `app.models`, not `app.intelligence`, so `test_intelligence_boundary.py` is unchanged. The "in
   the record" status set moves onto `FactStatus` (`FactStatus.in_record()`), so both packages
   share one definition.

### Changes to existing files in Stage 3

| File | Change |
|---|---|
| `services/assistant_context.py` | Additive: one family section, one admin line |
| `services/assistant_intents.py` | Two intents added to the catalogue |
| `services/assistant_fallback.py` | Two answer builders |
| `models/enums.py` | `FactStatus.in_record()` helper |
| `frontend/src/pages/nurse/NurseVisitDetail.tsx` | One self-fetching card |
| Admin patient page | One panel |

No existing response shape changes; `/visits/{id}/brief` and the family summary are untouched.

### Tests planned

- **Grounding:** a bullet citing a fact that doesn't exist, a bullet with a number not in its cited
  facts, an uncited bullet, malformed JSON. Each falls back to the deterministic brief.
- **The nurse brief never contains an unverified fact;** the admin summary marks every unverified one.
- **Assistant:** "what did the blood test say?" answers from verified facts with no key; a rejected
  fact never appears; another family's documents never appear; an answer inventing a lab value is
  rejected by the existing number gate; a prescription answer never phrases it as the current
  schedule.
- **Prompt injection:** nurse notes and document text containing "ignore your instructions" can't
  produce an uncited bullet.

### Decisions and open questions

1. ✅ **The nurse brief covers everything since the patient's last completed visit** (decided
   2026-11-11). The nurse sees exactly what's new since someone was last in the home. For a
   patient with no completed visit yet, the brief falls back to the last 30 days, and says so.
2. ⬜ **A one-click "add to the medicine schedule"** for verified prescription medicines? Proposed:
   **not in Stage 3.** It changes what nurses administer, so it deserves its own change.
