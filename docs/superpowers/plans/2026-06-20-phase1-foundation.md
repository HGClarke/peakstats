# Peakstats Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the deployable skeletons — a Vite + React frontend on Vercel, a FastAPI backend on Render, and a Supabase Postgres schema with RLS — so later phases have a working, wired foundation to build features into.

**Architecture:** Two services in one repo (`frontend/` Vite SPA, `backend/` FastAPI), backed by Supabase Postgres. Phase 1 ships no product features — it proves each piece builds, tests, deploys, and that the three platforms can talk to each other via configured env/secrets. Each task is an independent vertical slice with its own verification.

**Tech Stack:** Vite + React + TypeScript + Vitest (frontend); Python 3.12 + FastAPI + uvicorn + pytest + httpx (backend); Supabase Postgres + RLS; Vercel + Render for deploys.

## Global Constraints

- Python 3.12; Node 20+ (dev machine has 25).
- Data stored **metric**; no conversion server-side (relevant to later phases; schema columns use metric units).
- Strava client secret + Supabase service-role key live **only** on the backend (Render). Frontend gets only the Supabase anon key + API base URL.
- All tables have **RLS enabled**; an athlete may read only their own rows. `strava_tokens` denies all client access.
- Spec of record: `docs/superpowers/specs/2026-06-20-peakstats-design.md`.
- Frequent commits: each task ends in a commit. TDD where behavior exists.

---

## File Structure

**Backend (`backend/`)**
- `app/__init__.py` — package marker.
- `app/main.py` — FastAPI app factory, CORS, route registration.
- `app/config.py` — settings loaded from env (pydantic-settings).
- `app/routers/health.py` — `GET /health`.
- `tests/conftest.py` — pytest fixtures (TestClient).
- `tests/test_health.py` — health endpoint test.
- `requirements.txt` — runtime + test deps.
- `.env.example` — documented env var names (no values).
- `render.yaml` — Render service definition.
- `.gitignore` — Python ignores.

**Frontend (`frontend/`)** — scaffolded by Vite (`react-ts` template), then:
- `src/App.tsx` — placeholder landing shell.
- `src/lib/config.ts` — reads `import.meta.env` values.
- `src/App.test.tsx` — Vitest smoke test.
- `vitest.config.ts` / `vite.config.ts` — build + test config.
- `.env.example` — documented `VITE_*` var names.
- `vercel.json` — SPA rewrite config.

**Database (`supabase/`)**
- `supabase/migrations/0001_init.sql` — tables + RLS policies.

---

## Task 1: Backend FastAPI skeleton with health check

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/health.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_health.py`
- Create: `backend/.gitignore`

**Interfaces:**
- Produces: `app.main.create_app() -> FastAPI` — app factory used by tests and uvicorn. `GET /health` returns `{"status": "ok"}` with HTTP 200.

- [ ] **Step 1: Create requirements.txt**

```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic-settings==2.7.1
httpx==0.28.1
pytest==8.3.4
```

- [ ] **Step 2: Create the Python .gitignore**

`backend/.gitignore`:
```text
__pycache__/
*.pyc
.venv/
.env
.pytest_cache/
```

- [ ] **Step 3: Create a venv and install deps**

Run:
```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```
Expected: installs without error.

- [ ] **Step 4: Create package + router files (empty package markers)**

`backend/app/__init__.py`: empty.
`backend/app/routers/__init__.py`: empty.
`backend/tests/__init__.py`: empty.

- [ ] **Step 5: Write the failing test**

`backend/tests/conftest.py`:
```python
import pytest
from fastapi.testclient import TestClient
from app.main import create_app


@pytest.fixture
def client():
    return TestClient(create_app())
```

`backend/tests/test_health.py`:
```python
def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'` (or import error).

- [ ] **Step 7: Implement the health router**

`backend/app/routers/health.py`:
```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 8: Implement the app factory**

`backend/app/main.py`:
```python
from fastapi import FastAPI

