# Phase 7 — AI assistant, family + admin (§2.3)

**Goal:** a family member can ask "how has Amma been this week?" in their own words and get an
answer grounded in their own patient's data — and an admin can ask "who needs attention today?" and
get the board. Both work with **no API key, no network and no account**, because the deterministic
matcher is the product and the model is a polish pass.

---

## The one idea this phase is built around

> **The model never queries the database.** The server assembles a role-scoped context pack, and the
> pack is the only thing the model is ever allowed to know.

That single decision is what makes an LLM safe to put in front of a family member's mother's blood
pressure. Everything below follows from it:

- **Authorization happens while the pack is built, not while the answer is written.** A family pack
  contains exactly the patients that pass `authorize_patient`. There is no prompt instruction to
  disobey, because another family's patient was never in the context to begin with.
- **The strongest gate is the analogue of Phase 6's "no invented numbers": no claim outside the
  pack.** Every number in an assisted answer must already appear in the pack or in the deterministic
  answer. A model cannot invent a reading it was never given.
- **The emergency intent never reaches the model.** "I think she is having a stroke" is not a
  question to hand to a 70B model with an 8-second timeout and a fallback path.

---

## ⚠️ §2.3's intent list was never supplied — the Phase 4 pattern applies

The founder's build prompt §2.3 lists the intents the fallback must answer. That section has never
been pasted into a build session. **Decision taken 2026-08-22: derive the intents and mark them
`ASSUMED`**, exactly as `core/pricing.py` did for §3's prices.

Consequences, and they are the whole reason this is written down:

- The catalogue lives in **one file**, `app/services/assistant_intents.py`. Nothing else in the
  codebase contains an intent string, a keyword or a starter question.
- Every entry is marked `ASSUMED` in the same style as `core/pricing.py`.
- A reconciliation table goes into `STATE.md` when the phase closes.
- When the real §2.3 arrives, reconciling it is a one-file change. **Keep it that way** — the moment
  a keyword is inlined into `assistant_fallback.py`, that promise is broken.

The derived catalogue, and what answers each one. Every intent is answerable from data that already
exists; this phase adds no clinical table.

| Role | Intent id | Question a person actually asks | Answered from |
|---|---|---|---|
| both | `emergency` | "something is wrong right now" | **short-circuit: 108 → nurse → admin** |
| family | `how_have_they_been` | "how has Amma been this week?" | `summary_service.build_deterministic` |
| family | `latest_readings` | "what were her last readings?" | `vitals_service.latest_for_patient` |
| family | `medicines` | "is she taking her medicines?" | `medication_service.adherence_for_patient` |
| family | `next_visit` | "when is the next visit?" | next scheduled `Visit` |
| family | `who_is_the_nurse` | "who is the nurse, are they verified?" | `Nurse.credential`, `verification_status` |
| family | `about_the_alert` | "what was that alert about?" | `Alert.breached_parameters`, translated |
| family | `my_plan` | "what does my plan cover?" | `subscription_service.entitlement` |
| family | `my_payments` | "what have I paid?" | `billing_service.invoices_for_user` |
| admin | `needs_attention` | "which patients need attention today?" | open alerts by severity |
| admin | `todays_board` | "what is on the board today?" | `visit_service.list_today_visits` |
| admin | `unassigned` | "which visits are unassigned?" | today's board, `nurse_id is None` |
| admin | `nurse_workload` | "how is Anitha doing?" | `admin_service.list_nurses` |
| admin | `revenue` | "what is MRR, who is past due?" | `billing_service.revenue_summary` |
| both | `capabilities` | "what can you tell me?" | the catalogue itself |
| both | `unknown` | anything unmatched | graceful capability answer + suggestions |

---

## Decisions taken with the founder before writing code (2026-08-22)

| Question | Answer | Consequence |
|---|---|---|
| §2.3's intent list | **Derive, mark `ASSUMED`** | one file, reconciliation table in STATE |
| Groq API key | **Founder will paste one** | steps 1–4 are built keyless first; live verification when it lands |
| Does a nurse get an assistant? | **No — family + admin only** | `require_family_or_admin`, and a **test** asserts the 403 so it is explicit, not accidental |
| Conversation retention | **Store, scoped to the asker** | only the asker ever reads their own history; no admin route touches it |

### The retention stance, written out

`assistant_messages` stores a family member's question about a named relative. That is PHI-adjacent
and the docstring on the model says so. The protection is **access scoping, not redaction** — unlike
Phase 3's reset tokens, nothing in this row is a credential, so redacting it would destroy the
feature without protecting anything. What matters instead:

