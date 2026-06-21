# Migrate the db layer to the Supabase Python client

**Date:** 2026-06-21
**Status:** Approved (design)
**Area:** `backend/`

## Goal

Replace the hand-rolled httpx + PostgREST calls in the backend db layer with the
official `supabase` Python client, while keeping the service synchronous and
improving the many-concurrent-users story by sharing a single client instance for
the lifetime of the app.

## Background

The current db layer (`app/db/*`) issues raw PostgREST requests through a
short-lived `httpx.Client` that is rebuilt and torn down on every request
(`deps.get_supabase`) and inside every background task
(`services/sync.py`, `services/webhooks.py`). Rebuilding the client per request
means a fresh connection pool and TLS handshake to Supabase on every call — the
main weak spot under load.

The official `supabase` package ships a **synchronous** client
(`create_client` → `SyncPostgrestClient`) whose internals use a synchronous
`httpx.Client`, so it matches the existing execution model. Verified against
current supabase-py docs: it supports every operation the db layer needs —
`eq`/`gte`/`lte`/`ilike`, `order(desc=)`, `range`/`limit`/`offset`,
`upsert(on_conflict=...)` (merges by default), `delete`, and `count="exact"`
(which replaces the manual `Content-Range` header parsing).

## Decision: stay synchronous

Async conversion is **not** required and is explicitly out of scope.

- Handlers are already sync `def`; FastAPI runs them in a worker threadpool, so
  they don't block the event loop. Many users are served by that threadpool plus
  multiple uvicorn workers; the bottleneck is network/Supabase, not the GIL.
- Going async would force `async def` + `await` through every db function,
  service, router, and background task for negligible throughput gain on a
  network-bound app.
- The supabase sync client uses a synchronous `httpx.Client` internally — the
  same model in place today.

## Decision: shared singleton client

The real scalability lever is connection reuse, not async. A single supabase
client is created once at startup and reused across all requests and background
tasks, giving connection pooling and keep-alive (no per-request TLS handshake).

This is safe because the app uses a single service-role key and never mutates
per-request auth on the client. **Constraint:** do not introduce per-request
`.auth(jwt)` swapping on the shared client without revisiting thread-safety.

## Scope

**In scope**

- `app/db/*` — athletes, tokens, activities, sync_state
- `app/clients.py` — `build_supabase`
- `app/deps.py` — `get_supabase`
- `app/main.py` — add a FastAPI lifespan that owns the shared client
- `app/services/sync.py`, `app/services/webhooks.py` — background tasks receive
  the shared client instead of building their own
- `app/routers/sync.py`, `app/routers/webhooks.py` — wire the shared client into
  the background tasks / in-request refresh
- tests (db, clients, services)
- `requirements.txt`, `requirements-dev.txt`
- `backend/CLAUDE.md`

**Out of scope**

- The Strava client stays on httpx (`build_strava`, `StravaClient` untouched).
- No database schema changes.
- No async/await conversion.

## Design

### Dependencies

- `requirements.txt`: add `supabase` (pinned 2.x). Keep `httpx` (still used by the
  Strava client and transitively by supabase).
- `requirements-dev.txt`: add `respx` (pinned) for db-layer tests.

### Client lifecycle — shared singleton

- `clients.build_supabase(settings) -> Client` returns
  `create_client(settings.supabase_url, settings.supabase_service_role_key,
  options=ClientOptions(postgrest_client_timeout=10))`. `create_client` performs
  no network I/O, so it is safe to call at startup.
- `main.create_app`: add a FastAPI lifespan context manager that builds the client
  on startup, stores it on `app.state.supabase`, and closes it on shutdown.
- `deps.get_supabase(request) -> Client`: return `request.app.state.supabase`
  (no per-request build/close). Return type changes from
  `Iterator[httpx.Client]` to `Client`.

### db layer

Each function keeps its name, signature shape, and return type; only the param
type (`client: Client`) and the call mechanics change. Behavior is preserved.

- **upserts** → `client.table(t).upsert(rows, on_conflict="...").execute()`
  (default merge matches `resolution=merge-duplicates`). Keep the empty-list
  short-circuit in `upsert_activities`.
- **single / list selects** →
  `.select("*").eq(...).gte(...)/.ilike(...).order(col, desc=?).limit()/.range()`;
  `get_*` return `data[0] if data else None`.
- **counts** (`count_activities`, total in `list_activities_filtered`) →
  `.select(..., count="exact")` then `resp.count`. Delete `_parse_total` and the
  manual `Content-Range` parsing.
- **deletes** → `.delete().eq(...).execute()`.
- TypedDict row shapes (`ActivityRow`, `AthleteRow`, `TokenRow`,
  `SyncStateRow`) stay; cast `resp.data` to them as today.

### Background-task services

- `services/sync.py`: `run_backfill` and `refresh` stop calling `build_supabase`
  and stop closing it; they receive `supabase: Client` as a parameter. They still
  build and close the Strava client from `settings`.
- `services/webhooks.py`: `process_event` likewise receives `supabase: Client`.

### Router wiring

- `/sync/start`: pass the injected `supabase` into
  `background_tasks.add_task(run_backfill, supabase, settings, athlete_id)`.
- `/sync/refresh`: add `supabase = Depends(get_supabase)` and call
  `refresh(supabase, settings, athlete_id)` (this runs in-request, not as a
  background task).
- `/webhooks/strava` POST: add `supabase = Depends(get_supabase)` and pass it into
  `process_event`.

## Error handling

DB errors become postgrest `APIError` instead of `httpx.HTTPStatusError`.

- Background tasks already catch broad `Exception` and log, so they are
  unaffected.
- The `None`-on-empty semantics of `get_athlete` / `get_tokens` /
  `get_sync_state` key off `resp.data` being empty, not off HTTP errors, so they
  are preserved.
- During implementation, grep for any explicit `httpx` / `raise_for_status`
  handling around DB calls and update it.

## Testing strategy

- `tests/db/*`: rewrite on `respx` — intercept the outgoing PostgREST request and
  assert method / path / query params / body / `Prefer` header, returning canned
  JSON. For count tests, return a `Content-Range` response header so `resp.count`
  populates. This stays close to today's `MockTransport` tests.
- `tests/test_clients.py`: assert `build_supabase` returns a configured supabase
  `Client`.
- `tests/services/test_sync.py`, `tests/services/test_webhooks.py`: pass a
  fake/mock supabase client in (no longer patch `build_supabase`); keep patching
  `build_strava`.
- `conftest.py`: the `get_supabase` sentinel override still works because router
  tests mock at the service boundary.
- `test_architecture.py`: existing layering rules still hold.
- `ruff check .` and `mypy` must be clean.

## Risks / caveats

- The sync client's shutdown close method name should be confirmed at
  implementation time; if unavailable, process teardown is an acceptable fallback.
- `supabase` pulls in storage / realtime / gotrue sub-clients the app does not
  use. This is acceptable since it is the client the user asked for. Depending on
  `postgrest` alone is a noted alternative, not chosen.
- Thread-safety holds only while the shared client uses a single service-role key
  and is not mutated per request (see the singleton decision above).