from app.routers import health


def create_app() -> FastAPI:
    app = FastAPI(title="Peakstats API")
    app.include_router(health.router)
    return app


app = create_app()
```

- [ ] **Step 9: Run the test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_health.py -v`
Expected: PASS.

- [ ] **Step 10: Verify the server boots locally**

Run: `cd backend && .venv/bin/uvicorn app.main:app --port 8000 &` then `curl -s localhost:8000/health`
Expected: `{"status":"ok"}`. Then `kill %1`.

- [ ] **Step 11: Commit**

```bash
git add backend/ && git commit -m "feat(backend): FastAPI skeleton with /health"
```

---

## Task 2: Backend config + CORS

**Files:**
- Create: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Create: `backend/.env.example`
- Test: `backend/tests/test_cors.py`

**Interfaces:**
- Consumes: `app.main.create_app()` from Task 1.
- Produces: `app.config.Settings` (pydantic-settings) with fields `frontend_origin: str = "http://localhost:5173"`, `supabase_url: str = ""`, `supabase_service_role_key: str = ""`, `strava_client_id: str = ""`, `strava_client_secret: str = ""`, `strava_webhook_verify_token: str = ""`, `session_secret: str = ""`. `app.config.get_settings() -> Settings` (cached).

- [ ] **Step 1: Add pydantic-settings to requirements**

Append to `backend/requirements.txt` — already present? It is (Step from Task 1). No change needed; confirm `pydantic-settings==2.7.1` is listed.

- [ ] **Step 2: Write the failing CORS test**

`backend/tests/test_cors.py`:
```python
def test_cors_allows_frontend_origin(client):
    resp = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_cors.py -v`
Expected: FAIL — no `access-control-allow-origin` header.

- [ ] **Step 4: Implement config**

`backend/app/config.py`:
```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    frontend_origin: str = "http://localhost:5173"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_webhook_verify_token: str = ""
    session_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Wire CORS into the app factory**

Replace `backend/app/main.py` contents:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import health


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Peakstats API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    return app


app = create_app()
```

- [ ] **Step 6: Run all backend tests**

Run: `cd backend && .venv/bin/python -m pytest -v`
Expected: PASS (health + cors).

- [ ] **Step 7: Create .env.example**

`backend/.env.example`:
```text
# Backend (Render) — set real values in the Render dashboard
FRONTEND_ORIGIN=http://localhost:5173
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=
STRAVA_WEBHOOK_VERIFY_TOKEN=
SESSION_SECRET=
```

- [ ] **Step 8: Commit**

```bash
git add backend/ && git commit -m "feat(backend): settings config and CORS"
```

---

## Task 3: Render deploy definition

**Files:**
- Create: `backend/render.yaml`

**Interfaces:**
- Consumes: `backend/requirements.txt`, `app.main:app` from Tasks 1–2.
- Produces: a deployable Render web service spec. No code interface.

- [ ] **Step 1: Create render.yaml**

`backend/render.yaml`:
```yaml
services:
  - type: web
    name: peakstats-api
    runtime: python
    rootDir: backend
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    envVars:
      - key: FRONTEND_ORIGIN
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SERVICE_ROLE_KEY
        sync: false
      - key: STRAVA_CLIENT_ID
        sync: false
      - key: STRAVA_CLIENT_SECRET
        sync: false
      - key: STRAVA_WEBHOOK_VERIFY_TOKEN
        sync: false
      - key: SESSION_SECRET
        sync: false
```

- [ ] **Step 2: Create the Render service**

Use the Render MCP `create_web_service` with the settings above (runtime python, rootDir `backend`, build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health check `/health`), connected to this repo. If the repo is not yet on GitHub, push it first (`gh repo create` / `git push`), then create the service.

- [ ] **Step 3: Set backend env vars on Render**