- `GET /assistant/conversations` filters on `user_id == current_user.id`, full stop. **There is no
  admin route that reads another user's history**, and adding one later is a consent decision, not a
  convenience.
- Question length is capped in the schema, so the table cannot become a free-text dumping ground and
  the prompt has a bound.
- Erasure belongs with Phase 10's consent + audit log + family Privacy & Data page. Noted as a
  deferral rather than half-built here.

---

## Build order — the fallback first, exactly as Phase 6 did

| # | Step | Needs a key? |
|---|---|---|
| 1 | `assistant_intents.py` — the `ASSUMED` catalogue, one file | no |
| 2 | `assistant_context.py` — role-scoped context packs. **The security boundary.** | no |
| 3 | `assistant_fallback.py` — deterministic matcher + answer composer, **tested first** | no |
| 4 | `models/assistant.py`, `assistant_service.py`, `routers/assistant.py`, schemas | no |
| 5 | The Groq path behind the **existing** `llm_client.complete()`, 8s, gated | optional |
| 6 | Frontend: `api/assistant.ts`, `AssistantPanel`, two pages, two nav entries | no |

**Verify with `GROQ_API_KEY` unset before calling the phase done.** That is the demo configuration,
not an edge case, and Phase 6 proved the pattern.

---

## File-by-file

### Backend — new files

| File | Contents |
|---|---|
| `app/services/assistant_intents.py` | The `ASSUMED` catalogue: `Intent(id, roles, patterns, needs_patient, suggestion)`. Exports `INTENTS`, `EMERGENCY`, `for_role()`, `suggestions_for()`. **The only file containing an intent string.** |
| `app/services/assistant_context.py` | `build_family_pack(db, user, patient)` and `build_admin_pack(db, user)`. Returns a `ContextPack` carrying `facts: dict`, `render()` for the prompt and `numbers()` for the validation gate. |
| `app/services/assistant_fallback.py` | `match(question, role) -> Intent` and `answer(intent, pack, question) -> Answer`. No network, no key, no model. Answers every intent in the catalogue. |
| `app/services/assistant_service.py` | Orchestration: rate limit → match → **emergency short-circuit** → build pack → deterministic answer → optional gated rewrite → persist → return. |
| `app/models/assistant.py` | `AssistantMessage`. One row per exchange, readable only by `user_id`. |
| `app/routers/assistant.py` | `POST /assistant/ask`, `GET /assistant/conversations`, `GET /assistant/suggestions`. |
| `app/schemas/assistant.py` | `AssistantAskRequest`, `AssistantAnswerOut`, `AssistantMessageOut`, `AssistantSuggestionOut`. |
| `tests/test_assistant.py` | The phase's test file. |

### Backend — edited files

| File | Change |
|---|---|
| `app/services/summary_service.py` | Add `PLAIN_METRIC_LABELS` + `plain_metric_label()`. **`summary_service` owns the vocabulary rule**, so the family-facing name for `systolic_bp` lives there and not in a second table in the assistant. |
| `app/core/ratelimit.py` | `ASSISTANT_PER_USER = (30, 3600)` beside the forgot-password budgets. |
| `app/models/enums.py` | `AssistantSource` — `DETERMINISTIC`, `ASSISTED`. |
| `app/models/__init__.py` | Register `AssistantMessage`, `AssistantSource`. |
| `app/models/user.py` | `assistant_messages` relationship, cascade like the rest. |
| `app/main.py` | Include `assistant.router`; one sentence in `DESCRIPTION`. |
| `tests/conftest.py` | Nothing to add — the autouse `clean_process_state` fixture already resets the limiter, and this phase adds **no new process-global cache** (see below). |

### Frontend — new files

| File | Contents |
|---|---|
| `src/api/assistant.ts` | `assistantApi.ask / conversations / suggestions`. |
| `src/components/assistant/AssistantPanel.tsx` | The shared thread: suggestion chips, textarea, answers, source badge, disclaimer, emergency treatment. Used by both roles. |
| `src/components/assistant/AssistantMessage.tsx` | One exchange. Emergency answers get the `critical` treatment and a `role="alert"`. |
| `src/pages/family/FamilyAssistant.tsx` | "Ask DoorDoctor" — patient-scoped. |
| `src/pages/admin/AdminAssistant.tsx` | "Ask DoorDoctor" — org-scoped. |
| `src/test/assistant.test.tsx` | Vitest. |

