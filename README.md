<h1 align="center">DoorDoctor - Elderly Healthcare Platform (MVP)</h1>

<p align="center">
  <em>Visit &rarr; Vitals &rarr; Threshold Evaluation &rarr; Alert &rarr; Family Visibility &rarr; Coordinator Action</em>
</p>

---

## 1. Project overview

DoorDoctor is a subscription-style elderly healthcare platform built around **scheduled professional
home visits** and **exception-based escalation**. A family member who cannot be physically present can
see exactly what happened during a caregiver's visit, and is alerted when a recorded reading falls
outside the patient's configured monitoring thresholds.

This repository is a **complete, runnable MVP** of that workflow: a FastAPI backend with a real
database, JWT authentication, role-based authorization, a threshold engine, medication adherence
tracking, and a React + TypeScript frontend for all three user roles.

**The core demo story**

```
Coordinator schedules a visit
        │
Caregiver checks in and records vitals
        │
Threshold engine evaluates every reading (synchronously, in the same request)
        │
Out-of-range reading raises an alert + notifications
        │
Family dashboard shows "Attention Required" / "Critical Alert"
        │
Coordinator acknowledges and resolves the alert
```

> **Safety note.** DoorDoctor is a healthcare monitoring and coordination prototype. Alerts indicate
> configured monitoring thresholds and are **not medical diagnoses**. In a real deployment, thresholds
> and escalation procedures must be defined and validated by qualified clinical professionals. All
> data in this repository is fictional.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  React + TypeScript + Vite + Tailwind  (family / caregiver / │
│  coordinator UI, responsive down to 375px)                   │
└───────────────────────────┬─────────────────────────────────┘
                            │  REST + JWT (fetch)
┌───────────────────────────▼─────────────────────────────────┐
│  FastAPI                                                    │
│  routers/  -> HTTP surface, role dependencies               │
│  services/ -> business logic (threshold engine, lifecycle)  │
│  models/   -> SQLAlchemy 2.x ORM                            │
└───────────────────────────┬─────────────────────────────────┘
                            │
                    ┌───────▼────────┐
                    │  SQLite         │
                    └─────────────────┘
```

Request flow for the most important operation:

```
POST /api/v1/visits/{id}/vitals
  -> router validates the payload (Pydantic bounds) and the caregiver's ownership of the visit
  -> visit_service.record_vitals stores the reading
  -> vitals_service.evaluate_thresholds compares it against patient_thresholds
  -> alert_service.create_threshold_alert raises ONE alert listing every breached parameter
  -> notification_service notifies the family member and every coordinator
  -> the caregiver receives the outcome in the same HTTP response
```

Full architecture notes, data model and diagrams: **[DESIGN.md](DESIGN.md)**.

---

## 3. Tech stack

| Layer | Choice |
|---|---|
| Frontend | React 18, TypeScript (strict), Vite, Tailwind CSS, React Router, Recharts |
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.x, Pydantic v2 |
| Database | SQLite |
| Auth | JWT access tokens (PyJWT), bcrypt password hashing |
| Docs | FastAPI OpenAPI / Swagger UI |
| Tests | pytest + FastAPI TestClient (backend), Vitest + Testing Library (frontend) |
| Optional | Docker Compose |

---

## 4. Folder structure

```
DoorDoctor/
├── README.md
├── DESIGN.md
├── docker-compose.yml            # optional one-command startup
├── .env.example
│
├── backend/
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── .env.example
│   ├── app/
│   │   ├── main.py               # FastAPI app, CORS, error shaping
│   │   ├── config.py             # environment configuration
│   │   ├── database.py           # engine, session, Base
│   │   ├── seed.py               # demo reset + seed script
│   │   ├── core/                 # security, dependencies, exceptions
│   │   ├── models/               # SQLAlchemy ORM models
│   │   ├── schemas/              # Pydantic request/response schemas
│   │   ├── routers/              # HTTP endpoints
│   │   └── services/             # business logic (threshold engine, lifecycle, adherence)
│   └── tests/                    # 73 backend tests
│
└── frontend/
    ├── index.html
    ├── tailwind.config.js
    └── src/
        ├── api/                  # authenticated API client, one module per resource
        ├── auth/                 # AuthContext + ProtectedRoute
        ├── components/           # layout, cards, charts, forms, alerts, common
        ├── hooks/                # useAsync (loading / error / data)
        ├── lib/                  # formatting + threshold helpers
        ├── pages/                # family / caregiver / coordinator screens
        ├── test/                 # Vitest tests
        └── types/                # shared API types