Use the Render MCP `update_environment_variables` to set `FRONTEND_ORIGIN`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_WEBHOOK_VERIFY_TOKEN`, `SESSION_SECRET`. Use placeholders for any Strava values not yet available; real Supabase values come from Task 6.

- [ ] **Step 4: Verify the deploy is live**

Run: `curl -s https://peakstats-api.onrender.com/health` (substitute the actual Render URL).
Expected: `{"status":"ok"}`. Confirm via Render MCP `get_deploy` that the latest deploy status is `live`.

- [ ] **Step 5: Commit**

```bash
git add backend/render.yaml && git commit -m "chore(backend): Render service definition"
```

---

## Task 4: Frontend Vite + React skeleton with smoke test

**Files:**
- Create (via scaffold): `frontend/*` (Vite `react-ts` template).
- Create: `frontend/src/lib/config.ts`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/App.test.tsx`
- Modify: `frontend/vite.config.ts`
- Create: `frontend/.env.example`

**Interfaces:**
- Produces: `config` object from `src/lib/config.ts` with `apiBaseUrl: string`, `supabaseUrl: string`, `supabaseAnonKey: string`, read from `import.meta.env`.

- [ ] **Step 1: Scaffold Vite into the existing frontend dir**

Run:
```bash
cd frontend && npm create vite@latest . -- --template react-ts
npm install
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
```
Expected: scaffolds files; if prompted about the non-empty dir, choose "Ignore files and continue".

- [ ] **Step 2: Configure Vitest in vite.config.ts**

Replace `frontend/vite.config.ts`:
```typescript
/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
  },
});
```

`frontend/src/setupTests.ts`:
```typescript
import "@testing-library/jest-dom";
```

- [ ] **Step 3: Add the test script**

In `frontend/package.json` "scripts", add: `"test": "vitest run"`.

- [ ] **Step 4: Write the failing smoke test**

`frontend/src/App.test.tsx`:
```typescript
import { render, screen } from "@testing-library/react";
import App from "./App";

test("renders the peakstats wordmark", () => {
  render(<App />);
  expect(screen.getByText(/peakstats/i)).toBeInTheDocument();
});
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL — default App has no "peakstats" text.

- [ ] **Step 6: Implement the config module**

`frontend/src/lib/config.ts`:
```typescript
export const config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  supabaseUrl: import.meta.env.VITE_SUPABASE_URL ?? "",
  supabaseAnonKey: import.meta.env.VITE_SUPABASE_ANON_KEY ?? "",
};
```

- [ ] **Step 7: Replace App.tsx with a placeholder shell**

`frontend/src/App.tsx`:
```typescript
function App() {
  return (
    <main style={{ fontFamily: "sans-serif", padding: 24 }}>
      <h1>peakstats</h1>
      <p>Ride analytics — coming soon.</p>
    </main>
  );
}

export default App;
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `cd frontend && npm test`
Expected: PASS.

- [ ] **Step 9: Verify the production build succeeds**

Run: `cd frontend && npm run build`
Expected: build completes, `dist/` produced.

- [ ] **Step 10: Create .env.example**

`frontend/.env.example`:
```text
# Frontend (Vercel) — VITE_ vars are exposed to the browser
VITE_API_BASE_URL=http://localhost:8000
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
```

- [ ] **Step 11: Commit**

```bash
git add frontend/ && git commit -m "feat(frontend): Vite + React skeleton with smoke test"
```

---

## Task 5: Vercel deploy definition

**Files:**
- Create: `frontend/vercel.json`

**Interfaces:**
- Consumes: the frontend build from Task 4.
- Produces: SPA deploy config. No code interface.

- [ ] **Step 1: Create vercel.json**

`frontend/vercel.json`:
```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

- [ ] **Step 2: Create the Vercel project**

In the Vercel dashboard (or `vercel` CLI), import the repo, set **Root Directory** to `frontend`, framework preset **Vite**. (No Vercel MCP is available — this step is manual.)

