# PeakStats

Personal Strava analytics dashboard. Sign in with Strava, explore your training history, and surface insights across your activities.

- **Auth:** Sign in with Strava (OAuth 2.0)
- **Backend:** Python FastAPI — exposes a REST API, handles Strava webhooks, talks to Supabase
- **Frontend:** Vite + React + TypeScript SPA
- **Database / Auth:** Supabase (Postgres + Row-Level Security)
- **Deployment:** backend → Render; frontend → Vercel

---

## Repo layout

```
peakstats/
├── backend/            # FastAPI app (Python)
│   ├── app/
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example    # backend env vars (Render)
├── frontend/           # Vite + React + TypeScript SPA
│   ├── src/
│   ├── package.json
│   └── .env.example    # frontend env vars (Vercel)
├── supabase/
│   └── migrations/
│       └── 0001_init.sql
└── docs/
    └── superpowers/
        ├── specs/2026-06-20-peakstats-design.md
        └── plans/2026-06-20-phase1-foundation.md
```

---

## Local development

### Prerequisites

- Python 3.12
- Node 20+
- A Supabase project (or local Supabase CLI stack)
- A Strava API application

Copy and fill in the env files before starting:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

### Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

API available at `http://localhost:8000`.

Run tests:

```bash
cd backend
.venv/bin/python -m pytest
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App available at `http://localhost:5173`.

Run tests:

```bash
# from frontend/
cd frontend
npm test
```

Production build:

```bash
# from frontend/
cd frontend
npm run build
```

---

## Environment variable matrix

All variables are configured via the two `.env.example` files. **Never commit real secret values.**
Set production values in the respective platform dashboards.

| Variable | Platform | Description |
|---|---|---|
| **Backend — [`backend/.env.example`](backend/.env.example)** | | |
| `FRONTEND_ORIGIN` | Render (backend) | Allowed CORS origin — set to the deployed Vercel URL in production (e.g. `https://peakstats.vercel.app`) |
| `SUPABASE_URL` | Render (backend) | Supabase project URL (e.g. `https://<ref>.supabase.co`) |
| `SUPABASE_SERVICE_ROLE_KEY` | Render (backend) | Supabase service-role key — **keep secret, never expose to browser** |
| `STRAVA_CLIENT_ID` | Render (backend) | Strava API application client ID |
| `STRAVA_CLIENT_SECRET` | Render (backend) | Strava API application client secret — **keep secret** |
| `STRAVA_WEBHOOK_VERIFY_TOKEN` | Render (backend) | Token used to verify Strava webhook subscription requests |
| `SESSION_SECRET` | Render (backend) | Secret used to sign server-side sessions — **keep secret** |
| **Frontend — [`frontend/.env.example`](frontend/.env.example)** | | |
| `VITE_API_BASE_URL` | Vercel (frontend, browser-exposed) | Base URL of the backend API (e.g. `https://peakstats-api.onrender.com`) |
| `VITE_SUPABASE_URL` | Vercel (frontend, browser-exposed) | Supabase project URL — same value as backend `SUPABASE_URL` |
| `VITE_SUPABASE_ANON_KEY` | Vercel (frontend, browser-exposed) | Supabase anon (public) key — safe to expose to the browser |

> `VITE_*` variables are bundled into the client-side JavaScript by Vite and are therefore **public**. Never put service-role keys or other secrets in `VITE_*` variables.

---

## Documentation

- [Product design spec](docs/superpowers/specs/2026-06-20-peakstats-design.md)
- [Phase 1 foundation plan](docs/superpowers/plans/2026-06-20-phase1-foundation.md)
