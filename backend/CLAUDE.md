# Peakstats Backend — CLAUDE.md

FastAPI service deployed to Render. Handles Strava OAuth, token refresh, activity sync,
webhooks, and aggregation endpoints. Talks to Supabase Postgres. The SPA never sees
the Strava client secret — all token handling is server-side.

## Running the service

```bash
cd backend
uvicorn app.main:app --reload        # dev server (port 8000)
pytest                               # run all tests
pytest tests/routers/                # run a subtree
```

## Folder structure

```
backend/
  app/
    main.py          # app factory only — no business logic
    config.py        # pydantic-settings; all env vars live here
    deps.py          # FastAPI dependency injectors (supabase client, current_user, etc.)
    routers/         # HTTP layer — thin; delegates immediately to services
    services/        # Business logic — no FastAPI imports; pure async functions
    models/          # Pydantic I/O schemas (request/response bodies), one file per domain
    db/              # Supabase query functions — typed wrappers, one file per table group
  tests/
    conftest.py      # shared fixtures (TestClient, mock settings, etc.)
    routers/         # mirrors app/routers/
    services/        # mirrors app/services/
    db/              # mirrors app/db/
```

## Architecture rules

**Layering order: routers → services → db. No layer may skip another.**

- `routers/` — parse the request, call one service function, return the response.
  Must not contain business logic or direct DB calls.
- `services/` — all business logic lives here. No `fastapi` imports allowed (use
  plain Python types). Receives dependencies (db client, settings) as arguments.
- `db/` — typed async wrappers around Supabase. One module per logical table group
  (athletes, activities, segments, tokens). No business logic.
- `models/` — Pydantic schemas for request/response bodies. Keep separate from DB
  row shapes (those live in `db/`).
- `deps.py` — all FastAPI `Depends()` callables. This is the only place that calls
  `get_settings()` at request time.
- `config.py` — `get_settings()` cached with `@lru_cache`. Add every new env var here
  first; never read `os.environ` directly elsewhere.

## Coding conventions

- **Type annotations on every public function** — parameters and return type.
- **Async when you `await`** — use `async def` only when the function calls `await`
  (Supabase query, httpx request to Strava). Use plain `def` otherwise; FastAPI runs
  sync handlers in a thread pool so they don't block the event loop. Mixing `async def`
  with synchronous blocking I/O is worse than using plain `def`.
- **Pydantic for all I/O boundaries** — router request bodies, router response models,
  and Settings. Do not pass raw dicts across layer boundaries.
- **No secrets in code** — all credentials come from `Settings`; never hardcode or
  log token values.
- **One router per domain** — `auth.py`, `athletes.py`, `activities.py`,
  `segments.py`, `webhooks.py`. Register all routers in `main.py`.
- **Prefix routes at registration** — e.g. `include_router(activities.router, prefix="/activities")`.
  Individual route functions use relative paths (`@router.get("/{id}")`).
- **HTTP exceptions in routers only** — services raise plain Python exceptions
  (`ValueError`, custom domain errors); routers translate them to `HTTPException`.

## Testing conventions

- Test file location mirrors source: `app/routers/auth.py` → `tests/routers/test_auth.py`.
- All tests go through `TestClient` via the `client` fixture in `conftest.py`.
  Never instantiate `create_app()` directly in a test.
- Patch at the service boundary — mock `services.*` functions, not internal DB calls,
  so tests stay decoupled from Supabase.
- Each test file imports only from `fastapi.testclient` and the module under test.
  No cross-domain imports between test files.

## Adding a new feature

1. Add the Pydantic schema(s) to `models/<domain>.py`.
2. Add typed DB query functions to `db/<domain>.py`.
3. Add business logic to `services/<domain>.py`; inject DB functions as parameters.
4. Add a router to `routers/<domain>.py`; register it in `main.py`.
5. Add tests mirroring each layer above.
6. Add any new env vars to `config.py` and `.env.example`.

## Environment variables

All vars are in `app/config.py` (`Settings`) and documented in `.env.example`.
Render reads them from the dashboard; locally, copy `.env.example` to `.env`.

| Variable | Purpose |
|---|---|
| `FRONTEND_ORIGIN` | Allowed CORS origin for the SPA |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Service-role key (server-only; never expose to client) |
| `STRAVA_CLIENT_ID` | Strava app client ID |
| `STRAVA_CLIENT_SECRET` | Strava app secret (server-only) |
| `STRAVA_WEBHOOK_VERIFY_TOKEN` | Token used to verify Strava webhook subscription |
| `SESSION_SECRET` | Secret for signing session tokens |

## Deployment

Deployed via `render.yaml` at the repo root. Build: `pip install -r requirements.txt`.
Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
Health check: `GET /health`.

Do not change `render.yaml` without updating the Render dashboard env vars to match.