### Frontend — edited files

| File | Change |
|---|---|
| `src/types/index.ts` | `AssistantAnswer`, `AssistantMessage`, `AssistantSuggestion`, `AssistantSource`. |
| `src/App.tsx` | Routes `/family/assistant` and `/admin/assistant`. |
| `src/components/layout/navigation.ts` | A nav entry per role (`MessageCircleQuestion`). Family's is `primary` — it is the point of the product; the mobile bar is already at four, so `Reports` yields. |
| `src/pages/family/FamilyDashboard.tsx` | One `LinkButton` under the summary: "Ask a question about {first name}". Phase 6's layout is otherwise untouched. |

---

## The parts that need to be got right

### 1. The context pack is the security boundary

`build_family_pack` takes a `Patient` that has **already** been through `authorize_patient`. The
router resolves it; the service never accepts a bare `patient_id`. Someone else's patient is a
**404**, never a 403 — a 403 confirms the record exists, which is enough to learn that a named person
is a DoorDoctor patient. `authorize_report` is the worked example.

The pack is also the only thing the model sees. Not the database, not the session, not the user row.

### 2. A family pack must never quote an alert message

`alert_service.build_alert_message()` produces *"Systolic blood pressure 148 mmHg (above configured
threshold 140 mmHg)"*. Three banned words in one sentence. Pasting `Alert.message` into a family
answer would put the exact vocabulary Phase 6 exists to prevent straight back in front of a family
member — and the runtime guard would then reject the whole answer, so the bug would present as "the
assistant refuses to talk about alerts".

Family answers translate `Alert.breached_parameters` through `plain_metric_label()` instead. **Admin
answers use `alert_service.METRIC_LABELS` unchanged** — admins are clinical staff and "systolic" is
the correct word for them.

### 3. The emergency intent short-circuits everything

Matched **first**, before role scoping, before the pack is built, before any thought of a model.
Returns the fixed escalation: **call 108, then the nurse, then DoorDoctor**. The response carries
`intent: "emergency"` so the UI can render it as an alert rather than a paragraph.

A test monkeypatches `llm_client.complete` to raise and asserts an emergency question still answers.

### 4. The gates between a model and a reader

`assistant_service` owns them, not `llm_client` — the client is transport, the service owns meaning.
Same division as Phase 6.

| # | Gate | Applies to |
|---|---|---|
| 1 | No number outside `pack.numbers()` ∪ the deterministic answer | **both roles** |
| 2 | No banned clinical vocabulary (`contains_clinical_language`) | **family only** |
| 3 | No advice register (`FORBIDDEN_REGISTER`, reused from `summary_service`) | both roles |
| 4 | Length within bounds, non-empty | both roles |

Gate 1 is the one that matters and is the direct analogue of Phase 6's rule. Gate 2 is deliberately
*not* applied to admins: a platform that says "blood pressure" to a family and "systolic" to a nurse
manager has one voice per audience, which is correct — one voice for both is what would be wrong.

A failed gate falls back **silently** to the deterministic answer, and `source` reports
`deterministic` honestly, so a demo can *show* the fallback rather than assert it.

### 5. The assisted path answers from the pack — it does not merely re-word