- [ ] **Step 3: Set frontend env vars on Vercel**

Set `VITE_API_BASE_URL` to the Render URL from Task 3, and `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` to the Supabase values from Task 6 (Production scope).

- [ ] **Step 4: Verify the deploy is live**

Run: `curl -s https://<your-vercel-domain>/ | grep -i peakstats`
Expected: the served HTML references the app (title/root div). Confirm the page renders in a browser.

- [ ] **Step 5: Update backend FRONTEND_ORIGIN**

Set `FRONTEND_ORIGIN` on Render (Render MCP `update_environment_variables`) to the Vercel production domain so CORS allows it. Redeploy backend; re-run `curl` from Task 3 Step 4 to confirm still `live`.

- [ ] **Step 6: Commit**

```bash
git add frontend/vercel.json && git commit -m "chore(frontend): Vercel SPA deploy config"
```

---

## Task 6: Supabase schema + RLS migration

**Files:**
- Create: `supabase/migrations/0001_init.sql`

**Interfaces:**
- Produces: tables `athletes`, `strava_tokens`, `activities`, `segments`, `segment_efforts`, `sync_state` with RLS enabled, per the spec data model. Later phases write/read these.

- [ ] **Step 1: Write the migration SQL**

`supabase/migrations/0001_init.sql`:
```sql
-- Athletes (PK = Strava athlete id)
create table athletes (
  id bigint primary key,
  name text not null,
  avatar_url text,
  settings jsonb not null default '{"units":"metric","theme":"dark","default_period":"week"}',
  created_at timestamptz not null default now()
);

-- Strava OAuth tokens (server-only; no client policies => RLS denies all client access)
create table strava_tokens (
  athlete_id bigint primary key references athletes(id) on delete cascade,
  access_token text not null,
  refresh_token text not null,
  expires_at timestamptz not null
);

-- Activities (PK = Strava activity id). Stored metric.
create table activities (
  id bigint primary key,
  athlete_id bigint not null references athletes(id) on delete cascade,
  name text not null,
  type text not null,
  start_date timestamptz not null,
  distance_m double precision not null,
  moving_time_s integer not null,
  elapsed_time_s integer not null,
  elev_gain_m double precision not null default 0,
  avg_speed_ms double precision,
  avg_hr integer,
  calories integer,
  summary_polyline text,
  splits_metric jsonb,
  detail_fetched_at timestamptz,
  is_pr boolean not null default false
);
create index activities_athlete_date_idx on activities (athlete_id, start_date desc);

create table segments (
  id bigint primary key,
  name text not null,
  distance_m double precision not null,
  avg_grade double precision not null default 0
);

create table segment_efforts (
  id bigint primary key,
  segment_id bigint not null references segments(id) on delete cascade,
  athlete_id bigint not null references athletes(id) on delete cascade,
  activity_id bigint not null references activities(id) on delete cascade,
  elapsed_time_s integer not null,
  avg_watts double precision,
  avg_hr integer,
  avg_speed_ms double precision,
  start_date timestamptz not null,
  is_best boolean not null default false
);
create index segment_efforts_athlete_segment_idx on segment_efforts (athlete_id, segment_id);
create index segment_efforts_activity_idx on segment_efforts (activity_id);

create table sync_state (
  athlete_id bigint primary key references athletes(id) on delete cascade,
  status text not null default 'idle',
  progress integer not null default 0,
  last_backfill_at timestamptz,
  last_sync_at timestamptz,
  last_webhook_event_id bigint
);

-- Enable RLS on every table
alter table athletes enable row level security;
alter table strava_tokens enable row level security;
alter table activities enable row level security;
alter table segments enable row level security;
alter table segment_efforts enable row level security;
alter table sync_state enable row level security;

-- Athlete-scoped read policies. auth.jwt() carries the Strava athlete id under
-- the custom claim "athlete_id" (set when the backend mints the session in Phase 2).
create policy athlete_self_read on athletes
  for select using (id = (auth.jwt() ->> 'athlete_id')::bigint);

create policy activities_self_read on activities
  for select using (athlete_id = (auth.jwt() ->> 'athlete_id')::bigint);

create policy segment_efforts_self_read on segment_efforts
  for select using (athlete_id = (auth.jwt() ->> 'athlete_id')::bigint);

create policy sync_state_self_read on sync_state
  for select using (athlete_id = (auth.jwt() ->> 'athlete_id')::bigint);

-- segments is shared reference data: readable by any authenticated athlete.
create policy segments_authenticated_read on segments
  for select using ((auth.jwt() ->> 'athlete_id') is not null);

-- No policies on strava_tokens => all client access denied. The backend uses the
-- service-role key (bypasses RLS) for all writes and token reads.
```

