# Phase 1 — Global terminology refactor

**Goal:** `caregiver` → `nurse`, `coordinator` → `admin`, everywhere. Every later phase references
these names, so nothing else can start until this is clean.

**Measured scope:** ~700 occurrences across 50 tracked files.

| Old | New |
|---|---|
| `caregiver` / `Caregiver` / `CAREGIVER` | `nurse` / `Nurse` / `NURSE` |
| `coordinator` / `Coordinator` / `COORDINATOR` | `admin` / `Admin` / `ADMIN` |
| "Care Coordinator" / "Care coordinator" | "Admin" |

## Method

An ordered, case-preserving substitution applied per file by a one-off script in the scratchpad —
not 50 hand edits, and not a blind `sed`. Order matters so the compound phrase resolves before the
bare word:

1. `Care Coordinator` / `Care coordinator` / `care coordinator` → `Admin` / `Admin` / `admin`
2. `CAREGIVER` → `NURSE` · `COORDINATOR` → `ADMIN`
3. `Caregiver` → `Nurse` · `Coordinator` → `Admin`
4. `caregiver` → `nurse` · `coordinator` → `admin`

Compound identifiers resolve for free: `caregiver_profile`→`nurse_profile`,
`CaregiverStatus`→`NurseStatus`, `coordinator_service`→`admin_service`,
`CoordinatorSummary`→`AdminSummary`, `caregivers`→`nurses`,
`require_family_or_coordinator`→`require_family_or_admin`, `authorize_caregiver_visit`→
`authorize_nurse_visit`.

Untouched by design: `location_source = "demo/unverified"`, and the standalone word "care"
("care team", "healthcare", "Care at home").

Then `git mv` for paths → hand-write the prose files → grep audit → seed → tests.

## Step 1 — Path renames (`git mv`, preserves history)

### Backend
| From | To |
|---|---|
| `backend/app/models/caregiver.py` | `backend/app/models/nurse.py` |
| `backend/app/routers/coordinator.py` | `backend/app/routers/admin.py` |
| `backend/app/services/coordinator_service.py` | `backend/app/services/admin_service.py` |
| `backend/app/schemas/coordinator.py` | `backend/app/schemas/admin.py` |

### Frontend
| From | To |
|---|---|
| `frontend/src/pages/caregiver/CaregiverVisits.tsx` | `frontend/src/pages/nurse/NurseVisits.tsx` |
| `frontend/src/pages/caregiver/CaregiverVisitDetail.tsx` | `frontend/src/pages/nurse/NurseVisitDetail.tsx` |
| `frontend/src/pages/coordinator/CoordinatorDashboard.tsx` | `frontend/src/pages/admin/AdminDashboard.tsx` |
| `frontend/src/pages/coordinator/CoordinatorPatients.tsx` | `frontend/src/pages/admin/AdminPatients.tsx` |
| `frontend/src/pages/coordinator/CoordinatorCaregivers.tsx` | `frontend/src/pages/admin/AdminNurses.tsx` |
| `frontend/src/pages/coordinator/CoordinatorVisits.tsx` | `frontend/src/pages/admin/AdminVisits.tsx` |
| `frontend/src/pages/coordinator/CoordinatorAlerts.tsx` | `frontend/src/pages/admin/AdminAlerts.tsx` |
| `frontend/src/api/coordinator.ts` | `frontend/src/api/admin.ts` |

## Step 2 — Backend symbols

- **`models/enums.py`** — `UserRole.NURSE = "nurse"`, `UserRole.ADMIN = "admin"`, `class NurseStatus`.
- **`models/nurse.py`** — `class Nurse`, `__tablename__ = "nurses"`, back-refs `nurse_profile` / `nurse`.
- **`models/user.py`** — `nurse_profile: Mapped[Optional["Nurse"]]`, docstring.
- **`models/visit.py`** — `nurse_id` with FK `"nurses.id"`, relationship `nurse`.
- **`models/__init__.py`** — imports and `__all__`.
- **`core/dependencies.py`** — `require_nurse`, `require_admin`, `require_family_or_admin`,
  `NurseUser`, `AdminUser`, `get_nurse_profile`, `_nurse_has_patient_access`, `authorize_nurse_visit`.