Phase 6's rewrite could only re-voice a finished paragraph. The assistant is given the pack, the
question and the deterministic answer as a grounded baseline, and may combine facts across them.
That is where the assisted path earns its place: an unmatched question ("has she been sleeping badly
since the new tablet?") gets a stiff capability answer deterministically and a genuinely useful one
from the model — while gate 1 still makes an invented reading impossible.

### 6. No new cache

The summary cache exists because a dashboard paints on every load with identical inputs. An
assistant question is typed by a human and is different every time; a cache keyed on free text would
almost never hit and would be one more process-global to reset. **If that changes, register it in
the autouse `clean_process_state` fixture** — or test order will decide test outcomes.

### 7. Rate limiting

`POST /assistant/ask` is metered at **30 per user per hour** via the existing `core/ratelimit.py`.
An unmetered LLM endpoint behind a login is the obvious way to burn a free Groq tier. The limiter is
already reset per-test by the autouse fixture, so this costs no test plumbing.

---

## API surface

```
POST /assistant/ask
     {question: str (1..500), patient_id: int | null}
  -> {answer, source, intent, patient_id, disclaimer, suggestions[], created_at}

GET  /assistant/conversations?limit=
  -> the caller's own history, newest first. Never anyone else's.

GET  /assistant/suggestions?patient_id=
  -> role-scoped starter questions
```

All three depend on `require_family_or_admin`. A nurse gets 403; an anonymous caller gets 401.

---

## Test plan

`tests/test_assistant.py`, built alongside step 3 and grown through step 5.

**The fallback, with no key (the definition of done)**
- Every intent in the catalogue is matched from a representative question — parametrized over
  `INTENTS`, so **adding an intent without a test is impossible**.
- Every family answer passes `contains_clinical_language(...) is None`.
- Every intent produces a non-empty answer against the seeded demo data.
- `llm_client.complete` monkeypatched to raise: every intent still answers.

**Security**
- A family user asking about another family's patient → **404** (`other_family` fixture).
- A family user omitting `patient_id` gets their own patient, not a scan.
- A nurse → **403**. Anonymous → **401**.
- An admin cannot read a family member's conversation history.
- A family pack never contains a second family's patient name.

**Emergency**
- Matched first and answered without any LLM call, proven with an exploding monkeypatch.
- The answer names **108**, the nurse and DoorDoctor, in that order.

**Rate limit**
- The 31st question in an hour → **429** with `Retry-After`.

**The assisted path** (monkeypatched `httpx`/`complete`, copying `test_summary.py`'s `assisted`
fixture)
- A clean answer is used and declared `assisted`.
- An answer inventing a number is discarded → `deterministic`.
- A family answer reintroducing "systolic" is discarded.
- The **same** answer to an **admin** is *kept* — gate 2 is family-only, and this asserts it.
- An answer drifting into advice is discarded.
- No upstream call is attempted when no key is configured.

**Schema**
- A 501-character question → 422. An empty question → 422.

Vitest `assistant.test.tsx`: suggestion chips render and populate the box; submitting shows the
answer and the disclaimer; an emergency answer renders with `role="alert"`; the `deterministic`
source badge is visible (the demo shows the fallback, so it must be legible).

**Targets:** backend **287 → ~320**. Vitest **61 → ~66**.

---

## Definition of done

- [ ] Every intent answered with `GROQ_API_KEY` unset, proven by test
- [ ] Family user asking about another family's patient refused (404), proven by test
- [ ] Emergency path returns 108 → nurse → admin without touching the model, proven by test
- [ ] Nurse gets 403, proven by test
- [ ] Backend test count grows from 287; Vitest from 61
- [ ] `npx tsc -p tsconfig.json --noEmit` clean, `npm run build` clean, no `any`, no `@ts-ignore`
- [ ] Verified live in Chrome at 375 / 768 / 1024 / 1440, zero console errors
- [ ] Live verification against the real Groq endpoint once the founder's key lands
- [ ] This file closed with an "As executed" section
- [ ] One conventional commit on `main`, hash recorded in `STATE.md`'s phase table
- [ ] `ASSUMED` intent reconciliation table added to `STATE.md`

---

## As executed

Built in the planned order — catalogue, pack, fallback, service, gates, frontend — and every step
below step 5 was verified with `GROQ_API_KEY` unset before the Groq path was written at all.

### What the plan got right and did not have to change

The five "parts that need to be got right" all survived contact. In particular **§2 was a real
prediction, not a hypothetical**: `alert_service.build_alert_message()` produces *"Systolic blood
pressure 148 mmHg (above configured threshold 140 mmHg)"*, and a family pack that quoted it would
have failed its own banned-word gate and presented as "the assistant refuses to talk about alerts".
`assistant_context._plain_alert_causes` translates `breached_parameters` through
`summary_service.plain_metric_label` instead, and de-duplicates, because both halves of a blood
pressure share one spoken name.

### Decisions taken during the build

- **The family context pack is itself written in the family's vocabulary**, not merely the answers
  composed from it. This was not in the plan and it matters: it turns the banned-word gate from a
  trap into a near-certainty, because a model copying a phrase straight out of the context cannot
  reintroduce a word Phase 6 exists to keep out. `test_the_family_context_pack_itself_avoids_clinical_language`
  pins it.
- **`summary_service` gained `PLAIN_METRIC_LABELS` / `plain_metric_label()`**, and
  `_numbers_in` became the public **`numbers_in()`**. Both belong to the module that owns the
  vocabulary rule and the "no invented number" rule; a second copy in the assistant is exactly how
  "blood sugar" and "glucose" end up on the same screen.
- **Emergency matching is phrases only, never scored keywords.** A bare "help" false-positives on
  "can you help me read my bill?", and a bare `108` false-positives on a blood sugar of 108 — which
  is a real reading. The catalogue matches `call 108` / `dial 108` / `phone 108`, and
  `test_ordinary_questions_are_not_treated_as_emergencies` pins both cases.
- **The assisted path answers from the pack rather than re-wording a finished paragraph** (Phase 6's
  shape). It receives the pack, the question and the deterministic answer as a grounded baseline.
  That is where it earns its place — an unmatched question gets a stiff capability answer
  deterministically and a useful one from the model — while gate 1 still makes an invented reading
  impossible.
- **The suggestion catalogue excludes `capabilities`** (`SUGGESTION_EXCLUDED`). It stays matchable,
  but offering "what can you tell me about?" *as a chip* is circular — the chips are the answer to
  it — and it cost a row in a list that stacks vertically on a phone.
- **No new process-global cache.** A summary is painted repeatedly from identical inputs; an
  assistant question is typed by a human and is different every time. A cache keyed on free text
  would almost never hit and would be one more thing to reset in `clean_process_state`.

### Fixed on the way

- **`_reading_lines` prefixed every measurement with the patient's name**, so a six-measurement
  answer read "Lakshmi's blood pressure was 132 over 84, Lakshmi's heart rate was 80, Lakshmi's blood
  sugar was 109…". It is `_reading_phrases` now and returns bare `label value` phrases; the caller
  owns the sentence. **No pronoun is used** — `Patient.gender` records a gender, not pronouns, and
  "Lakshmi's readings were:" needs neither.
- **Pluralisation across the admin answers**: "1 visits", "1 nurses on the roster", "1 active
  patients out of 1", "across 1 unpaid invoices". All routed through `_plural` now. Invisible at 28
  patients and glaring at one.
- **"a RN/ANM"** — wrong article, and unfixable in general because the credential is a data value.
  Reworded to "a qualified {credential}", which sidesteps every agreement case.
- **`scrollIntoView` is feature-detected in `AssistantPanel`.** It does not exist in jsdom, and
  keeping the newest answer in view is a convenience that must never throw inside a render effect and
  blank the thread.
- **The server's `disclaimer` was returned and never rendered.** §2.3 requires every answer to close
  with it, and its wording differs by role. The panel now holds it from the most recent answer and
  shows it once below the composer — the requirement met without repeating a paragraph under every
  message.
- **The provenance badge is suppressed on an emergency answer.** That answer is a fixed escalation,
  not a record lookup, and "Direct from records" beside "call 108" competes with the one instruction
  that matters.
- **`LinkButton` gained the `icon` prop `Button` already had.** Per the primitives layer's own rule,
  a control a screen needs is added to the layer rather than styled inline — and the two now carry
  the same prop, so a row of actions does not have to know which of them navigates.

### Verification

| Check | Result |
|---|---|
| `pytest` | **365 passed** (was 287) — **+78** |
| `vitest` | **71 passed** (was 61) — **+10** |
| `tsc -p tsconfig.json --noEmit` | clean |
| `npm run build` | clean |
| `python -m app.seed`, `--small`, `--demo-reset` | clean |
| `python -m app.billing --generate-invoices --dry-run` | clean |
| Chrome at 375 / 768 / 1024 / 1440, family + admin | **zero console errors** |

Live in the browser: the family thread answers "How has amma been this week?" from the real seed,
"she has collapsed and is not breathing" renders the critical treatment with `role="alert"`, and the
admin thread reports **MRR ₹2,30,250 across 20 active subscriptions** and **Sanjay Dutta past due** —
matching the Phase 5 ledger exactly, because the pack borrows `billing_service.revenue_summary`
rather than re-querying it.

### Deliberately deferred

- **No nurse assistant.** Decided with the founder; `test_a_nurse_has_no_assistant` makes the 403
  explicit rather than accidental. It needs its own context pack and intents and belongs with
  Phase 10's nurse operations screens.
- **No erasure of stored exchanges.** The retention stance is written into `models/assistant.py`;
  deletion belongs with Phase 10's consent record, audit log and family Privacy & Data page. Deleting
  rows without those is a half-built promise.
- **The `AI_ASSISTANT` entitlement is not enforced.** It is `True` on all five plans, so a gate would
  be a no-op today, and Phase 4 deliberately deferred point-of-use entitlement enforcement until §3
  is reconciled. Consistent with that, not an oversight.
- **No live Groq request.** See the open item carried into `STATE.md`.
