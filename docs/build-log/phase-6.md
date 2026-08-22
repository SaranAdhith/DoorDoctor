# Phase 6 — Plain-language summary + reports (§2.2, §4.1)

**Goal:** the first thing a family member sees stops being a grid of clinical numbers and becomes a
paragraph in the language they actually speak. Then that same paragraph becomes a document they can
keep — a weekly and monthly PDF report, generated on a schedule and on demand.

The whole existing dashboard survives **untouched**, below a divider. Nobody loses the detail; the
detail stops being the front door.

---

## The one idea this phase is built around

> A summary a family member can read is a **product feature**, not a model output.

Which means the deterministic generator is the product and the LLM is an optional polish pass. It
ships in that order, and it ships working alone. Steps 1–3 need no key, no network and no account.
Step 4 makes the prose warmer when a key happens to be present, and is **invisible when it is not**.

Everything in this phase follows from that:

- The **banned-word list is a runtime guard, not only a test.** A test that asserts the deterministic
  generator avoids "systolic" is worth little if the rewrite three steps later puts it back. The same
  function checks both, and a rewrite that fails it is discarded silently.
- The rewrite may only **re-word**, never re-state. Four validation gates below, of which the
  strongest is: **every number in the rewrite must already appear in the deterministic text.** A
  model cannot invent a blood pressure reading if a digit it did not receive is grounds for
  rejection.
- `source` is reported honestly in the payload (`deterministic` / `assisted`) so the demo can show
  the fallback working rather than assert it.

---

## Build order

| # | Step | Needs a key? |
|---|---|---|
| 1 | `services/summary_service.py` — deterministic generator + banned-word guard | no |
| 2 | `GET /patients/{id}/plain-summary?window=7d\|30d\|90d` | no |
| 3 | `components/family/PlainSummary.tsx`, first on the family dashboard | no |
| 4 | `services/llm_client.py` — Groq rewrite, 2s, cached, four gates, silent fallback | optional |
| 5 | `models/report.py` + `services/report_service.py` + WeasyPrint + APScheduler + reports UI | no |

**Verify step 4 with `GROQ_API_KEY` unset before calling the phase done.** That is the demo
configuration, not an edge case.

---

## File-by-file

### Backend — new files

| File | Contents |
|---|---|
| `app/services/summary_service.py` | The deterministic generator. Windowed data gather → trend analysis → plain English. Exports `plain_summary()`, `build_deterministic()`, `contains_clinical_language()`, `WINDOWS`. |
| `app/services/llm_client.py` | **The single LLM boundary for the whole platform.** `complete()` returns `str \| None` and *never raises*. Phase 7's assistant calls the same function with a different timeout. |
| `app/models/report.py` | `Report` — one row per patient per kind per period, carrying a **frozen** narrative. |
| `app/services/report_service.py` | `generate()`, `list_for_patient()`, `render_pdf()`, `run_weekly()`, `run_monthly()`. |
| `app/routers/reports.py` | `GET /patients/{id}/reports`, `POST /patients/{id}/reports/generate`, `GET /reports/{id}`, `GET /reports/{id}/pdf`. |
| `app/schemas/summary.py` | `PlainSummaryOut`, `SummaryHighlight`. |
| `app/schemas/report.py` | `ReportOut`, `ReportGenerateRequest`. |
| `app/templates/reports/report.html` | WeasyPrint template. Same `string.Template` convention as `templates/invoices/invoice.html` — **not** a second templating engine. |
| `app/scheduler.py` | APScheduler `BackgroundScheduler`, two cron jobs, started from `main.lifespan`. |

### Backend — edited files