- [ ] **Step 2: Apply the migration**

Apply via the Supabase MCP `apply_migration` (name `0001_init`, the SQL above) against the project. (Alternatively `supabase db push` if the CLI is linked.)

- [ ] **Step 3: Verify tables exist**

Use Supabase MCP `list_tables` (schema `public`).
Expected: all six tables present.

- [ ] **Step 4: Verify RLS is enabled everywhere**

Use Supabase MCP `execute_sql`:
```sql
select relname, relrowsecurity
from pg_class
where relname in ('athletes','strava_tokens','activities','segments','segment_efforts','sync_state');
```
Expected: `relrowsecurity = true` for all six rows.

- [ ] **Step 5: Check security advisors**

Use Supabase MCP `get_advisors` (type `security`).
Expected: no error-level findings about missing RLS on these tables. Note any warnings for follow-up.

- [ ] **Step 6: Capture Supabase connection values**

Use Supabase MCP `get_project_url` and `get_publishable_keys` (anon key). Record the URL + anon key for the frontend env (Task 5 Step 3) and the URL + service-role key (from the Supabase dashboard) for the backend env (Task 3 Step 3).

- [ ] **Step 7: Commit**

```bash
git add supabase/migrations/0001_init.sql && git commit -m "feat(db): initial schema with RLS"
```

---

## Task 7: Root README + env wiring doc

**Files:**
- Create: `README.md`
- Modify: `.gitignore`

**Interfaces:** none (documentation).

- [ ] **Step 1: Extend root .gitignore**

`.gitignore`:
```text
# Python
backend/.venv/
backend/__pycache__/
**/__pycache__/
*.pyc
backend/.pytest_cache/

# Node
frontend/node_modules/
frontend/dist/

# Env
.env
**/.env
!**/.env.example
```

- [ ] **Step 2: Write the README**

`README.md` covering: project summary; repo layout (`frontend/`, `backend/`, `supabase/`); local dev commands (`backend`: venv + `uvicorn app.main:app`; `frontend`: `npm install` + `npm run dev`); the full env var matrix (which vars live on Vercel vs Render vs local `.env`, pointing at the two `.env.example` files); and links to the spec and this plan.

- [ ] **Step 3: Verify the env matrix is complete**

Cross-check the README env matrix against `backend/.env.example` and `frontend/.env.example`.
Expected: every variable in both example files appears in the README, with its platform noted.

- [ ] **Step 4: Commit**

```bash
git add README.md .gitignore && git commit -m "docs: root README and env wiring"
```

---

## Phase 1 Done — Definition of Done

- Backend `pytest` green; `/health` live on Render.
- Frontend `npm test` + `npm run build` green; placeholder app live on Vercel.
- All six tables exist in Supabase with RLS enabled; security advisors clean.
- Env/secrets set on Render + Vercel; CORS allows the Vercel origin; frontend points at the Render API.
- Spec coverage: Phase 1 items 1.1–1.4 from the design spec are all implemented.

Phase 2 (Auth) gets its own plan, written when Phase 1 is verified.