- **`routers/admin.py`** — `/admin/summary`, `/nurses`, `tags=["admin"]`.
- **`routers/visits.py`** — `AdminUser`, `authorize_nurse_visit`, `nurse_id`, `assign_nurse`, summaries.
- **`routers/patients.py`** — role checks and forbidden messages.
- **`routers/alerts.py`** — `AdminUser`, `Nurse`, payload key `nurse_name`.
- **`schemas/admin.py`** — `AdminSummary { nurses: int }`.
- **`schemas/visit.py`** — `nurse_id`, `nurse`.
- **`schemas/patient.py`** — `NurseOut`, `DashboardOut.nurse`.
- **`schemas/alert.py`** — `nurse_name`.
- **`services/admin_service.py`** — `list_nurses`, summary key `"nurses"`.
- **`services/visit_service.py`** — `assign_nurse`, `ensure_nurse_can_edit`, `include_nurse=`,
  payload key `"nurse"`, `"Nurse not found."`.
- **`services/dashboard_service.py`** — `_serialize_nurse`, keys `nurse` / `nurse_id` / `nurse_name`.
- **`services/alert_service.py`**, **`services/notification_service.py`** — role enums, `admin_ids`.
- **`main.py`** — `admin.router`, reworded `DESCRIPTION`.
- **`seed.py`** — emails `family@doordoctor.in` / `nurse@doordoctor.in` / `admin@doordoctor.in`.

## Step 3 — Backend tests

- **`tests/conftest.py`** — `FAMILY_EMAIL` / `NURSE_EMAIL` / `ADMIN_EMAIL` on `@doordoctor.in`;
  fixtures `nurse_headers`, `admin_headers`; `other_family` → `other-family@doordoctor.in`.
- **`tests/test_{alerts,auth,authorization,medications,visits,vitals}.py`** — fixture names, paths
  `/admin/summary` and `/nurses`, JSON keys `nurse_id` / `nurses`.

## Step 4 — Frontend symbols

- **`types/index.ts`** — `Role = 'family' | 'nurse' | 'admin'`; `interface Nurse`; `Visit.nurse_id` /
  `nurse` / `nurse_name`; `Dashboard.nurse`; `AdminSummary { nurses }`; `AlertDetail.nurse_name`.
- **`api/admin.ts`** — `adminApi`, `/admin/summary`, `/nurses`.
- **`api/visits.ts`** — `create({ nurse_id })`, `assign(visitId, nurseId)`.
- **`App.tsx`** — routes `/nurse/*`, `/admin/*`; `allow={['nurse']}` / `allow={['admin']}`.
- **`auth/AuthContext.tsx`** — `ROLE_HOME = { family: '/family/dashboard', nurse: '/nurse/visits', admin: '/admin/dashboard' }`.
- **`components/layout/AppShell.tsx`** — `NAV_BY_ROLE`, nav item "Nurses",
  `ROLE_LABELS = { family: 'Family Member', nurse: 'Nurse', admin: 'Admin' }`.
- **`components/cards/VisitCard.tsx`**, **`charts/VitalsTrendChart.tsx`**,
  **`forms/ScheduleVisitForm.tsx`** — props, labels, payload keys.
- **`pages/Login.tsx`** — demo account emails and labels.
- **`pages/{family,nurse,admin}/*`** — data keys and visible strings.

## Step 5 — Prose written by hand, not substituted

The mechanical rule produces bad English in five places:

| File | Fix |
|---|---|
| `pages/family/FamilyAlerts.tsx` | "Your care coordinator reviews and resolves alerts" → **"Your DoorDoctor care team reviews and resolves alerts."** — "your admin" is wrong to say to a family member |
| `pages/family/FamilyDashboard.tsx` | "Ask a coordinator to link a patient" → "Ask DoorDoctor to link a patient." |
| `main.py` `DESCRIPTION` | Reword the workflow sentence around "nurse visit" / "admin action" |
| `DESIGN.md` | Mermaid node `Coordinator[Care Coordinator]` → `Admin[Admin]` |
| `README.md` §11 | Demo credentials table |

## Step 6 — Housekeeping

- `.env.example` — fix the stray `ju` typo on line 1 (pre-existing uncommitted edit).
- `backend/doordoc.db` — stale after the table rename; re-seed. No migration needed: `seed.py`
  drops and recreates the schema. Alembic arrives in Phase 11.

## Acceptance

```bash
grep -rin "caregiver\|coordinator" --include='*.py' --include='*.ts' --include='*.tsx' \
  --include='*.md' --include='*.js' --include='*.json' . | grep -v node_modules   # → 0 hits
cd backend && .venv/bin/python -m app.seed        # runs clean
cd backend && .venv/bin/python -m pytest          # 73 passed
cd frontend && npx tsc -b --noEmit && npm test    # clean
```

Plus: each demo account signs in and lands on its role home (`/family/dashboard`, `/nurse/visits`,
`/admin/dashboard`).

**Commit:** `refactor: rename caregiver→nurse and coordinator→admin across the platform`
