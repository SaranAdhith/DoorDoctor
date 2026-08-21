# DoorDoctor Platform v2 — Build State

Running ledger for the multi-phase build. Updated at every phase boundary.
If context is lost, this file plus `git log` restores full state.

## Locked decisions

| Decision | Answer |
|---|---|
| Source of facts | The build prompt is the source of truth. No business documents exist in the repo. Every price, tier, ratio and founder name comes from the prompt verbatim. Invent no traction, testimonials, customer counts, certifications or partner logos — DoorDoctor is pre-launch. |
| Checkpointing | Report at each phase boundary and continue. No waiting for approval between phases. |
| Git | Commit directly on `main`, one conventional commit per phase boundary, full suite green before each. |
| LLM provider | **Groq, not Anthropic.** Free-tier key supplied by the founder when needed. No `anthropic` package, no Claude API key. Deterministic fallback is mandatory and built first. |

### Founders (always named together, as an equal pair)
- **Saran Adhith** — Founder & CEO
- **Darren D'Souza** — Co-Founder

## Phase status

| Phase | Scope | Status |
|---|---|---|
| 1 | Terminology refactor (caregiver→nurse, coordinator→admin) | ✅ done |
| 2 | Design system, UI primitives, sidebar navigation | ⬜ not started |
| 3 | Forgot password + login rebuild | ⬜ not started |
| 4 | Subscriptions, plans, billing, quotas, referrals, loyalty | ⬜ not started |
| 5 | Realistic seed data | ⬜ not started |
| 6 | Plain-language summary + reports | ⬜ not started |
| 7 | AI assistant (family + admin) | ⬜ not started |
| 8 | Public marketing site + leads | ⬜ not started |
| 9 | Clinical features (labs → escalation) | ⬜ not started |
| 10 | Trust, GPS, medication, community, consent, ops, notifications | ⬜ not started |
| 11 | Multi-family, hardening, tests, docs | ⬜ not started |

## Baseline (before Phase 1)

- Backend: 73 pytest cases passing via `backend/.venv/bin/python -m pytest` (Python 3.13.12).
- Frontend: 2 Vitest files, TypeScript strict, `frontend/node_modules` present (Node v20.20.2).
- WeasyPrint system libs (pango, cairo, harfbuzz, gobject) verified present on this machine.
- PyPI and npm registry reachable.

## Environment variables

| Variable | Added in | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | baseline | `sqlite:///./doordoc.db` | Database connection |
| `JWT_SECRET` | baseline | `change-this-in-development` | Token signing |
| `JWT_EXPIRE_MINUTES` | baseline | `1440` | Access token lifetime |
| `CORS_ORIGINS` | baseline | `http://localhost:5173,...` | CORS allow-list |
| `VITE_API_BASE_URL` | baseline | `http://localhost:8000/api/v1` | Frontend API base |

## Dependencies added

*(none yet)*

## Phase results

### Phase 1 — terminology refactor (2026-08-21)
- 51 files rewritten, 16 paths renamed via `git mv` (history preserved), ~700 occurrences resolved.
- Grep audit: **0** hits for caregiver/coordinator outside `docs/build-log/`.
- 73 backend tests pass · frontend builds clean · 11 Vitest tests pass.
- Live smoke test: all three roles log in, `/admin/summary` and `/nurses` serve, old
  `/coordinator/summary` and `/caregivers` return 404, and the 148/92 breach path still runs
  end-to-end (nurse records → family + admin see the alert → admin resolves).
- Doc repairs beyond the rename: README architecture box and DESIGN.md route map were
  column-aligned around the longer old words and needed re-padding; the SQLite box top border
  was one column short (pre-existing) and is now square.
- Family-facing prose written by hand rather than substituted, because "your admin" is wrong to
  say to a family member: FamilyAlerts now reads "Your DoorDoctor care team reviews and resolves
  alerts", FamilyDashboard "Ask DoorDoctor to link a patient".
- `.env.example` had an uncommitted stray `ju` prefix on line 1; removed, file now matches HEAD.

## Deferrals and open items

- Business documents were never supplied. Facts come from the build prompt. All prices/tiers will be
  centralised in one constants module in Phase 4 so later reconciliation is a one-file change.

## Demo credentials

| Role | Email | Password |
|---|---|---|
| Family | `family@doordoctor.in` | `Demo@123` |
| Nurse | `nurse@doordoctor.in` | `Demo@123` |
| Admin | `admin@doordoctor.in` | `Demo@123` |