| File | Change |
|---|---|
| `app/config.py` | `groq_api_key`, `groq_model`, `groq_base_url`, `assistant_enabled`, `reports_scheduler_enabled`. |
| `app/models/enums.py` | `class ReportKind(str, Enum)` — `WEEKLY`, `MONTHLY`, `ON_DEMAND`. |
| `app/models/__init__.py` | Register `Report` and `ReportKind`. |
| `app/models/patient.py` | `reports` relationship, `cascade="all, delete-orphan"` like the rest. |
| `app/services/vitals_service.py` | `history_since(db, patient_id, since)` — the existing `history_for_patient` limits by **count**, and a window limits by **date**. |
| `app/services/medication_service.py` | `adherence_for_patient(..., since=None)` — one optional argument, so there is one adherence calculation and not two. |
| `app/routers/patients.py` | The `plain-summary` route. |
| `app/core/dependencies.py` | `authorize_report` — resolves the report's patient and delegates to `authorize_patient`, so someone else's report is a **404** for the same reason someone else's patient is. |
| `app/main.py` | Include `reports.router`; start/stop the scheduler in `lifespan`; a sentence in `DESCRIPTION`. |
| `tests/conftest.py` | `REPORTS_SCHEDULER_ENABLED=false` and `GROQ_API_KEY=""` in the env block; extend the autouse reset fixture to clear the summary cache. |
| `requirements.txt` | `apscheduler==3.11.0`. |

### Frontend

| File | Change |
|---|---|
| `src/components/family/PlainSummary.tsx` | **new** — the card. `SegmentedControl` for the window, skeleton / empty / error-with-retry. |
| `src/pages/family/FamilyReports.tsx` | **new** — report list, generate button, open PDF. |
| `src/api/summary.ts` | **new** — `summaryApi`, `reportsApi`, `openReportPdf` (mirrors `openInvoicePdf`). |
| `src/types/index.ts` | `PlainSummary`, `SummaryHighlight`, `SummaryWindow`, `Report`, `ReportKind`. |
| `src/pages/family/FamilyDashboard.tsx` | **Three inserted lines and nothing else.** `<PlainSummary/>` after the alert banner, then a "Detailed health record" divider above the existing status card. The rest of the file is not touched. |
| `src/App.tsx` | `/family/reports`. |
| `src/components/layout/navigation.ts` | Family nav item "Reports" (`FileText`). |
| `src/test/plainSummary.test.tsx` | **new** — Vitest. |

---

## Step 1 — the deterministic generator, in detail

### Window

`7d` / `30d` / `90d`, validated by a `Literal` in the schema so a bad value is a **422** and never a
silent default.

### What it reads

Only what already exists: readings in the window (`vitals_service.history_since`), doses in the
window (`medication_service.adherence_for_patient(since=)`), visits in the window, alerts raised and
resolved in the window. No new columns, no new tables.

**Patient conditions are seed-only** (`demo_data.PatientSpec.conditions` never reaches the `Patient`
table), so the generator does not mention a diagnosis. That is the right outcome anyway — §2.2 wants
observations, not clinical interpretation.

### Trend detection

Split the window's readings in half, compare the means, and only call it a trend when the gap clears
a per-measure **noticeable change** floor:

| Measure | Floor | Why |
|---|---|---|
| Blood pressure (upper) | 5 mmHg | Below this is cuff-and-posture noise. |
| Blood pressure (lower) | 4 mmHg | |
| Heart rate | 5 bpm | |
| Blood sugar | 15 mg/dL | Swings with meals; a small mean shift means nothing. |
| Oxygen | 1.5 % | The scale is compressed; 1.5 points is a lot. |
| Temperature | 0.5 °F | |
| Weight | 1.5 kg | Below this is scales and clothing. |

Under the floor the answer is **"steady"**, which is a real finding and the most common one. A
generator that reports a trend every week is a generator nobody believes by week three.

### Vocabulary

The banned list is the specification. The mapping it forces:

| Never | Always |
|---|---|
| systolic / diastolic | blood pressure, "the upper number" / "the lower number" |
| SpO2 | oxygen levels |
| blood glucose | blood sugar |
| adherence | "took 13 of her 15 doses on time" |
| threshold / breach | "outside the range we watch for her" |
| vitals | readings, checks |
| metric | measure |
| escalation | "we called the family and the nurse" |

Full banned list, asserted by test: `systolic`, `diastolic`, `spo2`, `sp02`, `adherence`,
`threshold`, `breach`, `vitals`, `metric`, `escalation`. Checked case-insensitively as substrings, so
"thresholds" and "breached" are caught too.

### Output

