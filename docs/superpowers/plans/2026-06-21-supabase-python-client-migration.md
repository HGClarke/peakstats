# Supabase Python Client Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-rolled httpx + PostgREST calls in `backend/app/db/*` with the official synchronous `supabase` Python client, and serve every request and background task from a single shared client instance created once at startup.

**Architecture:** A FastAPI lifespan builds one `supabase.Client` (service-role key) on startup and stores it on `app.state.supabase`; `deps.get_supabase` hands that same instance to every request. The db layer keeps its function names, signatures, and TypedDict return shapes but swaps httpx mechanics for the supabase query builder (`.table().select().eq()…`, `.upsert(on_conflict=…)`, `count="exact"`, `.delete()`). Background tasks (`sync`, `webhooks`) stop building their own client and receive the shared one. The service stays fully synchronous.

**Tech Stack:** FastAPI, `supabase` (sync client, 2.x), `postgrest` (transitive), `respx` for db tests, pytest/ruff/mypy. Strava stays on httpx (unchanged).

## Global Constraints

- **Layering:** routers → services → db, no layer skips another; no `fastapi` imports in `services/`. (`backend/CLAUDE.md`)
- **Type annotations on every public function** — params and return. mypy runs with `disallow_untyped_defs`, `warn_unused_ignores`, `warn_redundant_casts`, `no_implicit_optional` (`backend/pyproject.toml`). Never add a `# type: ignore` or `cast(...)` that mypy reports as unused/redundant.
- **Async only when you `await`** — all functions here are sync `def`. (`backend/CLAUDE.md`)
- **Stay synchronous; do NOT convert to async/await.** (spec — out of scope)
- **Shared singleton:** exactly one supabase client for the process. Do NOT introduce per-request `.auth(jwt)` swapping on it (thread-safety depends on the single service-role key). (spec)
- **db layer purity:** each `db/` module declares a `TypedDict` row shape and returns it (`cast` the supabase `.data`). No business logic in `db/`. (`backend/CLAUDE.md`)
- **Behavior preserved:** every db function keeps its existing name, parameter names/shape, and return type. Only the client type (`httpx.Client` → `supabase.Client`) and the call mechanics change.
- **No new env vars.** `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` already exist; `render.yaml` stays a plain `pip install -r requirements.txt`.
- **Backend done = clean:** `cd backend && pytest && ruff check . && mypy` all pass.
- **Commits:** end each message body with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. The repo `hooks/pre-commit` runs ruff + mypy on every commit, so each commit must already be clean (or use `SKIP_HOOKS=1`, which this plan never needs).

## Why the core migration is a single commit (Task 2)

The client type flows through every layer: `build_supabase` → `get_supabase` → routers → services → db. Because the pre-commit hook runs **mypy on the whole `app/`**, you cannot land the db param-type change without simultaneously updating every caller's annotation — they are not independently acceptable. Task 2 therefore migrates the entire chain and lands as one commit. Within Task 2, individual db modules are verified in isolation with scoped `pytest tests/db/test_<module>.py` runs (each db test builds its own supabase client + respx and touches no other layer); the **full** `pytest && ruff check . && mypy` gate and the single commit happen at the end.

## File Structure

- `backend/requirements.txt` — **modify** — add `supabase` (pinned 2.x).
- `backend/requirements-dev.txt` — **modify** — add `respx` (pinned).
- `backend/app/clients.py` — **modify** — `build_supabase` returns `supabase.Client` (no network I/O at build).
- `backend/app/main.py` — **modify** — add a lifespan that owns the shared client on `app.state.supabase`.
- `backend/app/deps.py` — **modify** — `get_supabase(request)` returns `request.app.state.supabase`.
- `backend/app/db/athletes.py`, `tokens.py`, `sync_state.py`, `activities.py` — **modify** — supabase query builder; param type → `Client`; drop `_MERGE`, `_parse_total`.
- `backend/app/services/sync.py`, `webhooks.py` — **modify** — receive `supabase: Client`; stop building/closing their own client; still build the Strava client.
- `backend/app/services/athletes.py`, `activities.py`, `auth.py`, `tokens.py` — **modify** — annotation flip `httpx.Client` → `Client` (athletes keeps `import httpx` for `httpx.HTTPError` around the **Strava** deauthorize call).
- `backend/app/routers/sync.py`, `webhooks.py` — **modify** — wire the shared client into the background tasks / in-request refresh.
- `backend/app/routers/activities.py`, `athletes.py`, `auth.py` — **modify** — annotation flip `httpx.Client` → `Client`.
- `backend/tests/test_clients.py` — **modify** — assert `build_supabase` returns a supabase `Client`.
- `backend/tests/db/test_athletes.py`, `test_tokens.py`, `test_sync_state.py`, `test_activities.py` — **rewrite** — on `respx`.
- `backend/tests/services/test_sync.py`, `test_webhooks.py` — **modify** — pass a fake client in; drop the `build_supabase` monkeypatches.
- `backend/tests/routers/test_sync.py`, `test_webhooks.py` — **modify** — widen patched-callable signatures for the new arg order.
- `backend/CLAUDE.md` — **modify** — describe the db layer as the supabase client + shared singleton.

---

### Task 1: Add dependencies and verify the supabase client API

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/requirements-dev.txt`

**Interfaces:**
- Produces: `supabase` (runtime) and `respx` (dev) installed and importable; confirmed import paths for `create_client`, `Client`, `ClientOptions`, `CountMethod` used by Task 2.

- [ ] **Step 1: Install the packages and let pip resolve a compatible httpx**

`supabase` constrains `httpx`; the repo currently pins `httpx==0.28.1`. Install without fighting the resolver, then pin whatever it resolves:

Run:
```bash
cd backend
python -m pip install "supabase>=2,<3" respx
python -m pip show supabase httpx respx | grep -E "^(Name|Version):"
```
Expected: three `Name:`/`Version:` pairs. Note the exact versions (e.g. `supabase 2.15.1`, `httpx 0.27.x or 0.28.1`, `respx 0.21.1`). If pip downgraded `httpx`, that is fine — you will update its pin in Step 2.

- [ ] **Step 2: Pin the resolved versions**

In `backend/requirements.txt`, add `supabase` and reconcile the `httpx` pin with what Step 1 resolved. Replace the version numbers below with the actual resolved values from Step 1:

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic-settings==2.7.1
httpx==0.28.1
supabase==2.15.1
itsdangerous==2.2.0
```
(If Step 1 resolved a different `httpx`, set `httpx==<resolved>` to match; if a different `supabase`, set `supabase==<resolved>`.)

In `backend/requirements-dev.txt`, add `respx` under the existing dev tools:

```
# Development and CI dependencies. Runtime deps live in requirements.txt and are
# the only thing installed in production (see render.yaml).
-r requirements.txt
pytest==8.3.4
ruff==0.8.4
mypy==1.14.0
respx==0.21.1
```
(Use the `respx` version resolved in Step 1.)

- [ ] **Step 3: Verify imports and that `create_client` does no network I/O**

Run:
```bash
cd backend && python -c "
from supabase import create_client, Client, ClientOptions
from postgrest.types import CountMethod
c = create_client('https://test.supabase.co', 'svc', options=ClientOptions(postgrest_client_timeout=10))
print('client:', type(c).__name__)
print('has table:', callable(c.table))
print('has postgrest.session:', hasattr(getattr(c, 'postgrest', None), 'session'))
print('count exact:', CountMethod.exact.value)
"
```
Expected: prints `client: SyncClient` (or `Client`), `has table: True`, `has postgrest.session: True`, `count exact: exact` — and **no** network error, proving `create_client` is I/O-free and safe at startup.

If `from supabase import ClientOptions` raises `ImportError`, use `from supabase.client import ClientOptions` and adjust Task 2's `clients.py`/verification import accordingly. If `has postgrest.session` is `False`, note the actual attribute that holds the httpx client (Task 2's lifespan close is best-effort and guarded, so a `False` here just means the OS reclaims sockets at exit — acceptable per spec).

- [ ] **Step 4: Confirm the existing suite still passes (nothing migrated yet)**

Run: `cd backend && pytest -q && ruff check . && mypy`
Expected: all pass. Only dependency files changed.

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/requirements-dev.txt
git commit -m "build(backend): add supabase python client and respx test dep

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Migrate the db layer to the shared Supabase client

One atomic commit (see "Why the core migration is a single commit" above). Do the steps in order; run the scoped checks where shown; the full gate + commit is the final step.

**Files:** all `Modify`/`rewrite` files from File Structure except `requirements*.txt` and `CLAUDE.md` (CLAUDE.md is the last step of this task and rides the same commit).

**Interfaces:**
- Consumes: `build_supabase(settings) -> Client` (Task 1 deps).
- Produces:
  - `app.clients.build_supabase(settings: Settings) -> Client`
  - `app.deps.get_supabase(request: Request) -> Client`
  - db functions, unchanged names/returns, first param `client: Client`:
    `upsert_athlete`, `get_athlete -> AthleteRow | None`, `delete_athlete`;
    `upsert_tokens`, `get_tokens -> TokenRow | None`;
    `get_sync_state -> SyncStateRow | None`, `upsert_sync_state`;
    `upsert_activities`, `list_activities_since -> list[ActivityRow]`,
    `list_recent_activities -> list[ActivityRow]`, `count_activities -> int`,
    `list_activities_filtered(...) -> tuple[list[ActivityRow], int]`, `delete_activity`.
  - `services.sync.run_backfill(supabase: Client, settings: Settings, athlete_id: int) -> None`,
    `services.sync.refresh(supabase: Client, settings: Settings, athlete_id: int) -> RefreshResponse`,
    `services.sync.get_status(supabase: Client, ...)`, `services.sync.start_backfill(supabase: Client, ...)`.
  - `services.webhooks.process_event(supabase: Client, settings: Settings, event: StravaWebhookEvent) -> None`.

#### 2a — Client lifecycle

- [ ] **Step 1: Rewrite `build_supabase`**

Replace `backend/app/clients.py` entirely:

```python
import httpx
from supabase import Client, ClientOptions, create_client

from app.config import Settings
from app.strava import StravaClient


def build_supabase(settings: Settings) -> Client:
    """A Supabase client configured with the service-role key.

    `create_client` performs no network I/O, so this is safe to call at startup.
    The client wraps a synchronous httpx session (connection pooling + keep-alive);
    share one instance for the app's lifetime (see app.main lifespan).
    """
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
        options=ClientOptions(postgrest_client_timeout=10),
    )


def build_strava(settings: Settings) -> StravaClient:
    """A StravaClient backed by a short-lived httpx session."""
    redirect_uri = f"{settings.backend_base_url}/auth/strava/callback"
    http = httpx.Client(timeout=10)
    return StravaClient(
        http, settings.strava_client_id, settings.strava_client_secret, redirect_uri
    )
```
(If Task 1 Step 3 required `from supabase.client import ClientOptions`, use that import line instead.)

- [ ] **Step 2: Add the lifespan that owns the shared client**

Replace `backend/app/main.py` entirely:

```python
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.clients import build_supabase
from app.config import get_settings
from app.routers import activities, athletes, auth, health, sync, webhooks


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application instance."""
    settings = get_settings()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # One Supabase client for the whole process: connection pooling and
        # keep-alive, no per-request TLS handshake. Safe to share because we use a
        # single service-role key and never mutate per-request auth on the client.
        app.state.supabase = build_supabase(settings)
        try:
            yield
        finally:
            # Best-effort: release the pooled httpx connections held by the
            # postgrest sub-client. The sync supabase Client exposes no top-level
            # close(); if its internals change, the OS reclaims the sockets at
            # process exit (acceptable per the design spec).
            session = getattr(app.state.supabase.postgrest, "session", None)
            if session is not None:
                session.close()

    app = FastAPI(title="Peakstats API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(auth.router, prefix="/auth")
    app.include_router(athletes.router, prefix="/athlete")
    app.include_router(activities.router, prefix="/activities")
    app.include_router(sync.router, prefix="/sync")
    app.include_router(webhooks.router, prefix="/webhooks")
    return app


app = create_app()
```

- [ ] **Step 3: Rewrite `get_supabase`**

Replace `backend/app/deps.py` entirely:

```python
from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from supabase import Client

from app.clients import build_strava
from app.config import Settings, get_settings
from app.session import SESSION_COOKIE, read_session
from app.strava import StravaClient

__all__ = ["get_settings", "get_supabase", "get_strava", "get_current_athlete_id"]


def get_supabase(request: Request) -> Client:
    """Return the process-wide shared Supabase client (created in the app lifespan)."""
    return request.app.state.supabase


def get_strava(settings: Settings = Depends(get_settings)) -> Iterator[StravaClient]:
    """Yield a StravaClient backed by a short-lived httpx session."""
    strava = build_strava(settings)
    try:
        yield strava
    finally:
        strava.close()


def get_current_athlete_id(
    request: Request, settings: Settings = Depends(get_settings)
) -> int:
    """Return the athlete ID from the signed session cookie; raise 401 if missing or invalid."""
    token = request.cookies.get(SESSION_COOKIE)
    athlete_id = read_session(token, settings.session_secret) if token else None
    if athlete_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return athlete_id
```
Note: `request.app.state.supabase` is `Any` (starlette scope), so returning it as `Client` needs **no** `cast` — mypy here does not set `warn_return_any`, and a cast would be flagged redundant.