```

---

## 5. Prerequisites

- Python **3.11 or newer**
- Node.js **18 or newer** (Node 20 recommended) with npm
- No external services, accounts or API keys are required.

---

## 6. Backend setup

```bash
cd backend

python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env                 # then edit JWT_SECRET
python -m app.seed                   # creates and seeds doordoc.db

uvicorn app.main:app --reload        # http://localhost:8000
```

The API is now at `http://localhost:8000`, Swagger UI at `http://localhost:8000/docs`.

## 7. Frontend setup

In a second terminal:

```bash
cd frontend

npm install
cp .env.example .env                 # VITE_API_BASE_URL=http://localhost:8000/api/v1

npm run dev                          # http://localhost:5173
```

Open **http://localhost:5173** and sign in with a demo account.

---

## 8. Environment variables

`backend/.env`

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./doordoc.db` | SQLAlchemy database URL |
| `JWT_SECRET` | `change-this-in-development` | Signing key for access tokens |
| `JWT_EXPIRE_MINUTES` | `1440` | Access-token lifetime |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allow-list (`*` disables it) |

`frontend/.env`

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | Base URL used by the API client |

`.env` files are git-ignored; `.env.example` files are committed. No secrets are hardcoded.

---

## 9. Database setup

The schema is created automatically on application start (`Base.metadata.create_all`), so no
migration step is needed. The seed script drops and recreates everything for a clean demo.

## 10. Seed / demo reset

```bash
cd backend
python -m app.seed
```

This **resets the demo database** and recreates:

- the three demo accounts,
- patient **Lakshmi D'Souza** (68) linked to the family account,
- caregiver **Anitha Kumar** (RN/ANM, verified),
- three scheduled medications (Amlodipine 5 mg 08:00, Metformin 500 mg 08:00, Atorvastatin 10 mg 20:00),
- four completed historical visits with in-range vitals,
- medication logs producing **87% adherence**,
- the patient's threshold configuration,
- **today's visit left in `scheduled` state** so the live workflow can be demonstrated,
- one future scheduled visit for the coordinator screens.

Run it again at any time to return to a clean demo state.

---

## 11. Demo credentials

| Role | Email | Password |
|---|---|---|
| Family member | `family@doordoc.demo` | `Demo@123` |
| Caregiver | `caregiver@doordoc.demo` | `Demo@123` |
| Care coordinator | `coordinator@doordoc.demo` | `Demo@123` |

The login screen also offers one-click buttons that fill these in.

---

## 12. API documentation

| What | URL |
|---|---|
| Swagger UI | http://localhost:8000/docs |
| OpenAPI JSON | http://localhost:8000/openapi.json |
| Health check | http://localhost:8000/health |

All endpoints live under `/api/v1`. Selected examples:

```http
POST /api/v1/auth/login              { "email": "...", "password": "..." }
GET  /api/v1/auth/me
GET  /api/v1/patients/1/dashboard    # single aggregation for the family dashboard
GET  /api/v1/visits/today
POST /api/v1/visits/1/checkin        { "lat": 12.93, "lng": 77.62 }   # location optional
POST /api/v1/visits/1/vitals         { "systolic_bp": 148, "diastolic_bp": 92, ... }
POST /api/v1/visits/1/medication-logs{ "medication_id": 1, "status": "skipped", "reason": "..." }
POST /api/v1/visits/1/complete
GET  /api/v1/alerts?status=active
POST /api/v1/alerts/1/acknowledge
POST /api/v1/alerts/1/resolve
GET  /api/v1/coordinator/summary
```

Recording out-of-range vitals returns the alert in the same response:

```json
{
  "vitals": { "id": 5, "systolic_bp": 148, "threshold_breached": true, "...": "..." },
  "threshold_breached": true,
  "breached_parameters": [
    { "metric": "systolic_bp", "value": 148, "threshold": 140, "direction": "above", "unit": " mmHg" },
    { "metric": "diastolic_bp", "value": 92, "threshold": 90, "direction": "above", "unit": " mmHg" }
  ],
  "alerts_created": [ { "id": 1, "severity": "critical", "status": "active", "...": "..." } ]
}
```

---

## 13. Running tests

Backend (73 tests covering auth, authorization, visit lifecycle, the threshold engine, medication
adherence and alert handling):

```bash
cd backend
source .venv/bin/activate
pytest
```

Frontend:

```bash
cd frontend
npm test
```

---

## 14. Demo workflow (3-5 minutes)

1. **Sign in as the family member** (`family@doordoc.demo`).
   Lakshmi's dashboard shows her latest vitals, the blood-pressure trend, 87% medication adherence,
   the upcoming visit, her caregiver, and status **Stable**.
2. **Sign out, sign in as the caregiver** (`caregiver@doordoc.demo`).
   Today's assigned visit is listed. Click **Start Visit**, then **Check In**.
3. **Record normal vitals**: `130/80, 82 bpm, 98% SpO2, 110 mg/dL, 98.2 °F, 64 kg`.
   The reading is saved and confirmed as within range - no alert.
4. **Record the demo scenario**: `148/92, 82 bpm, 97% SpO2, 112 mg/dL, 98.2 °F, 64 kg`.
   The screen immediately shows **"Threshold exceeded. An alert has been created for the care team."**
   with both breached parameters (systolic 148 > 140, diastolic 92 > 90) and severity **critical**.
5. **Log medication** - administered / skipped / refused (a reason is required for skipped and
   refused) - then click **Complete Visit**.
6. **Sign in as the family member again.** The dashboard now shows **Critical Alert**, the red
   blood-pressure card, the new reading in the trend chart and history, and a notification badge.
7. **Sign in as the coordinator** (`coordinator@doordoc.demo`).
   The operations dashboard shows the counts, today's visits and the active alert. Open it,
   **Acknowledge**, then **Resolve** - the alert leaves the family dashboard but stays in history.

Try validation too: submit an impossible value (e.g. systolic 400), or skip a dose without a reason -
both are rejected by the backend with a readable message.

---

## 15. MVP limitations

This is a deliberately reduced slice of the production design:

- SQLite, single process, no background workers or message queue.
- Notifications are in-app database records - no SMS, WhatsApp, email or push delivery.
- No payments, subscriptions, corporate/institutional management or NRI features.
- Check-in location is optional and unverified (`demo/unverified` unless the browser provides
  coordinates); there is no geofencing.
- The caregiver app is a responsive web UI, not an offline-first React Native app.
- Dashboards refresh on navigation; only the notification bell polls (every 30s) instead of using
  WebSockets.
- JWT is stored in `localStorage`, which is acceptable for a local academic prototype but not for
  production.
- Timestamps are stored naive in the server's own timezone.
- No PDF reports, hospital/lab/ambulance integrations, wearables, or AI/diagnostic features - by design.

## 16. Production architecture differences

| MVP | Production (per the DoorDoctor SDD) |
|---|---|
| SQLite | PostgreSQL (+ MongoDB event store) |
| Synchronous alert dispatch | Emergency escalation + notification services over SQS/RabbitMQ |
| `notifications` table | FCM push, Twilio SMS/WhatsApp, SendGrid email |
| In-process caching | Redis |
| React responsive caregiver UI | React Native offline-first app (WatermelonDB) |
| Simulated check-in | GPS verification / geofencing |
| REST polling | WebSocket real-time dashboard |
| Demo credentials | OTP + MFA |
| Local process / Docker | AWS ECS/Fargate, S3, CloudWatch |
| Basic logs | Immutable audit log |

## 17. Safety disclaimer

> DoorDoctor is a healthcare monitoring and coordination prototype. Alerts indicate configured
> monitoring thresholds and are not medical diagnoses. In a real deployment, thresholds and escalation
> procedures must be defined and validated by qualified clinical professionals. This project makes no
> claim of regulatory certification, and all patient data included here is fictional.

---

## 18. Troubleshooting

| Symptom | Fix |
|---|---|
| `python3 -m venv` reports `ensurepip is not available` | Debian/Ubuntu ships venv separately: `sudo apt install python3-venv python3-pip`. Alternatively use [uv](https://docs.astral.sh/uv/): `uv venv .venv && uv pip install -r requirements.txt` |
| `Cannot reach the DoorDoctor API` in the UI | The backend is not running, or `frontend/.env` points at the wrong port. Check `curl http://localhost:8000/health` |
| Browser console shows a CORS error | Add the frontend origin to `CORS_ORIGINS` in `backend/.env` and restart the API |
| `Address already in use` on 8000 / 5173 | `uvicorn app.main:app --port 8001` and update `VITE_API_BASE_URL`, or stop the other process |
| Demo data looks stale or half-used | Re-run `python -m app.seed` to reset to a clean demo state |
| Today's visit is missing from the caregiver worklist | Re-seed; the seed always places one `scheduled` visit on the current day |

---

## 19. Optional: Docker

```bash
docker compose up --build
# frontend: http://localhost:5173
# backend:  http://localhost:8000/docs
```

The backend container seeds the demo database on start.