```
patient_id, patient_name, window, window_label,
headline            one sentence
paragraphs          2–4 short paragraphs: how they have been · medicines · visits and care
highlights          [{tone: good|watch|attention, text}]
what_happens_next   [str]
reading_count, dose_count, visit_count
generated_at, source ("deterministic" | "assisted"), disclaimer
```

**The no-data case is a first-class output, not an error.** A patient with no readings in the window
gets an honest "we have not recorded any checks in the last seven days" summary with
`reading_count: 0` — never a fabricated reassurance, and never a 404.

---

## Step 4 — the LLM boundary

### `llm_client.complete()`

```
complete(*, system: str, user: str, timeout: float, max_tokens: int = 400) -> str | None
```

- Groq's OpenAI-compatible `POST {base}/chat/completions` via **`httpx`, already a dependency**.
- Returns `None` — never raises — for: assistant disabled, no key, timeout, connection error, non-2xx,
  malformed body, empty completion. Every caller's fallback path is therefore the same path.
- **Never logs the prompt or the completion.** A prompt here contains a named patient's readings.
  Logs get the failure reason and the elapsed time.
- `temperature=0.2`. This is a re-wording task; creativity is the failure mode.

### The four gates a rewrite must clear

Applied in `summary_service`, not in `llm_client` — the client is transport, the service owns meaning.

1. **No banned words.** Same `contains_clinical_language()` the deterministic test uses.
2. **No new numbers.** Every numeric token in the rewrite must appear in the deterministic source
   text. This is the anti-hallucination gate and the one that matters most.
3. **Length sanity.** Between 0.5× and 2× the deterministic character count.
4. **No forbidden register.** `diagnos`, `prescri`, `should stop taking`, `you must`, `emergency room`
   — a summary must not drift into advice.

Fail any gate → the deterministic text is returned and `source` stays `deterministic`. The family
member is never shown that anything happened.

### Cache

15 minutes per `(patient_id, window)` **plus a fingerprint of the deterministic text**. Time alone
would keep serving last quarter-hour's paragraph after a nurse records a new reading; the fingerprint
makes new data bust the cache immediately and makes the TTL a cost control rather than a correctness
risk. Module-level with `.reset()`, exactly like `core/ratelimit.py`, and reset by the autouse
fixture in `conftest.py` for exactly the same reason: process-global state otherwise lets test order
decide test outcomes.

---

## Step 5 — reports

### The record is frozen; the PDF is rendered

`Report` stores the **narrative JSON at generation time**. The PDF is re-rendered from that stored
snapshot on every fetch, exactly as `billing_service.render_pdf` re-renders an invoice from stored
totals. Phase 4's rule applies unchanged: *an issued document is a historical record*. A report from
six weeks ago must still say what it said six weeks ago, even though the underlying readings have
moved on — and no blob column is needed to achieve it.

### One report per patient per kind per period

Unique constraint on `(patient_id, kind, period_start)`, plus a lookup before insert — the same
belt-and-braces as invoices. Re-generating an existing period **refreshes** that row (new narrative,
new `generated_at`) rather than adding a duplicate. The scheduler can therefore run twice without
producing two Sunday reports, and the demo's "Generate report" button stays honest on the fifth press.

### Scheduling

`app/scheduler.py`, APScheduler `BackgroundScheduler`, `ZoneInfo("Asia/Kolkata")` from the stdlib:

- **Weekly** — Sunday 18:00 IST, covering the seven days ending that day.
- **Monthly** — the 1st at 06:00 IST, covering the previous calendar month.

Started and shut down in `main.lifespan`, gated by `REPORTS_SCHEDULER_ENABLED` (default true;
**`false` in `tests/conftest.py`**, because `TestClient` as a context manager runs the lifespan and a
test suite must not start a background thread). The job bodies `run_weekly(db)` / `run_monthly(db)`
are plain functions called directly by tests — the scheduler is wiring, and wiring is not what needs
proving.

A generated report raises a `system` notification for the family member through the existing
`notification_service`, so it appears in the bell without a second mechanism.

---

## Tests

### Backend — `tests/test_summary.py`, `tests/test_reports.py`, `tests/test_llm_client.py`