#### 2b — db layer (one module at a time, scoped-test each)

- [ ] **Step 4: Rewrite `db/athletes.py`**

```python
from typing import TypedDict, cast

from supabase import Client


class AthleteRow(TypedDict):
    """Shape of a row in the `athletes` table as returned by PostgREST."""

    id: int
    name: str
    avatar_url: str | None
    settings: dict


def upsert_athlete(
    client: Client, athlete_id: int, name: str, avatar_url: str | None
) -> None:
    """Insert or update an athlete row, merging on the primary key."""
    client.table("athletes").upsert(
        {"id": athlete_id, "name": name, "avatar_url": avatar_url},
        on_conflict="id",
    ).execute()


def get_athlete(client: Client, athlete_id: int) -> AthleteRow | None:
    """Return the athlete row for the given ID, or None if not found."""
    resp = client.table("athletes").select("*").eq("id", athlete_id).execute()
    return cast(AthleteRow, resp.data[0]) if resp.data else None


def delete_athlete(client: Client, athlete_id: int) -> None:
    """Delete the athlete row and all cascade-deleted related data."""
    client.table("athletes").delete().eq("id", athlete_id).execute()
```

- [ ] **Step 5: Rewrite `tests/db/test_athletes.py` and run it**

```python
import respx
from httpx import Response
from supabase import create_client

from app.db import athletes

CLIENT = create_client("https://proj.supabase.co", "svc")


@respx.mock
def test_upsert_athlete_merges_on_id():
    route = respx.route(method="POST", path="/rest/v1/athletes").mock(
        return_value=Response(201, json=[])
    )
    athletes.upsert_athlete(CLIENT, 7, "Ada", "http://x/a.png")
    req = route.calls.last.request
    assert req.url.params["on_conflict"] == "id"
    assert b'"id": 7' in req.content or b'"id":7' in req.content
    assert "merge-duplicates" in req.headers.get("prefer", "")


@respx.mock
def test_get_athlete_returns_first_row():
    respx.route(method="GET", path="/rest/v1/athletes").mock(
        return_value=Response(
            200, json=[{"id": 7, "name": "Ada", "avatar_url": None, "settings": {}}]
        )
    )
    row = athletes.get_athlete(CLIENT, 7)
    assert row == {"id": 7, "name": "Ada", "avatar_url": None, "settings": {}}


@respx.mock
def test_get_athlete_none_when_empty():
    respx.route(method="GET", path="/rest/v1/athletes").mock(
        return_value=Response(200, json=[])
    )
    assert athletes.get_athlete(CLIENT, 7) is None


@respx.mock
def test_delete_athlete_scopes_by_id():
    route = respx.route(method="DELETE", path="/rest/v1/athletes").mock(
        return_value=Response(204)
    )
    athletes.delete_athlete(CLIENT, 7)
    assert route.calls.last.request.url.params["id"] == "eq.7"
```
Run: `cd backend && pytest tests/db/test_athletes.py -q`
Expected: PASS. (respx's `path=` matcher matches the request path regardless of query string; `CLIENT` makes no real network call because respx intercepts.)

- [ ] **Step 6: Rewrite `db/tokens.py`**

```python
from datetime import datetime
from typing import TypedDict, cast

from supabase import Client


class TokenRow(TypedDict):
    """Shape of a row in the `strava_tokens` table as returned by PostgREST."""

    athlete_id: int
    access_token: str
    refresh_token: str
    expires_at: str  # ISO-8601 timestamp string


def upsert_tokens(
    client: Client,
    athlete_id: int,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
) -> None:
    """Insert or update a Strava token row for the athlete, merging on athlete_id."""
    client.table("strava_tokens").upsert(
        {
            "athlete_id": athlete_id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at.isoformat(),
        },
        on_conflict="athlete_id",
    ).execute()


def get_tokens(client: Client, athlete_id: int) -> TokenRow | None:
    """Return the stored Strava tokens for the athlete, or None if not found."""
    resp = (
        client.table("strava_tokens")
        .select("*")
        .eq("athlete_id", athlete_id)
        .execute()
    )
    return cast(TokenRow, resp.data[0]) if resp.data else None
```

- [ ] **Step 7: Rewrite `tests/db/test_tokens.py` and run it**

```python
from datetime import UTC, datetime

import respx
from httpx import Response
from supabase import create_client

from app.db import tokens

CLIENT = create_client("https://proj.supabase.co", "svc")


@respx.mock
def test_upsert_tokens_merges_on_athlete_id():
    route = respx.route(method="POST", path="/rest/v1/strava_tokens").mock(
        return_value=Response(201, json=[])
    )
    tokens.upsert_tokens(
        CLIENT, 7, "AT", "RT", datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
    )
    req = route.calls.last.request
    assert req.url.params["on_conflict"] == "athlete_id"
    assert b'"access_token": "AT"' in req.content or b'"access_token":"AT"' in req.content
    assert "merge-duplicates" in req.headers.get("prefer", "")


@respx.mock
def test_get_tokens_returns_row():
    respx.route(method="GET", path="/rest/v1/strava_tokens").mock(
        return_value=Response(
            200,
            json=[{"athlete_id": 7, "access_token": "AT", "refresh_token": "RT",
                   "expires_at": "2026-06-21T12:00:00+00:00"}],
        )
    )
    row = tokens.get_tokens(CLIENT, 7)
    assert row is not None and row["access_token"] == "AT"


@respx.mock
def test_get_tokens_none_when_empty():
    respx.route(method="GET", path="/rest/v1/strava_tokens").mock(
        return_value=Response(200, json=[])
    )
    assert tokens.get_tokens(CLIENT, 7) is None
```
Run: `cd backend && pytest tests/db/test_tokens.py -q`
Expected: PASS.

- [ ] **Step 8: Rewrite `db/sync_state.py`**

```python
from typing import TypedDict, cast

from supabase import Client


class SyncStateRow(TypedDict):
    athlete_id: int
    status: str
    progress: int
    last_backfill_at: str | None
    last_sync_at: str | None
    last_webhook_event_id: int | None


def get_sync_state(client: Client, athlete_id: int) -> SyncStateRow | None:
    resp = (
        client.table("sync_state").select("*").eq("athlete_id", athlete_id).execute()
    )
    return cast(SyncStateRow, resp.data[0]) if resp.data else None


def upsert_sync_state(client: Client, athlete_id: int, fields: dict) -> None:
    client.table("sync_state").upsert(
        {"athlete_id": athlete_id, **fields}, on_conflict="athlete_id"
    ).execute()
```

- [ ] **Step 9: Rewrite `tests/db/test_sync_state.py` and run it**

```python
import respx
from httpx import Response
from supabase import create_client

from app.db import sync_state

CLIENT = create_client("https://proj.supabase.co", "svc")


@respx.mock
def test_get_sync_state_returns_row():
    respx.route(method="GET", path="/rest/v1/sync_state").mock(
        return_value=Response(
            200,
            json=[{"athlete_id": 7, "status": "idle", "progress": 100,
                   "last_backfill_at": "T1", "last_sync_at": "T2",
                   "last_webhook_event_id": None}],
        )
    )
    row = sync_state.get_sync_state(CLIENT, 7)
    assert row is not None and row["status"] == "idle"


@respx.mock
def test_get_sync_state_none_when_empty():
    respx.route(method="GET", path="/rest/v1/sync_state").mock(
        return_value=Response(200, json=[])
    )
    assert sync_state.get_sync_state(CLIENT, 7) is None


@respx.mock
def test_upsert_sync_state_merges_and_includes_fields():
    route = respx.route(method="POST", path="/rest/v1/sync_state").mock(
        return_value=Response(201, json=[])
    )
    sync_state.upsert_sync_state(CLIENT, 7, {"status": "backfilling", "progress": 0})
    req = route.calls.last.request
    assert req.url.params["on_conflict"] == "athlete_id"
    assert b'"status": "backfilling"' in req.content or b'"status":"backfilling"' in req.content
    assert b'"athlete_id": 7' in req.content or b'"athlete_id":7' in req.content
    assert "merge-duplicates" in req.headers.get("prefer", "")
```
Run: `cd backend && pytest tests/db/test_sync_state.py -q`
Expected: PASS.

- [ ] **Step 10: Rewrite `db/activities.py`**

```python
from typing import Any, NotRequired, TypedDict, cast

from postgrest.types import CountMethod
from supabase import Client


class ActivityRow(TypedDict):
    id: int
    athlete_id: int
    name: str
    type: str
    start_date: str
    start_date_local: str | None
    distance_m: float
    moving_time_s: int
    elapsed_time_s: int
    elev_gain_m: float
    avg_speed_ms: float | None
    avg_hr: int | None
    summary_polyline: str | None
    created_at: NotRequired[str]


def upsert_activities(client: Client, rows: list[ActivityRow]) -> None:
    if not rows:
        return
    client.table("activities").upsert(
        cast(list[dict[str, Any]], rows), on_conflict="id"
    ).execute()


def list_activities_since(
    client: Client, athlete_id: int, since_iso: str
) -> list[ActivityRow]:
    resp = (
        client.table("activities")
        .select("*")
        .eq("athlete_id", athlete_id)
        .gte("start_date", since_iso)
        .order("start_date", desc=False)
        .execute()
    )
    return cast(list[ActivityRow], resp.data)


def list_recent_activities(
    client: Client, athlete_id: int, limit: int
) -> list[ActivityRow]:
    resp = (
        client.table("activities")
        .select("*")
        .eq("athlete_id", athlete_id)
        .order("start_date", desc=True)
        .limit(limit)
        .execute()
    )
    return cast(list[ActivityRow], resp.data)


def count_activities(client: Client, athlete_id: int) -> int:
    resp = (
        client.table("activities")
        .select("id", count=CountMethod.exact)
        .eq("athlete_id", athlete_id)
        .limit(1)
        .execute()
    )
    return resp.count or 0


def list_activities_filtered(
    client: Client,
    athlete_id: int,
    *,
    q: str | None,
    min_dist: float | None,
    min_time: int | None,
    min_elev: float | None,
    order: str,
    as_of: str,
    offset: int,
    limit: int,
) -> tuple[list[ActivityRow], int]:
    # `query: Any` sidesteps the differing builder subtypes returned by each
    # chained filter (select -> filter -> ...), which mypy would otherwise reject
    # on reassignment.
    query: Any = (
        client.table("activities")
        .select("*", count=CountMethod.exact)
        .eq("athlete_id", athlete_id)
        .lte("created_at", as_of)
    )
    if q:
        query = query.ilike("name", f"%{q}%")
    if min_dist is not None:
        query = query.gte("distance_m", min_dist)
    if min_time is not None:
        query = query.gte("moving_time_s", min_time)
    if min_elev is not None:
        query = query.gte("elev_gain_m", min_elev)
    # `order` is a PostgREST order string the service builds, e.g.
    # "avg_speed_ms.desc.nullslast,id.desc"; replay each clause as an .order() call
    # so the emitted query matches the previous behavior exactly.
    for part in order.split(","):
        column, _, rest = part.partition(".")
        tokens = rest.split(".") if rest else []
        desc = "desc" in tokens
        nullsfirst: bool | None = None
        if "nullslast" in tokens:
            nullsfirst = False
        elif "nullsfirst" in tokens:
            nullsfirst = True
        query = query.order(column, desc=desc, nullsfirst=nullsfirst)
    resp = query.range(offset, offset + limit - 1).execute()
    return cast(list[ActivityRow], resp.data), (resp.count or 0)


def delete_activity(client: Client, athlete_id: int, activity_id: int) -> None:
    client.table("activities").delete().eq("id", activity_id).eq(
        "athlete_id", athlete_id
    ).execute()
```
Notes: `_MERGE` and `_parse_total` are removed; `count="exact"` is replaced by `CountMethod.exact` (mypy-typed); the empty-list short-circuit in `upsert_activities` is kept.

- [ ] **Step 11: Rewrite `tests/db/test_activities.py` and run it**

```python
import respx
from httpx import Response
from supabase import create_client

from app.db import activities

CLIENT = create_client("https://proj.supabase.co", "svc")


@respx.mock
def test_upsert_activities_posts_rows_with_merge():
    route = respx.route(method="POST", path="/rest/v1/activities").mock(
        return_value=Response(201, json=[])
    )
    activities.upsert_activities(CLIENT, [{"id": 1, "athlete_id": 7, "name": "Ride"}])  # type: ignore[list-item]
    req = route.calls.last.request
    assert req.url.params["on_conflict"] == "id"
    assert "merge-duplicates" in req.headers.get("prefer", "")
    assert b'"id": 1' in req.content or b'"id":1' in req.content


@respx.mock
def test_upsert_activities_noop_on_empty():
    route = respx.route(method="POST", path="/rest/v1/activities").mock(
        return_value=Response(201, json=[])
    )
    activities.upsert_activities(CLIENT, [])
    assert not route.called


@respx.mock
def test_count_activities_reads_exact_count():
    respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(200, json=[{"id": 1}], headers={"Content-Range": "0-0/42"})
    )
    assert activities.count_activities(CLIENT, 7) == 42


@respx.mock
def test_count_activities_zero_when_empty():
    respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(200, json=[], headers={"Content-Range": "*/0"})
    )
    assert activities.count_activities(CLIENT, 7) == 0


@respx.mock
def test_list_activities_since_filters_and_orders():
    route = respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(200, json=[{"id": 1, "athlete_id": 7, "name": "Ride"}])
    )
    rows = activities.list_activities_since(CLIENT, 7, "2026-06-08T00:00:00+00:00")
    params = route.calls.last.request.url.params
    assert params["athlete_id"] == "eq.7"
    assert params["start_date"] == "gte.2026-06-08T00:00:00+00:00"
    assert params["order"] == "start_date.asc"
    assert rows == [{"id": 1, "athlete_id": 7, "name": "Ride"}]


@respx.mock
def test_list_recent_activities_orders_desc_and_limits():
    route = respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(200, json=[{"id": 9, "athlete_id": 7, "name": "Ride"}])
    )
    rows = activities.list_recent_activities(CLIENT, 7, limit=5)
    params = route.calls.last.request.url.params
    assert params["athlete_id"] == "eq.7"
    assert params["order"] == "start_date.desc"
    assert params["limit"] == "5"
    assert rows == [{"id": 9, "athlete_id": 7, "name": "Ride"}]


@respx.mock
def test_list_activities_filtered_builds_query_and_reads_count():
    route = respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(
            200,
            json=[{"id": 9, "athlete_id": 7, "name": "Ride"}],
            headers={"Content-Range": "0-8/42"},
        )
    )
    rows, total = activities.list_activities_filtered(
        CLIENT, 7,
        q="loop", min_dist=1000.0, min_time=600, min_elev=50.0,
        order="distance_m.desc,id.desc",
        as_of="2026-06-21T12:00:00+00:00",
        offset=0, limit=9,
    )
    req = route.calls.last.request
    params = req.url.params
    assert params["athlete_id"] == "eq.7"
    assert params["created_at"] == "lte.2026-06-21T12:00:00+00:00"
    assert "ilike" in params["name"] and "loop" in params["name"]
    assert params["distance_m"] == "gte.1000.0"
    assert params["moving_time_s"] == "gte.600"
    assert params["elev_gain_m"] == "gte.50.0"
    assert params["order"] == "distance_m.desc,id.desc"
    assert req.headers["range"] == "0-8"
    assert total == 42
    assert rows == [{"id": 9, "athlete_id": 7, "name": "Ride"}]


@respx.mock
def test_list_activities_filtered_omits_empty_filters():
    route = respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(200, json=[], headers={"Content-Range": "*/0"})
    )
    rows, total = activities.list_activities_filtered(
        CLIENT, 7,
        q=None, min_dist=None, min_time=None, min_elev=None,
        order="start_date.desc,id.desc",
        as_of="2026-06-21T12:00:00+00:00",
        offset=0, limit=9,
    )
    params = route.calls.last.request.url.params
    assert "name" not in params
    assert "distance_m" not in params
    assert "moving_time_s" not in params
    assert "elev_gain_m" not in params
    assert total == 0
    assert rows == []


@respx.mock
def test_delete_activity_scopes_by_athlete_and_id():
    route = respx.route(method="DELETE", path="/rest/v1/activities").mock(
        return_value=Response(204)
    )
    activities.delete_activity(CLIENT, athlete_id=7, activity_id=123)
    params = route.calls.last.request.url.params
    assert params["id"] == "eq.123"
    assert params["athlete_id"] == "eq.7"
```
Run: `cd backend && pytest tests/db/ -q`
Expected: all db tests PASS. If `req.headers["range"]` is absent, print `dict(req.headers)` and `dict(params)` to see whether postgrest emitted `Range` as a header vs `offset`/`limit` params for this version, then adjust the assertion to match the actual mechanism (the production behavior is correct either way — this only affects the test assertion).

#### 2c — flip caller annotations (no behavior change)

- [ ] **Step 12: Re-annotate the read-path services**

In each file, change the supabase parameter type from `httpx.Client` to `Client`, fixing imports.

`backend/app/services/activities.py`: replace `import httpx` (line ~5) with `from supabase import Client`, and change both `supabase: httpx.Client` (in `get_overview` and `list_activities`) to `supabase: Client`.

`backend/app/services/tokens.py`: replace `import httpx` with `from supabase import Client`; change `supabase: httpx.Client` to `supabase: Client`.

`backend/app/services/auth.py`: replace `import httpx` with `from supabase import Client`; change `supabase: httpx.Client` to `supabase: Client` in `handle_callback`.

`backend/app/services/athletes.py`: **keep** `import httpx` (used by `except httpx.HTTPError` around the Strava `deauthorize` call) and **add** `from supabase import Client`; change both `supabase: httpx.Client` to `supabase: Client` (in `get_profile` and `disconnect`). Verify the import block stays isort-clean (`import httpx` in the stdlib/third-party group, then a blank line, then the `from app...`/`from supabase...` group — run ruff in Step 16 to confirm).

- [ ] **Step 13: Re-annotate the read-path routers**

`backend/app/routers/activities.py`, `backend/app/routers/athletes.py`, `backend/app/routers/auth.py`: replace `import httpx` with `from supabase import Client` and change every `supabase: httpx.Client = Depends(get_supabase)` to `supabase: Client = Depends(get_supabase)`. (None of these three routers use httpx for anything else.)

#### 2d — background tasks receive the shared client

- [ ] **Step 14: Migrate `services/sync.py`**

Change the imports and the two background functions. Replace the import block top (lines ~1-11):

```python
import logging
from datetime import UTC, datetime

from supabase import Client

from app.clients import build_strava
from app.config import Settings
from app.db import activities as activities_db
from app.db import sync_state as sync_state_db
from app.models.sync import RefreshResponse, SyncStatusResponse
from app.services.tokens import get_valid_access_token
```
(`import httpx` and `build_supabase` are removed; `build_strava` stays.)

Change the four supabase-typed signatures:
- `def get_status(supabase: Client, athlete_id: int) -> SyncStatusResponse:`
- `def start_backfill(supabase: Client, athlete_id: int) -> tuple[SyncStatusResponse, bool]:`

Replace `run_backfill` (currently builds + closes its own client) with:

```python
def run_backfill(supabase: Client, settings: Settings, athlete_id: int) -> None:
    strava = build_strava(settings)
    try:
        access_token = get_valid_access_token(supabase, strava, athlete_id)
        page = 1
        while True:
            summaries = strava.list_activities(
                access_token, page=page, per_page=PER_PAGE
            )
            if not summaries:
                break
            rows = [_to_activity_row(athlete_id, s) for s in summaries]
            activities_db.upsert_activities(supabase, rows)  # type: ignore[arg-type]
            sync_state_db.upsert_sync_state(
                supabase, athlete_id,
                {"status": "backfilling", "progress": min(95, page * 10)},
            )
            if len(summaries) < PER_PAGE:
                break
            page += 1
        now = datetime.now(UTC).isoformat()
        sync_state_db.upsert_sync_state(
            supabase, athlete_id,
            {"status": "idle", "progress": 100,
             "last_backfill_at": now, "last_sync_at": now},
        )
    except Exception:
        logger.exception("Backfill failed for athlete %s", athlete_id)
        sync_state_db.upsert_sync_state(supabase, athlete_id, {"status": "error"})
    finally:
        strava.close()
```

Replace `refresh` with:

```python
def refresh(supabase: Client, settings: Settings, athlete_id: int) -> RefreshResponse:
    strava = build_strava(settings)
    try:
        access_token = get_valid_access_token(supabase, strava, athlete_id)
        row = sync_state_db.get_sync_state(supabase, athlete_id)
        if row is None or row["last_backfill_at"] is None:
            raise SyncNotReadyError(
                "Refresh requires a completed initial backfill"
            )
        after: int | None = None
        if row["last_sync_at"] is not None:
            after = int(datetime.fromisoformat(row["last_sync_at"]).timestamp())
        count = 0
        page = 1
        while True:
            summaries = strava.list_activities(
                access_token, page=page, per_page=PER_PAGE, after=after
            )
            if not summaries:
                break
            rows = [_to_activity_row(athlete_id, s) for s in summaries]
            activities_db.upsert_activities(supabase, rows)  # type: ignore[arg-type]
            count += len(summaries)
            if len(summaries) < PER_PAGE:
                break
            page += 1
        now = datetime.now(UTC).isoformat()
        sync_state_db.upsert_sync_state(
            supabase, athlete_id, {"last_sync_at": now}
        )
        return RefreshResponse(synced=count)
    finally:
        strava.close()
```
(The `# type: ignore[arg-type]` on `upsert_activities` stays — `rows` is `list[dict]` passed to a `list[ActivityRow]` param, exactly as before. mypy's `warn_unused_ignores` will confirm it is still required.)

- [ ] **Step 15: Migrate `services/webhooks.py`**

Replace the file with (drops `build_supabase`/`.close()`, receives `supabase`):

```python
import logging

from supabase import Client

from app.clients import build_strava
from app.config import Settings
from app.db import activities as activities_db
from app.db import athletes as athletes_db
from app.db import sync_state as sync_state_db
from app.models.webhooks import StravaWebhookEvent
from app.services import sync as sync_service
from app.services.tokens import get_valid_access_token

logger = logging.getLogger(__name__)


def process_event(
    supabase: Client, settings: Settings, event: StravaWebhookEvent
) -> None:
    """Ingest one Strava webhook event: fetch+upsert or delete the activity.

    Runs as a background task on the shared Supabase client. Builds its own Strava
    client; ignores non-activity, foreign-subscription, and unknown-owner events;
    and swallows errors (we have already returned 200 to Strava).
    """
    if event.object_type != "activity":
        logger.info("Ignoring non-activity webhook event: %s", event.object_type)
        return
    if (
        settings.strava_webhook_subscription_id
        and event.subscription_id != settings.strava_webhook_subscription_id
    ):
        logger.warning("Ignoring webhook from unexpected subscription %s",
                       event.subscription_id)
        return

    strava = build_strava(settings)
    try:
        if athletes_db.get_athlete(supabase, event.owner_id) is None:
            logger.info("Ignoring webhook for unknown athlete %s", event.owner_id)
            return

        if event.aspect_type == "delete":
            activities_db.delete_activity(supabase, event.owner_id, event.object_id)
        else:  # "create" or "update"
            access_token = get_valid_access_token(supabase, strava, event.owner_id)
            detail = strava.get_activity(access_token, event.object_id)
            row = sync_service._to_activity_row(event.owner_id, detail)
            activities_db.upsert_activities(supabase, [row])  # type: ignore[list-item]

        sync_state_db.upsert_sync_state(
            supabase, event.owner_id, {"last_webhook_event_id": event.event_time}
        )
    except Exception:
        logger.exception("Failed to process webhook for athlete %s", event.owner_id)
    finally:
        strava.close()
```

- [ ] **Step 16: Wire the routers**

`backend/app/routers/sync.py` — replace the file:

```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from supabase import Client

from app.config import Settings, get_settings
from app.deps import get_current_athlete_id, get_supabase
from app.models.sync import RefreshResponse, SyncStatusResponse
from app.services import sync as sync_service

router = APIRouter()


@router.get("/status", response_model=SyncStatusResponse)
def status(
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: Client = Depends(get_supabase),
) -> SyncStatusResponse:
    return sync_service.get_status(supabase, athlete_id)


@router.post("/start", response_model=SyncStatusResponse)
def start(
    background_tasks: BackgroundTasks,
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: Client = Depends(get_supabase),
    settings: Settings = Depends(get_settings),
) -> SyncStatusResponse:
    result, started = sync_service.start_backfill(supabase, athlete_id)
    if started:
        background_tasks.add_task(
            sync_service.run_backfill, supabase, settings, athlete_id
        )
    return result


@router.post("/refresh", response_model=RefreshResponse)
def refresh(
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: Client = Depends(get_supabase),
    settings: Settings = Depends(get_settings),
) -> RefreshResponse:
    try:
        return sync_service.refresh(supabase, settings, athlete_id)
    except sync_service.SyncNotReadyError as exc:
        raise HTTPException(
            status_code=409, detail="Initial sync has not completed yet"
        ) from exc
    except Exception as exc:  # noqa: BLE001 - surface upstream failures as 502
        raise HTTPException(status_code=502, detail="Refresh from Strava failed") from exc
```

`backend/app/routers/webhooks.py` — add the `get_supabase` import and dependency, and pass `supabase` into the task. Replace the import block and the POST handler:

```python
import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import ValidationError
from supabase import Client

from app.config import Settings, get_settings
from app.deps import get_supabase
from app.models.webhooks import StravaWebhookEvent
from app.services import webhooks as webhooks_service

logger = logging.getLogger(__name__)

router = APIRouter()
```
and:
```python
@router.post("/strava")
async def receive_event(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
    supabase: Client = Depends(get_supabase),
) -> dict[str, str]:
    try:
        payload = await request.json()
        event = StravaWebhookEvent.model_validate(payload)
    except (ValueError, ValidationError):
        logger.warning("Ignoring malformed Strava webhook payload")
        return {"status": "ignored"}
    background_tasks.add_task(
        webhooks_service.process_event, supabase, settings, event
    )
    return {"status": "accepted"}
```
(The GET `validate_subscription` handler is unchanged.)

#### 2e — update remaining tests, gate, docs, commit

- [ ] **Step 17: Update `tests/test_clients.py`**

Replace the supabase test (the Strava test is unchanged):

```python
from supabase import Client

from app.clients import build_strava, build_supabase
from app.config import Settings


def _settings() -> Settings:
    return Settings(
        supabase_url="https://test.supabase.co",
        supabase_service_role_key="svc",
        backend_base_url="http://localhost:8000",
        strava_client_id="cid",
        strava_client_secret="sec",
    )


def test_build_supabase_returns_supabase_client():
    client = build_supabase(_settings())
    assert isinstance(client, Client)
    assert callable(client.table)


def test_build_strava_returns_configured_client():
    strava = build_strava(_settings())
    try:
        url = strava.authorize_url("state123")
        assert "client_id=cid" in url
        assert "state=state123" in url
    finally:
        strava.close()
```

- [ ] **Step 18: Update `tests/services/test_sync.py`**

The service tests mock the db functions, so the fake client is just an opaque sentinel. Two changes:

(1) Replace the `FakeSupabase` helper and drop the `build_supabase` monkeypatches. The fake no longer needs `.close()`:

```python
class FakeSupabase:
    pass
```

(2) For the three tests that exercise `run_backfill`/`refresh` (`test_refresh_raises_when_never_backfilled`, `test_run_backfill_paginates_and_finalizes`, `test_run_backfill_sets_error_on_failure`, `test_refresh_pulls_since_last_sync`): **delete** the line
`monkeypatch.setattr(sync_service, "build_supabase", lambda settings: FakeSupabase())`
and call the function with the client passed in. Concretely:

- `test_refresh_raises_when_never_backfilled`: change the call to
  `sync_service.refresh(FakeSupabase(), settings=object(), athlete_id=7)`.
- `test_run_backfill_paginates_and_finalizes`: change the call to
  `sync_service.run_backfill(FakeSupabase(), settings=object(), athlete_id=7)`.
- `test_run_backfill_sets_error_on_failure`: change the call to
  `sync_service.run_backfill(FakeSupabase(), settings=object(), athlete_id=7)`.
- `test_refresh_pulls_since_last_sync`: change the call to
  `sync_service.refresh(FakeSupabase(), settings=object(), athlete_id=7)`.

(All four already monkeypatch `sync_service.activities_db.*`, `sync_service.sync_state_db.*`, `get_valid_access_token`, and `build_strava`, so nothing else changes.)

Run: `cd backend && pytest tests/services/test_sync.py -q`
Expected: PASS.

- [ ] **Step 19: Update `tests/services/test_webhooks.py`**

(1) `FakeSupabase` no longer needs `.close()`:

```python
class FakeSupabase:
    pass
```

(2) In `_wire`, drop the `build_supabase` monkeypatch line and return both fakes:

```python
def _wire(monkeypatch, *, athlete=True):
    strava = FakeStrava()
    monkeypatch.setattr(webhooks_service, "build_strava", lambda settings: strava)
    monkeypatch.setattr(webhooks_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    monkeypatch.setattr(webhooks_service.athletes_db, "get_athlete",
                        lambda supabase, athlete_id: {"id": athlete_id} if athlete else None)
    return strava
```

(3) Pass the fake client into every `process_event` call. Update each call site:
- `test_create_event_fetches_and_upserts`: `webhooks_service.process_event(FakeSupabase(), SETTINGS, _event(aspect_type="create"))`
- `test_delete_event_removes_row_without_fetch`: `webhooks_service.process_event(FakeSupabase(), SETTINGS, _event(aspect_type="delete"))`
- `test_unknown_owner_is_ignored`: `webhooks_service.process_event(FakeSupabase(), SETTINGS, _event())`
- `test_fetch_error_is_swallowed`: `webhooks_service.process_event(FakeSupabase(), SETTINGS, _event(aspect_type="update"))`

(4) The two "ignored early" tests no longer build a supabase client at all, so assert no **Strava** client is built (the early `return` happens before `build_strava`). Replace their bodies' guard patches:

```python
def test_non_activity_event_builds_no_clients(monkeypatch):
    def fail(*a: object, **k: object) -> None:
        raise AssertionError("must not build a strava client for non-activity events")

    monkeypatch.setattr(webhooks_service, "build_strava", fail)
    webhooks_service.process_event(
        FakeSupabase(), SETTINGS, _event(object_type="athlete", aspect_type="update")
    )


def test_foreign_subscription_id_is_ignored(monkeypatch):
    def fail(*a: object, **k: object) -> None:
        raise AssertionError("must not build a strava client for a foreign subscription id")

    monkeypatch.setattr(webhooks_service, "build_strava", fail)
    settings = Settings(strava_webhook_subscription_id=999)
    webhooks_service.process_event(FakeSupabase(), settings, _event(subscription_id=1))
```

Run: `cd backend && pytest tests/services/test_webhooks.py -q`
Expected: PASS.

- [ ] **Step 20: Update `tests/routers/test_sync.py`**

The router now passes `supabase` first into `run_backfill`/`refresh`. Widen the patched callables:

- `test_start_schedules_backfill_when_started`:
  `monkeypatch.setattr(sync_service, "run_backfill", lambda supabase, settings, athlete_id: spawned.update(athlete=athlete_id))`
- `test_start_does_not_reschedule_when_already_running`: change `def fail(settings, athlete_id):` to `def fail(supabase, settings, athlete_id):`
- `test_refresh_returns_count`:
  `monkeypatch.setattr(sync_service, "refresh", lambda supabase, settings, athlete_id: RefreshResponse(synced=4))`
- `test_refresh_conflict_when_not_synced`: change `def not_ready(settings, athlete_id):` to `def not_ready(supabase, settings, athlete_id):`

(`status`/`start_backfill`/`get_status` patches keep their `lambda supabase, athlete_id` shape — unchanged.)

Run: `cd backend && pytest tests/routers/test_sync.py -q`
Expected: PASS.

- [ ] **Step 21: Update `tests/routers/test_webhooks.py`**

The POST handler now passes `supabase` first into `process_event`:

- `test_post_accepts_and_schedules_processing`:
  `monkeypatch.setattr(webhooks_service, "process_event", lambda supabase, settings, event: seen.update(owner=event.owner_id, obj=event.object_id))`
- `test_post_ignores_malformed_payload`: change `def fail(settings, event):` to `def fail(supabase, settings, event):`

Run: `cd backend && pytest tests/routers/test_webhooks.py -q`
Expected: PASS.

- [ ] **Step 22: Update `backend/CLAUDE.md`**

In the `deps.py` line of the Folder structure, and the `db/` bullet of Architecture rules, replace the httpx/PostgREST description with the supabase client. Specifically:

- Folder structure `deps.py` comment → `# FastAPI dependency injectors (shared supabase client, current_user, etc.)`
- Architecture rules `db/` bullet → change "typed wrappers around Supabase (sync `httpx`; PostgREST)" to "typed wrappers around the **supabase** Python client (sync). One module per logical table group (athletes, activities, segments, tokens). No business logic. Each module declares a `TypedDict` for its row shape and returns it (cast from the client's `.data`)."
- Add one line under Architecture rules noting the shared client: "The supabase client is a process-wide singleton built in the `app.main` lifespan and stored on `app.state.supabase`; `deps.get_supabase` returns it. Do not build per-request clients, and do not mutate per-request auth on it."

- [ ] **Step 23: Full gate**

Run: `cd backend && pytest && ruff check . && mypy`
Expected: all pass. Common things mypy/ruff may flag and how to resolve:
- Unused `# type: ignore` → remove only the ones mypy names (keep the two on `upsert_activities` calls if still required).
- Redundant `cast` → remove only the exact cast mypy names.
- Unused import (`httpx`/`build_supabase`) → delete it (recall `services/athletes.py` legitimately keeps `import httpx`).
- isort ordering on the new `from supabase import ...` / `from postgrest.types import ...` lines → run `ruff check . --fix` for import order only, then re-run the gate.

- [ ] **Step 24: Commit**

```bash
git add backend/app backend/tests backend/CLAUDE.md
git commit -m "refactor(db): migrate db layer to the supabase python client

Replace hand-rolled httpx/PostgREST calls with the official sync supabase
client, served from one process-wide instance created in the app lifespan.
Background sync/webhook tasks now receive the shared client instead of
building their own. db tests rewritten on respx.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Deploy and verify end-to-end

**Files:** none (operational). Render rebuilds from `requirements.txt` automatically; no env-var or `render.yaml` changes.

**Interfaces:**
- Consumes: Task 2 merged to the deploy branch.

- [ ] **Step 1: Merge and deploy** the branch per the project's normal flow (push → Render backend redeploys, installing `supabase`). Watch the Render deploy logs for a clean `pip install` (no httpx/supabase resolver conflict) and a successful startup (the lifespan builds the client at boot).

- [ ] **Step 2: Smoke-test the read path** — log in, open Overview (`GET /activities/overview`) and the Activities table (`GET /activities`). Both must return data, proving select/count/range work through the shared client.

- [ ] **Step 3: Smoke-test sync** — trigger `POST /sync/start` (backfill) for an athlete with no completed backfill, then `POST /sync/refresh`. Confirm `GET /sync/status` advances to `idle`/`100` and `synced` grows — proving upserts on the shared client from a background task.

- [ ] **Step 4: Smoke-test the webhook** — create/edit one activity in Strava; confirm it appears (upsert) and a delete removes it, proving `process_event` works on the shared client.

- [ ] **Step 5: Confirm connection reuse** — over several consecutive requests, the backend should not be opening a fresh TLS connection to Supabase each time (the point of the singleton). Spot-check Render logs / latency; no errors and stable/low per-request overhead is the success signal.

---

## Self-Review

**Spec coverage:**
- Replace httpx/PostgREST with the supabase sync client in `app/db/*` → Task 2 Steps 4-11. ✅
- `clients.build_supabase` returns a `Client` (no I/O at build) → Step 1. ✅
- FastAPI lifespan owns a shared client on `app.state.supabase` → Step 2. ✅
- `deps.get_supabase` returns the shared client (type `Client`, no per-request build/close) → Step 3. ✅
- upserts via `.upsert(on_conflict=...)` (default merge), empty-list short-circuit kept → Steps 4/6/8/10. ✅
- single/list selects via `.select().eq()/.gte()/.ilike().order(desc=)`, `get_* -> data[0] or None` → Steps 4/6/8/10. ✅
- counts via `count=CountMethod.exact` + `resp.count`; `_parse_total`/`Content-Range` parsing deleted → Step 10. ✅
- deletes via `.delete().eq()` → Steps 4/10. ✅
- TypedDict shapes kept, `.data` cast → all db steps. ✅
- background tasks receive the shared client (sync + webhooks) → Steps 14/15; router wiring → Step 16. ✅
- `/sync/refresh` runs in-request on the injected client → Step 16. ✅
- tests on respx (db), fake client passed into service tests, clients test → Steps 5/7/9/11/17/18/19. ✅
- requirements (supabase + respx) → Task 1. ✅
- CLAUDE.md → Step 22. ✅
- Stay synchronous / no async; shared-singleton thread-safety constraint → Global Constraints + Step 2 comment. ✅
- Error-handling note: grep confirmed the only `httpx.HTTPError`/`raise_for_status` near DB code is in `services/athletes.py` and wraps the **Strava** deauthorize call, so it stays (Step 12). No DB-call error handler keys off httpx. ✅
- Strava client stays on httpx; no schema changes → respected (clients.build_strava untouched; no migrations). ✅

**Placeholder scan:** No TBD/TODO. Version pins are "install-then-pin-resolved" with concrete commands (the exact version cannot be known without resolving against the pinned httpx). Every source step shows complete code or an exact old→new edit; every test step shows the full file or the exact line change.

**Type consistency:** `build_supabase -> Client` (Step 1) ↔ `app.state.supabase` (Step 2) ↔ `get_supabase -> Client` (Step 3) ↔ router params `supabase: Client` (Steps 13/16) ↔ service params `supabase: Client` (Steps 12/14/15) ↔ db params `client: Client` (Steps 4-10). `run_backfill(supabase, settings, athlete_id)` / `refresh(supabase, settings, athlete_id)` (Step 14) match the router calls (Step 16) and the patched test lambdas (Step 20). `process_event(supabase, settings, event)` (Step 15) matches the router task (Step 16) and the patched test lambdas (Step 21). `CountMethod.exact` (Step 10) is imported from `postgrest.types`, verified in Task 1 Step 3. `cast(list[ActivityRow], resp.data)` return types match each function's declared return.