- Banned words absent from **every string in the payload**, all three windows. The test is the spec.
- A patient with no readings gets an honest empty-window summary, not a 404 and not a fabrication.
- Authorization: another family → 404; assigned nurse → 200; unassigned nurse → 404; no token → 401.
- Bad window → 422.
- `llm_client.complete()` returns `None` with no key, on timeout, on 500, on a malformed body — and
  never raises in any of those.
- A rewrite containing a banned word is discarded. A rewrite containing an **invented number** is
  discarded. A clean rewrite is accepted and flips `source` to `assisted`.
- Cache: two calls in the window make **one** upstream call; a new reading busts it.
- Reports: generate → row with frozen narrative; regenerate the same period → **same id**, newer
  `generated_at`; PDF begins `%PDF-`; PDF 401 without a token and 404 for another family; the frozen
  narrative does **not** change when new readings arrive afterwards; `run_weekly` is idempotent.

### Frontend — `src/test/plainSummary.test.tsx`

Renders the headline and paragraphs; the window control refetches with the new window; the error
state offers retry.

---

## Acceptance

```bash
cd backend  && .venv/bin/python -m pytest                      # all green, count only grows
cd backend  && .venv/bin/python -m app.seed                    # clean
cd frontend && npx tsc -p tsconfig.json --noEmit               # zero errors
cd frontend && npm run build && npx vitest run                 # clean, green
```

Plus, live in Chrome at 375 / 768 / 1024 / 1440:

1. **With `GROQ_API_KEY` unset** — the family dashboard leads with the summary, the window control
   switches between three genuinely different paragraphs, and the detailed dashboard is intact below
   the divider.
2. Generate a report, open the PDF, confirm it is a real document with the narrative in it.
3. The 148/92 demo path still runs end to end.

Commit: `feat(summary): plain-language health summaries and weekly report PDFs`

---

## As executed

Shipped as planned, in the planned order. Five things went differently:

1. **`build_deterministic` gained an explicit period.** The plan had the generator take a window
   keyword and compute `since` from `now()`. That produced a monthly report headed
   "1 July — 1 August" whose narrative quoted a 21 August reading — the stated period and the content
   disagreed. The generator now takes `[since, until)` (`build_for_period`), and the upper bound was
   pushed down into `vitals_service.history_since` and `medication_service.adherence_for_patient`.
   **Every test passed while this bug was live.** It was caught by rendering the PDF and looking at it.

2. **`period_end` is deliberately *not* truncated to midnight**, though `period_start` is. The
   truncated start is what makes regeneration idempotent; truncating the end would have dropped
   Sunday's visit from the report generated on Sunday evening. Monthly is the exception — a closed
   calendar month has both bounds on the 1st.

3. **The report narrative is unassisted, by choice.** The plan did not say either way. A document a
   family keeps should not read differently depending on whether an API key happened to be set when
   the scheduler fired, so `report_service` calls `build_for_period` directly and never the assisted
   path.

4. **`SegmentedControl` segments no longer wrap.** "This month" wrapped to two lines at the
   constrained desktop width and distorted the control's height. A wrapping segment label is always
   wrong, so `whitespace-nowrap` went into the primitive rather than into this one call site.

5. **The four gates run in `summary_service`, not `llm_client`.** As planned, but worth restating:
   the client is transport and the service owns meaning. Phase 7 should validate its assistant output
   the same way rather than pushing rules down into the shared client.

### Counts

| | Before | After |
|---|---|---|
| Backend tests | 210 | **287** |
| Vitest | 56 | **61** |
| Backend dependencies | — | **+`apscheduler` 3.11.3** (Groq needed none) |

### Verified live

Chrome at 375 / 768 / 1024 / 1440, zero console errors, **with `GROQ_API_KEY` unset**: the summary
leads the family dashboard, the three windows produce genuinely different narratives, the detailed
clinical dashboard is intact below the divider, a generated report opens as a real PDF (200 with a
bearer token, 401 without), and recording 148/92 still raises an alert the summary immediately
reflects.

**Not verified:** any request to the real Groq endpoint. No key has been supplied. Every LLM path is
proven against a monkeypatched `httpx`, and the demo is proven correct and complete without one.
