# Peakstats Phase 3a — Sync Pipeline + App Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backfill an athlete's Strava activity history into Supabase with a faithfully-ported sync screen and a manual refresh, on a unified design system + shared app shell.

**Architecture:** FastAPI owns the sync pipeline (layered `routers → services → db` per `backend/CLAUDE.md`). On first connect the SPA's `/sync` screen calls `POST /sync/start`, which flips `sync_state.status='backfilling'` and spawns an **in-process background task** (its own short-lived clients) that paginates `/athlete/activities`, upserts into `activities`, and bumps `sync_state.progress`. The SPA polls `GET /sync/status` and shows the design's overlay sync card; on completion the user clicks "Go to dashboard" → `/home`. Manual refresh (`POST /sync/refresh`) pulls activities since `last_sync_at`. The frontend adopts TanStack Query and a shared `AppShell` (sidebar + topbar), and unifies the whole app on the design files' token system.

**Tech Stack:** Python 3.12 + FastAPI + httpx + Pydantic + pytest + ruff + mypy (backend); React 19 + Vite + TypeScript + Tailwind v4 + TanStack Query v5 + Vitest + Testing Library (frontend); Supabase Postgres via PostgREST; Strava API.

## Global Constraints

- **Spec of record:** `docs/superpowers/specs/2026-06-20-phase3-sync-pipeline-design.md`. Design source vendored under `docs/design/` (`Peakstats Sync.dc.html`, `Peakstats Dashboard.dc.html`).
- **Backend layering (`backend/CLAUDE.md`):** `routers → services → db`, no layer skipping. Routers thin (parse request, call one service, own HTTP concerns). `services/` hold business logic, **no `fastapi` imports**, receive clients/settings as arguments. `db/` are typed PostgREST wrappers, one module per table group, each declaring a `TypedDict` row shape; no business logic. `models/` hold Pydantic I/O schemas. `deps.py` is the only place that calls `get_settings()` at request time. `config.py` holds every env var (none new this phase). `test_architecture.py` statically enforces these rules — keep it green.
- **Async rule:** use `async def` only when the body `await`s. This phase uses **sync** blocking I/O (`httpx.Client`) in plain `def` functions; FastAPI runs them in a threadpool.
- **Tests mirror source:** `app/services/sync.py` → `tests/services/test_sync.py`, etc. Router tests go through the `client` fixture (`tests/conftest.py`) and mock at the service boundary (patch `app.services.*`); service tests mock `app.db.*`; db tests exercise real httpx against `httpx.MockTransport`.
- **Type annotations on every public function** (params + return). No secrets in code or logs. `ruff check .` and `mypy` must be clean before each backend commit (there is a repo `pre-commit` hook running both).
- **Background task isolation:** the backfill task MUST build its own Supabase/Strava clients via `app/clients.py` (never reuse request-scoped `deps` clients, which close when the response is sent).
- **Frontend conventions (`frontend/CLAUDE.md`):** pages compose / components render; data via `api/` hooks; `@/` imports; **token utilities only — no raw hex, no `text-[#..] dark:text-[#..]` pairs** (SVG stroke/fill literals are the allowed exception); co-located `*.test.tsx`; react-router `<Link>`/`navigate` for navigation. `npm test && npm run lint && npm run build` must pass before a frontend task is done. `erasableSyntaxOnly` is on: no enums/namespaces/param-properties — use union types / `as const`.
- **Strava details:** activities endpoint `GET https://www.strava.com/api/v3/athlete/activities`, `per_page=200`, per-call `Authorization: Bearer <token>`. Access tokens expire hourly → refresh on demand before any call. All tests stub Strava (`httpx.MockTransport` / fakes); real backfill is verified only against the deployed stack.
- **Commit after every task.** TDD throughout: failing test → run it red → implement → run it green → commit.

---

## File Structure

**Backend (`backend/`)**
- `app/strava.py` — MODIFY: add `list_activities` + `close`.
- `app/clients.py` — CREATE: `build_supabase` / `build_strava` factories (no fastapi).
- `app/deps.py` — MODIFY: `get_supabase`/`get_strava` delegate to `clients.py`.
- `app/db/activities.py` — CREATE: `upsert_activities`, `count_activities`, `ActivityRow`.
- `app/db/sync_state.py` — CREATE: `get_sync_state`, `upsert_sync_state`, `SyncStateRow`.
- `app/services/tokens.py` — CREATE: `get_valid_access_token`.
- `app/services/sync.py` — CREATE: mapping + `start_backfill`/`run_backfill`/`get_status` (+ `refresh` in Task 12).
- `app/models/sync.py` — CREATE: `SyncStatusResponse` (+ `RefreshResponse` in Task 12).
- `app/routers/sync.py` — CREATE: `GET /status`, `POST /start` (+ `POST /refresh` in Task 12).
- `app/main.py` — MODIFY: register the sync router.
- Tests mirror each: `tests/test_strava.py` (append), `tests/test_clients.py`, `tests/db/test_activities.py`, `tests/db/test_sync_state.py`, `tests/services/test_tokens.py`, `tests/services/test_sync.py`, `tests/routers/test_sync.py`.

**Frontend (`frontend/`)**
- `src/index.css` — MODIFY: extend tokens + Archivo body font + keyframes/animation utilities.
- `src/app/providers/QueryProvider.tsx` — CREATE.
- `src/App.tsx` — MODIFY: wrap in `QueryProvider`.
- `src/api/auth.ts` — MODIFY: `useAthlete` → `useQuery`.
- `src/test/providers.tsx` — CREATE: shared test wrapper.
- `src/components/app-shell/{Sidebar,Topbar,AppShell}.tsx` (+ tests) — CREATE.
- `src/types/sync.ts` — CREATE.
- `src/api/sync.ts` (+ test) — CREATE.
- `src/pages/sync/SyncPage.tsx` (+ test) — CREATE.
- `src/app/router.tsx` — MODIFY: add `/sync`.
- `src/pages/app-home/AppHome.tsx` (+ test) — MODIFY: rebuild as Overview shell.

---

## Task 1: Strava `list_activities` + `close` (backend)

**Files:**
- Modify: `backend/app/strava.py`
- Test: `backend/tests/test_strava.py`

**Interfaces:**
- Consumes: existing `StravaClient(http, client_id, client_secret, redirect_uri)`.
- Produces: `StravaClient.list_activities(access_token: str, *, page: int = 1, per_page: int = 200, after: int | None = None) -> list[dict]` (authenticated GET, raises for non-2xx); `StravaClient.close() -> None`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_strava.py`:
```python
def test_list_activities_sends_bearer_and_params():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/athlete/activities"
        assert request.headers["authorization"] == "Bearer AT"
        assert request.url.params["page"] == "2"
        assert request.url.params["per_page"] == "200"
        assert request.url.params["after"] == "1700000000"
        return httpx.Response(200, json=[{"id": 1}, {"id": 2}])

    acts = _client(handler).list_activities("AT", page=2, per_page=200, after=1_700_000_000)
    assert acts == [{"id": 1}, {"id": 2}]


def test_list_activities_omits_after_when_none():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "after" not in request.url.params
        return httpx.Response(200, json=[])

    assert _client(handler).list_activities("AT", page=1) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_strava.py -k list_activities -v`
Expected: FAIL — `AttributeError: 'StravaClient' object has no attribute 'list_activities'`.

- [ ] **Step 3: Implement `list_activities` + `close`**

In `backend/app/strava.py`, add the API base constant near the other URL constants:
```python
API_BASE_URL = "https://www.strava.com/api/v3"
```
Then add these methods to `StravaClient` (after `deauthorize`):
```python
    def list_activities(
        self,
        access_token: str,
        *,
        page: int = 1,
        per_page: int = 200,
        after: int | None = None,
    ) -> list[dict]:
        params: dict[str, int] = {"page": page, "per_page": per_page}
        if after is not None:
            params["after"] = after
        response = self._http.get(
            f"{API_BASE_URL}/athlete/activities",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._http.close()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_strava.py -v`
Expected: all pass.

- [ ] **Step 5: Lint, type-check, commit**

```bash
cd backend && ruff check . && mypy
git add backend/app/strava.py backend/tests/test_strava.py
git commit -m "feat(backend): Strava list_activities + client close"
```

---

## Task 2: db layer — activities + sync_state (backend)

**Files:**
- Create: `backend/app/db/activities.py`, `backend/app/db/sync_state.py`
- Test: `backend/tests/db/test_activities.py`, `backend/tests/db/test_sync_state.py`

**Interfaces:**
- Consumes: a configured `httpx.Client` (base_url `{supabase_url}/rest/v1`, service-key headers) — built in Task 4.
- Produces:
  - `app.db.activities.ActivityRow` (TypedDict); `upsert_activities(client, rows: list[ActivityRow]) -> None`; `count_activities(client, athlete_id: int) -> int`.
  - `app.db.sync_state.SyncStateRow` (TypedDict); `get_sync_state(client, athlete_id: int) -> SyncStateRow | None`; `upsert_sync_state(client, athlete_id: int, fields: dict) -> None`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/db/test_activities.py`:
```python
import httpx
from app.db import activities


def _client(handler) -> httpx.Client:
    return httpx.Client(
        base_url="https://proj.supabase.co/rest/v1",
        headers={"apikey": "svc", "Authorization": "Bearer svc",
                 "Content-Type": "application/json"},
        transport=httpx.MockTransport(handler),
    )


def test_upsert_activities_posts_rows_with_merge():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["prefer"] = request.headers.get("prefer")
        seen["body"] = request.read().decode()
        return httpx.Response(201, json=[])

    rows = [{"id": 1, "athlete_id": 7, "name": "Ride"}]
    activities.upsert_activities(_client(handler), rows)  # type: ignore[list-item]
    assert seen["url"] == "https://proj.supabase.co/rest/v1/activities?on_conflict=id"
    assert seen["prefer"] == "resolution=merge-duplicates"
    assert '"id": 1' in seen["body"]


def test_upsert_activities_noop_on_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not POST for empty rows")

    activities.upsert_activities(_client(handler), [])


def test_count_activities_parses_content_range():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["athlete_id"] == "eq.7"
        assert request.headers["prefer"] == "count=exact"
        return httpx.Response(200, json=[], headers={"Content-Range": "0-0/42"})

    assert activities.count_activities(_client(handler), 7) == 42


def test_count_activities_handles_star_range():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[], headers={"Content-Range": "*/0"})

    assert activities.count_activities(_client(handler), 7) == 0
```

Create `backend/tests/db/test_sync_state.py`:
```python
import httpx
from app.db import sync_state


def _client(handler) -> httpx.Client:
    return httpx.Client(
        base_url="https://proj.supabase.co/rest/v1",
        headers={"apikey": "svc", "Authorization": "Bearer svc",
                 "Content-Type": "application/json"},
        transport=httpx.MockTransport(handler),
    )


def test_get_sync_state_returns_first_row_or_none():
    def found(request: httpx.Request) -> httpx.Response:
        assert request.url.params["athlete_id"] == "eq.7"
        return httpx.Response(200, json=[{"athlete_id": 7, "status": "idle", "progress": 100,
                                          "last_backfill_at": None, "last_sync_at": None,
                                          "last_webhook_event_id": None}])

    assert sync_state.get_sync_state(_client(found), 7)["status"] == "idle"

    def empty(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    assert sync_state.get_sync_state(_client(empty), 7) is None


def test_upsert_sync_state_merges_fields():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["prefer"] = request.headers.get("prefer")
        seen["body"] = request.read().decode()
        return httpx.Response(201, json=[])

    sync_state.upsert_sync_state(_client(handler), 7, {"status": "backfilling", "progress": 0})
    assert seen["url"] == "https://proj.supabase.co/rest/v1/sync_state?on_conflict=athlete_id"
    assert seen["prefer"] == "resolution=merge-duplicates"
    assert '"athlete_id": 7' in seen["body"]
    assert '"status": "backfilling"' in seen["body"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/db/test_activities.py tests/db/test_sync_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db.activities'`.

- [ ] **Step 3: Implement the db modules**

Create `backend/app/db/activities.py`:
```python
from typing import TypedDict

import httpx

_MERGE = {"Prefer": "resolution=merge-duplicates"}


class ActivityRow(TypedDict):
    id: int
    athlete_id: int
    name: str
    type: str
    start_date: str
    distance_m: float
    moving_time_s: int
    elapsed_time_s: int
    elev_gain_m: float
    avg_speed_ms: float | None
    avg_hr: int | None
    summary_polyline: str | None


def upsert_activities(client: httpx.Client, rows: list[ActivityRow]) -> None:
    if not rows:
        return
    response = client.post(
        "/activities",
        params={"on_conflict": "id"},
        headers=_MERGE,
        json=rows,
    )
    response.raise_for_status()


def count_activities(client: httpx.Client, athlete_id: int) -> int:
    response = client.get(
        "/activities",
        params={"athlete_id": f"eq.{athlete_id}", "select": "id"},
        headers={"Prefer": "count=exact", "Range": "0-0"},
    )
    response.raise_for_status()
    content_range = response.headers.get("Content-Range", "")
    total = content_range.split("/")[-1]
    return int(total) if total.isdigit() else 0
```

Create `backend/app/db/sync_state.py`:
```python
from typing import cast, TypedDict

import httpx

_MERGE = {"Prefer": "resolution=merge-duplicates"}


class SyncStateRow(TypedDict):
    athlete_id: int
    status: str
    progress: int
    last_backfill_at: str | None
    last_sync_at: str | None
    last_webhook_event_id: int | None


def get_sync_state(client: httpx.Client, athlete_id: int) -> SyncStateRow | None:
    response = client.get(
        "/sync_state", params={"athlete_id": f"eq.{athlete_id}", "select": "*"}
    )
    response.raise_for_status()
    rows = response.json()
    return cast(SyncStateRow, rows[0]) if rows else None


def upsert_sync_state(
    client: httpx.Client, athlete_id: int, fields: dict
) -> None:
    response = client.post(
        "/sync_state",
        params={"on_conflict": "athlete_id"},
        headers=_MERGE,
        json=[{"athlete_id": athlete_id, **fields}],
    )
    response.raise_for_status()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/db/test_activities.py tests/db/test_sync_state.py -v`
Expected: all pass.

- [ ] **Step 5: Lint, type-check, commit**

```bash
cd backend && ruff check . && mypy
git add backend/app/db/activities.py backend/app/db/sync_state.py backend/tests/db/test_activities.py backend/tests/db/test_sync_state.py
git commit -m "feat(backend): db wrappers for activities + sync_state"
```

---

## Task 3: token-refresh service (backend)

**Files:**
- Create: `backend/app/services/tokens.py`
- Test: `backend/tests/services/test_tokens.py`

**Interfaces:**
- Consumes: `app.db.tokens.get_tokens`/`upsert_tokens` (Phase 2), `app.strava.StravaClient.refresh`/`StravaToken`.
- Produces: `app.services.tokens.get_valid_access_token(supabase, strava, athlete_id, *, now: datetime | None = None) -> str` (raises `ValueError` if no tokens stored).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/services/test_tokens.py`:
```python
from datetime import datetime, timedelta, timezone

import pytest
from app.services import tokens as tokens_service
from app.strava import StravaToken


class FakeStrava:
    def __init__(self) -> None:
        self.refreshed_with: str | None = None

    def refresh(self, refresh_token: str) -> StravaToken:
        self.refreshed_with = refresh_token
        return StravaToken("NEW_AT", "NEW_RT",
                           datetime(2099, 1, 1, tzinfo=timezone.utc))


def test_returns_existing_token_when_not_expiring(monkeypatch):
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    monkeypatch.setattr(tokens_service.tokens_db, "get_tokens",
                        lambda supabase, athlete_id: {"access_token": "AT",
                                                      "refresh_token": "RT",
                                                      "expires_at": future})
    strava = FakeStrava()
    token = tokens_service.get_valid_access_token(object(), strava, 7)
    assert token == "AT"
    assert strava.refreshed_with is None


def test_refreshes_and_persists_when_expiring(monkeypatch):
    soon = (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat()
    saved = {}
    monkeypatch.setattr(tokens_service.tokens_db, "get_tokens",
                        lambda supabase, athlete_id: {"access_token": "OLD",
                                                      "refresh_token": "RT",
                                                      "expires_at": soon})
    monkeypatch.setattr(tokens_service.tokens_db, "upsert_tokens",
                        lambda supabase, athlete_id, access_token, refresh_token, expires_at:
                        saved.update(at=access_token, rt=refresh_token))
    strava = FakeStrava()
    token = tokens_service.get_valid_access_token(object(), strava, 7)
    assert token == "NEW_AT"
    assert strava.refreshed_with == "RT"
    assert saved == {"at": "NEW_AT", "rt": "NEW_RT"}


def test_raises_when_no_tokens(monkeypatch):
    monkeypatch.setattr(tokens_service.tokens_db, "get_tokens",
                        lambda supabase, athlete_id: None)
    with pytest.raises(ValueError):
        tokens_service.get_valid_access_token(object(), FakeStrava(), 7)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/services/test_tokens.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.tokens'`.

- [ ] **Step 3: Implement the service**

Create `backend/app/services/tokens.py`:
```python
from datetime import datetime, timezone

import httpx

from app.db import tokens as tokens_db
from app.strava import StravaClient

REFRESH_BUFFER_S = 60


def get_valid_access_token(
    supabase: httpx.Client,
    strava: StravaClient,
    athlete_id: int,
    *,
    now: datetime | None = None,
) -> str:
    current = now or datetime.now(timezone.utc)
    row = tokens_db.get_tokens(supabase, athlete_id)
    if row is None:
        raise ValueError(f"No Strava tokens stored for athlete {athlete_id}")
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at.timestamp() - current.timestamp() > REFRESH_BUFFER_S:
        return row["access_token"]
    token = strava.refresh(row["refresh_token"])
    tokens_db.upsert_tokens(
        supabase, athlete_id, token.access_token, token.refresh_token, token.expires_at
    )
    return token.access_token
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/services/test_tokens.py -v`
Expected: 3 passed.

- [ ] **Step 5: Lint, type-check, commit**

```bash
cd backend && ruff check . && mypy
git add backend/app/services/tokens.py backend/tests/services/test_tokens.py
git commit -m "feat(backend): on-demand Strava token refresh service"
```

---

## Task 4: client factories + deps refactor (backend)

**Files:**
- Create: `backend/app/clients.py`
- Modify: `backend/app/deps.py`
- Test: `backend/tests/test_clients.py`

**Interfaces:**
- Produces: `app.clients.build_supabase(settings: Settings) -> httpx.Client`; `app.clients.build_strava(settings: Settings) -> StravaClient`. `deps.get_supabase`/`get_strava` unchanged in signature (still yield the same objects) but delegate to these factories.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_clients.py`:
```python
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


def test_build_supabase_sets_base_url_and_auth_headers():
    client = build_supabase(_settings())
    try:
        assert str(client.base_url) == "https://test.supabase.co/rest/v1"
        assert client.headers["apikey"] == "svc"
        assert client.headers["Authorization"] == "Bearer svc"
    finally:
        client.close()


def test_build_strava_returns_configured_client():
    strava = build_strava(_settings())
    try:
        url = strava.authorize_url("state123")
        assert "client_id=cid" in url
        assert "state=state123" in url
    finally:
        strava.close()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_clients.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.clients'`.

- [ ] **Step 3: Implement the factories**

Create `backend/app/clients.py`:
```python
import httpx

from app.config import Settings
from app.strava import StravaClient


def build_supabase(settings: Settings) -> httpx.Client:
    """A short-lived httpx client pre-configured for the Supabase REST API."""
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }
    return httpx.Client(
        base_url=f"{settings.supabase_url}/rest/v1", headers=headers, timeout=10
    )


def build_strava(settings: Settings) -> StravaClient:
    """A StravaClient backed by a short-lived httpx session."""
    redirect_uri = f"{settings.backend_base_url}/auth/strava/callback"
    http = httpx.Client(timeout=10)
    return StravaClient(
        http, settings.strava_client_id, settings.strava_client_secret, redirect_uri
    )
```

- [ ] **Step 4: Refactor `deps.py` to use the factories**

Replace the bodies of `get_supabase` and `get_strava` in `backend/app/deps.py`:
```python
from collections.abc import Iterator

import httpx
from fastapi import Depends, HTTPException, Request

from app.clients import build_strava, build_supabase
from app.config import Settings, get_settings
from app.session import SESSION_COOKIE, read_session
from app.strava import StravaClient

__all__ = ["get_settings", "get_supabase", "get_strava", "get_current_athlete_id"]


def get_supabase(settings: Settings = Depends(get_settings)) -> Iterator[httpx.Client]:
    """Yield a short-lived httpx client pre-configured for the Supabase REST API."""
    client = build_supabase(settings)
    try:
        yield client
    finally:
        client.close()


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

- [ ] **Step 5: Run the full backend suite to verify nothing regressed**

Run: `cd backend && python -m pytest -v`
Expected: all pass (existing auth/athlete tests still green after the deps refactor).

- [ ] **Step 6: Lint, type-check, commit**

```bash
cd backend && ruff check . && mypy
git add backend/app/clients.py backend/app/deps.py backend/tests/test_clients.py
git commit -m "refactor(backend): client factories shared by deps + background tasks"
```

---

## Task 5: sync service + model + router (status + start) (backend)

**Files:**
- Create: `backend/app/models/sync.py`, `backend/app/services/sync.py`, `backend/app/routers/sync.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/services/test_sync.py`, `backend/tests/routers/test_sync.py`

**Interfaces:**
- Consumes: `app.clients` (Task 4), `app.services.tokens.get_valid_access_token` (Task 3), `app.db.activities`/`app.db.sync_state` (Task 2), `app.strava.StravaClient.list_activities` (Task 1).
- Produces:
  - `app.models.sync.SyncStatusResponse(status: str, progress: int, synced: int, last_backfill_at: str | None, last_sync_at: str | None)`.
  - `app.services.sync._to_activity_row(athlete_id, summary) -> dict`.
  - `app.services.sync.get_status(supabase, athlete_id) -> SyncStatusResponse`.
  - `app.services.sync.start_backfill(supabase, athlete_id) -> tuple[SyncStatusResponse, bool]` (bool = "started a new backfill").
  - `app.services.sync.run_backfill(settings, athlete_id) -> None` (background entry point).
  - Routes on the sync router (`prefix="/sync"`): `GET /status`, `POST /start`.

- [ ] **Step 1: Write the failing service tests**

Create `backend/tests/services/test_sync.py`:
```python
from app.models.sync import SyncStatusResponse
from app.services import sync as sync_service


def test_to_activity_row_maps_summary_fields():
    summary = {
        "id": 555, "name": "River loop", "sport_type": "Ride",
        "start_date": "2026-06-15T08:00:00Z", "distance": 38700.0,
        "moving_time": 5662, "elapsed_time": 5900, "total_elevation_gain": 420.0,
        "average_speed": 6.8, "average_heartrate": 148.6,
        "map": {"summary_polyline": "abc"},
    }
    row = sync_service._to_activity_row(7, summary)
    assert row["id"] == 555
    assert row["athlete_id"] == 7
    assert row["type"] == "Ride"
    assert row["distance_m"] == 38700.0
    assert row["avg_hr"] == 149
    assert row["summary_polyline"] == "abc"


def test_to_activity_row_handles_missing_optionals():
    row = sync_service._to_activity_row(7, {
        "id": 1, "name": "Spin", "type": "Workout",
        "start_date": "2026-06-15T08:00:00Z", "distance": 0.0,
        "moving_time": 10, "elapsed_time": 10, "total_elevation_gain": 0.0,
    })
    assert row["avg_speed_ms"] is None
    assert row["avg_hr"] is None
    assert row["summary_polyline"] is None
    assert row["type"] == "Workout"


def test_get_status_never_synced(monkeypatch):
    monkeypatch.setattr(sync_service.sync_state_db, "get_sync_state",
                        lambda supabase, athlete_id: None)
    monkeypatch.setattr(sync_service.activities_db, "count_activities",
                        lambda supabase, athlete_id: 0)
    status = sync_service.get_status(object(), 7)
    assert status == SyncStatusResponse(status="never_synced", progress=0, synced=0)


def test_get_status_reads_row(monkeypatch):
    monkeypatch.setattr(sync_service.sync_state_db, "get_sync_state",
                        lambda supabase, athlete_id: {"status": "idle", "progress": 100,
                                                      "last_backfill_at": "T1",
                                                      "last_sync_at": "T2",
                                                      "last_webhook_event_id": None})
    monkeypatch.setattr(sync_service.activities_db, "count_activities",
                        lambda supabase, athlete_id: 218)
    status = sync_service.get_status(object(), 7)
    assert status.status == "idle"
    assert status.synced == 218
    assert status.last_sync_at == "T2"


def test_start_backfill_starts_when_idle(monkeypatch):
    calls = {}
    monkeypatch.setattr(sync_service.sync_state_db, "get_sync_state",
                        lambda supabase, athlete_id: None)
    monkeypatch.setattr(sync_service.sync_state_db, "upsert_sync_state",
                        lambda supabase, athlete_id, fields: calls.update(fields=fields))
    monkeypatch.setattr(sync_service.activities_db, "count_activities",
                        lambda supabase, athlete_id: 0)
    _, started = sync_service.start_backfill(object(), 7)
    assert started is True
    assert calls["fields"] == {"status": "backfilling", "progress": 0}


def test_start_backfill_idempotent_when_already_backfilling(monkeypatch):
    monkeypatch.setattr(sync_service.sync_state_db, "get_sync_state",
                        lambda supabase, athlete_id: {"status": "backfilling", "progress": 30,
                                                      "last_backfill_at": None,
                                                      "last_sync_at": None,
                                                      "last_webhook_event_id": None})
    monkeypatch.setattr(sync_service.activities_db, "count_activities",
                        lambda supabase, athlete_id: 50)

    def fail(*a, **k):
        raise AssertionError("must not re-upsert while backfilling")

    monkeypatch.setattr(sync_service.sync_state_db, "upsert_sync_state", fail)
    status, started = sync_service.start_backfill(object(), 7)
    assert started is False
    assert status.status == "backfilling"


def test_run_backfill_paginates_and_finalizes(monkeypatch):
    upserts = []
    states = []

    class FakeStrava:
        def __init__(self) -> None:
            self.pages = {1: [{"id": i, "name": "R", "type": "Ride",
                               "start_date": "2026-06-15T08:00:00Z", "distance": 1.0,
                               "moving_time": 1, "elapsed_time": 1,
                               "total_elevation_gain": 0.0} for i in range(200)],
                          2: [{"id": 999, "name": "R", "type": "Ride",
                               "start_date": "2026-06-15T08:00:00Z", "distance": 1.0,
                               "moving_time": 1, "elapsed_time": 1,
                               "total_elevation_gain": 0.0}]}

        def list_activities(self, access_token, *, page, per_page=200, after=None):
            return self.pages.get(page, [])

        def close(self):
            pass

    monkeypatch.setattr(sync_service, "build_supabase", lambda settings: object())
    monkeypatch.setattr(sync_service, "build_strava", lambda settings: FakeStrava())
    monkeypatch.setattr(sync_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    monkeypatch.setattr(sync_service.activities_db, "upsert_activities",
                        lambda supabase, rows: upserts.append(len(rows)))
    monkeypatch.setattr(sync_service.sync_state_db, "upsert_sync_state",
                        lambda supabase, athlete_id, fields: states.append(fields))

    sync_service.run_backfill(settings=object(), athlete_id=7)

    assert upserts == [200, 1]
    assert states[-1]["status"] == "idle"
    assert states[-1]["progress"] == 100
    assert states[-1]["last_backfill_at"]


def test_run_backfill_sets_error_on_failure(monkeypatch):
    states = []
    monkeypatch.setattr(sync_service, "build_supabase", lambda settings: object())

    class BoomStrava:
        def close(self):
            pass

    monkeypatch.setattr(sync_service, "build_strava", lambda settings: BoomStrava())

    def boom(supabase, strava, athlete_id):
        raise RuntimeError("token fail")

    monkeypatch.setattr(sync_service, "get_valid_access_token", boom)
    monkeypatch.setattr(sync_service.sync_state_db, "upsert_sync_state",
                        lambda supabase, athlete_id, fields: states.append(fields))

    sync_service.run_backfill(settings=object(), athlete_id=7)
    assert states[-1] == {"status": "error"}
```

- [ ] **Step 2: Run the service tests to verify they fail**

Run: `cd backend && python -m pytest tests/services/test_sync.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.sync'` / `app.services.sync`.

- [ ] **Step 3: Implement the model**

Create `backend/app/models/sync.py`:
```python
from pydantic import BaseModel


class SyncStatusResponse(BaseModel):
    status: str
    progress: int
    synced: int
    last_backfill_at: str | None = None
    last_sync_at: str | None = None
```

- [ ] **Step 4: Implement the sync service**

Create `backend/app/services/sync.py`:
```python
import logging
from datetime import datetime, timezone

import httpx

from app.clients import build_strava, build_supabase
from app.config import Settings
from app.db import activities as activities_db
from app.db import sync_state as sync_state_db
from app.models.sync import SyncStatusResponse
from app.services.tokens import get_valid_access_token

logger = logging.getLogger(__name__)

PER_PAGE = 200


def _to_activity_row(athlete_id: int, summary: dict) -> dict:
    hr = summary.get("average_heartrate")
    activity_map = summary.get("map") or {}
    return {
        "id": summary["id"],
        "athlete_id": athlete_id,
        "name": summary.get("name") or "Untitled",
        "type": summary.get("sport_type") or summary.get("type") or "Workout",
        "start_date": summary["start_date"],
        "distance_m": summary.get("distance", 0.0),
        "moving_time_s": summary.get("moving_time", 0),
        "elapsed_time_s": summary.get("elapsed_time", 0),
        "elev_gain_m": summary.get("total_elevation_gain", 0.0),
        "avg_speed_ms": summary.get("average_speed"),
        "avg_hr": round(hr) if hr is not None else None,
        "summary_polyline": activity_map.get("summary_polyline"),
    }


def get_status(supabase: httpx.Client, athlete_id: int) -> SyncStatusResponse:
    row = sync_state_db.get_sync_state(supabase, athlete_id)
    synced = activities_db.count_activities(supabase, athlete_id)
    if row is None:
        return SyncStatusResponse(status="never_synced", progress=0, synced=synced)
    return SyncStatusResponse(
        status=row["status"],
        progress=row["progress"],
        synced=synced,
        last_backfill_at=row["last_backfill_at"],
        last_sync_at=row["last_sync_at"],
    )


def start_backfill(
    supabase: httpx.Client, athlete_id: int
) -> tuple[SyncStatusResponse, bool]:
    row = sync_state_db.get_sync_state(supabase, athlete_id)
    already_running = row is not None and row["status"] == "backfilling"
    if not already_running:
        sync_state_db.upsert_sync_state(
            supabase, athlete_id, {"status": "backfilling", "progress": 0}
        )
    return get_status(supabase, athlete_id), not already_running


def run_backfill(settings: Settings, athlete_id: int) -> None:
    supabase = build_supabase(settings)
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
        now = datetime.now(timezone.utc).isoformat()
        sync_state_db.upsert_sync_state(
            supabase, athlete_id,
            {"status": "idle", "progress": 100,
             "last_backfill_at": now, "last_sync_at": now},
        )
    except Exception:
        logger.exception("Backfill failed for athlete %s", athlete_id)
        sync_state_db.upsert_sync_state(supabase, athlete_id, {"status": "error"})
    finally:
        supabase.close()
        strava.close()
```

- [ ] **Step 5: Run the service tests to verify they pass**

Run: `cd backend && python -m pytest tests/services/test_sync.py -v`
Expected: all pass.

- [ ] **Step 6: Write the failing router tests**

Create `backend/tests/routers/test_sync.py`:
```python
from app.services import sync as sync_service
from app.session import SESSION_COOKIE, sign_session
from app.models.sync import SyncStatusResponse


def _auth(client):
    client.cookies.set(SESSION_COOKIE, sign_session(99, "test-secret"))


def test_status_requires_session(client):
    assert client.get("/sync/status").status_code == 401


def test_status_returns_body(client, monkeypatch):
    monkeypatch.setattr(sync_service, "get_status",
                        lambda supabase, athlete_id: SyncStatusResponse(
                            status="idle", progress=100, synced=42))
    _auth(client)
    response = client.get("/sync/status")
    assert response.status_code == 200
    assert response.json()["synced"] == 42


def test_start_schedules_backfill_when_started(client, monkeypatch):
    spawned = {}
    monkeypatch.setattr(sync_service, "start_backfill",
                        lambda supabase, athlete_id: (
                            SyncStatusResponse(status="backfilling", progress=0, synced=0), True))
    monkeypatch.setattr(sync_service, "run_backfill",
                        lambda settings, athlete_id: spawned.update(athlete=athlete_id))
    _auth(client)
    response = client.post("/sync/start")
    assert response.status_code == 200
    assert response.json()["status"] == "backfilling"
    assert spawned == {"athlete": 99}


def test_start_does_not_reschedule_when_already_running(client, monkeypatch):
    monkeypatch.setattr(sync_service, "start_backfill",
                        lambda supabase, athlete_id: (
                            SyncStatusResponse(status="backfilling", progress=30, synced=5), False))

    def fail(settings, athlete_id):
        raise AssertionError("must not spawn a second backfill")

    monkeypatch.setattr(sync_service, "run_backfill", fail)
    _auth(client)
    assert client.post("/sync/start").status_code == 200
```

- [ ] **Step 7: Run the router tests to verify they fail**

Run: `cd backend && python -m pytest tests/routers/test_sync.py -v`
Expected: FAIL — 404s (router not registered).

- [ ] **Step 8: Implement the router and register it**

Create `backend/app/routers/sync.py`:
```python
from fastapi import APIRouter, BackgroundTasks, Depends

from app.config import Settings, get_settings
from app.deps import get_current_athlete_id, get_supabase
from app.models.sync import SyncStatusResponse
from app.services import sync as sync_service

router = APIRouter()


@router.get("/status", response_model=SyncStatusResponse)
def status(
    athlete_id: int = Depends(get_current_athlete_id),
    supabase=Depends(get_supabase),
) -> SyncStatusResponse:
    return sync_service.get_status(supabase, athlete_id)


@router.post("/start", response_model=SyncStatusResponse)
def start(
    background_tasks: BackgroundTasks,
    athlete_id: int = Depends(get_current_athlete_id),
    supabase=Depends(get_supabase),
    settings: Settings = Depends(get_settings),
) -> SyncStatusResponse:
    result, started = sync_service.start_backfill(supabase, athlete_id)
    if started:
        background_tasks.add_task(sync_service.run_backfill, settings, athlete_id)
    return result
```

In `backend/app/main.py` change the routers import to `from app.routers import athletes, auth, health, sync` and add after the athletes include:
```python
    app.include_router(sync.router, prefix="/sync")
```

- [ ] **Step 9: Run the full backend suite to verify it passes**

Run: `cd backend && python -m pytest -v`
Expected: all pass (incl. `test_architecture.py`).

- [ ] **Step 10: Lint, type-check, commit**

```bash
cd backend && ruff check . && mypy
git add backend/app/models/sync.py backend/app/services/sync.py backend/app/routers/sync.py backend/app/main.py backend/tests/services/test_sync.py backend/tests/routers/test_sync.py
git commit -m "feat(backend): backfill worker + GET /sync/status + POST /sync/start"
```

---

## Task 6: unified design system — tokens, Archivo body, keyframes (frontend)

**Files:**
- Modify: `frontend/src/index.css`
- Verify: existing `frontend/src/pages/landing/LandingPage.test.tsx`, `frontend/src/App.test.tsx`

**Interfaces:**
- Produces: new Tailwind color utilities (`bg-surface-panel2`, `bg-surface-sidebar`, `border-line2`, `border-line-strong`, `text-ink2`, `text-ink-hi`, `text-muted2`, `text-muted5`, `text-good`/`bg-good-soft`, `text-bad`/`bg-bad-soft`, `bg-strava-soft`, `bg-track`, `bg-skel`, `bg-overlay`, chart token `--color-chartgrid`); `font-sans` = Archivo; animation utility classes `.animate-pkspin/.animate-pkskel/.animate-pkshimmer/.animate-pkpulse/.animate-pkrise`. No new utilities renamed away from existing ones (`text-ink`, `text-body`, `text-subtle`, `text-faint`, `bg-surface-page`, `bg-surface-card`, `bg-surface-inset`, `text-strava` all keep their meaning).

> Note: Archivo, Space Grotesk, and JetBrains Mono are already loaded in `frontend/index.html`; no font-link change is needed.

- [ ] **Step 1: Add the new palette variables**

In `frontend/src/index.css`, inside the `:root` block (after `--line-subtle`), add:
```css
    /* Extended dashboard palette — light */
    --panel2: #f6f5ef;
    --sidebar: #eeede7;
    --border2: rgba(0, 0, 0, 0.06);
    --border-strong: rgba(0, 0, 0, 0.14);
    --text2: #22262d;
    --text-hi: #3a414b;
    --muted2: #6b7480;
    --muted5: #a0a6ae;
    --good: #1f9d63;
    --good-soft: rgba(31, 157, 99, 0.12);
    --bad: #d9534f;
    --bad-soft: rgba(217, 83, 79, 0.12);
    --accent-soft: rgba(252, 76, 2, 0.12);
    --track: rgba(0, 0, 0, 0.12);
    --chartgrid: rgba(0, 0, 0, 0.08);
    --overlay: rgba(244, 243, 238, 0.78);
    --skel: rgba(0, 0, 0, 0.06);
```
Inside the `.dark` block (after `--line-subtle`), add:
```css
    /* Extended dashboard palette — dark */
    --panel2: #0e1116;
    --sidebar: #0a0c10;
    --border2: rgba(255, 255, 255, 0.06);
    --border-strong: rgba(255, 255, 255, 0.1);
    --text2: #e6e9ee;
    --text-hi: #c4cad4;
    --muted2: #8b93a1;
    --muted5: #5b6472;
    --good: #34d399;
    --good-soft: rgba(52, 211, 153, 0.13);
    --bad: #f87171;
    --bad-soft: rgba(248, 113, 113, 0.12);
    --accent-soft: rgba(252, 76, 2, 0.12);
    --track: rgba(255, 255, 255, 0.09);
    --chartgrid: rgba(255, 255, 255, 0.05);
    --overlay: rgba(8, 10, 13, 0.74);
    --skel: rgba(255, 255, 255, 0.06);
```

- [ ] **Step 2: Expose the new tokens + Archivo via `@theme inline`**

In the `@theme inline` block of `frontend/src/index.css`, after `--font-mono: ...`, add:
```css
  --font-sans: "Archivo", -apple-system, sans-serif;
```
Also after the existing `--color-strava-glow: ...;` line, add the (theme-invariant) Strava accent shades the dashboard uses, so components never need raw hex:
```css
  --color-strava-deep: #b8370a;
  --color-strava-light: #ff7a3d;
  --color-strava-hover: #e34602;
```
And after `--color-line-subtle: var(--line-subtle);`, add:
```css
  --color-surface-panel2: var(--panel2);
  --color-surface-sidebar: var(--sidebar);
  --color-line2: var(--border2);
  --color-line-strong: var(--border-strong);
  --color-ink2: var(--text2);
  --color-ink-hi: var(--text-hi);
  --color-muted2: var(--muted2);
  --color-muted5: var(--muted5);
  --color-good: var(--good);
  --color-good-soft: var(--good-soft);
  --color-bad: var(--bad);
  --color-bad-soft: var(--bad-soft);
  --color-strava-soft: var(--accent-soft);
  --color-track: var(--track);
  --color-chartgrid: var(--chartgrid);
  --color-overlay: var(--overlay);
  --color-skel: var(--skel);
```

- [ ] **Step 3: Apply the Archivo body font**

In the `@layer base` block that styles `body`, change it to:
```css
  body {
    background-color: var(--background);
    color: var(--foreground);
    font-family: var(--font-sans);
  }
```

- [ ] **Step 4: Add the sync/skeleton keyframes + animation utilities**

At the end of `frontend/src/index.css`, append:
```css
/* ── Sync + skeleton animations ──────────────────────────── */
@keyframes pkpulse { 0%, 100% { transform: scale(1); opacity: 1; } 50% { transform: scale(0.55); opacity: 0.5; } }
@keyframes pkspin { to { transform: rotate(360deg); } }
@keyframes pkshimmer { 0% { transform: translateX(-120%); } 100% { transform: translateX(420%); } }
@keyframes pkskel { 0%, 100% { opacity: 0.5; } 50% { opacity: 0.85; } }
@keyframes pkrise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

.animate-pkpulse { animation: pkpulse 1.2s ease-in-out infinite; }
.animate-pkspin { animation: pkspin 0.7s linear infinite; }
.animate-pkshimmer { animation: pkshimmer 1.5s linear infinite; }
.animate-pkskel { animation: pkskel 1.6s ease-in-out infinite; }
.animate-pkrise { animation: pkrise 0.35s ease both; }
```

- [ ] **Step 5: Verify build + existing tests (landing now renders on Archivo)**

Run: `cd frontend && npm run build && npm test`
Expected: build succeeds; all existing tests pass (landing + App + router). The landing page now inherits Archivo and shares the unified token layer — visually confirm in `npm run dev` if convenient.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat(frontend): unify design system tokens + Archivo body + sync keyframes"
```

---

## Task 7: TanStack Query foundation + `useAthlete` migration (frontend)

**Files:**
- Modify: `frontend/package.json` (add dep), `frontend/src/App.tsx`, `frontend/src/api/auth.ts`
- Create: `frontend/src/app/providers/QueryProvider.tsx`, `frontend/src/test/providers.tsx`
- Test: `frontend/src/api/auth.test.ts` (append a hook test)

**Interfaces:**
- Produces: `QueryProvider` component; `useAthlete()` returning `{ data: Athlete | null; isLoading: boolean; error: Error | null }` backed by `useQuery` (key `['athlete']`); test helper `renderWithProviders(ui)` and `createQueryWrapper()` in `src/test/providers.tsx`.
- Consumes: `fetchAthlete` (existing in `api/auth.ts`).

- [ ] **Step 1: Install TanStack Query**

Run: `cd frontend && npm install @tanstack/react-query`
Expected: `@tanstack/react-query` (v5.x) added to `package.json` dependencies.

- [ ] **Step 2: Create the QueryProvider**

Create `frontend/src/app/providers/QueryProvider.tsx`:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, refetchOnWindowFocus: false },
  },
});

export function QueryProvider({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
```

- [ ] **Step 3: Wrap the app**

Replace `frontend/src/App.tsx` with:
```tsx
import { RouterProvider } from "react-router/dom";
import { QueryProvider } from "@/app/providers/QueryProvider";
import { ThemeProvider } from "@/app/providers/ThemeProvider";
import { router } from "@/app/router";

export default function App() {
  return (
    <QueryProvider>
      <ThemeProvider>
        <RouterProvider router={router} />
      </ThemeProvider>
    </QueryProvider>
  );
}
```

- [ ] **Step 4: Create the shared test provider helper**

Create `frontend/src/test/providers.tsx`:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { ThemeProvider } from "@/app/providers/ThemeProvider";

/** A fresh QueryClient per call so tests never share cache. */
export function createQueryWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <ThemeProvider>{children}</ThemeProvider>
      </QueryClientProvider>
    );
  };
}

export function renderWithProviders(ui: ReactElement, options?: RenderOptions) {
  return render(ui, { wrapper: createQueryWrapper(), ...options });
}
```

- [ ] **Step 5: Write the failing `useAthlete` hook test**

Append to `frontend/src/api/auth.test.ts`:
```ts
import { renderHook, waitFor } from "@testing-library/react";
import { createQueryWrapper } from "@/test/providers";
import { useAthlete } from "./auth";

describe("useAthlete", () => {
  it("loads the athlete via react-query", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(athlete), {
          status: 200,
          headers: { "content-type": "application/json" },
        })
      )
    );
    const { result } = renderHook(() => useAthlete(), {
      wrapper: createQueryWrapper(),
    });
    await waitFor(() => expect(result.current.data).toEqual(athlete));
    expect(result.current.error).toBeNull();
  });
});
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/api/auth.test.ts`
Expected: FAIL — `useAthlete` still uses `useState`/`useEffect`; `result.current.data` shape mismatch or hook errors without a QueryClient. (It must fail before the migration.)

- [ ] **Step 7: Migrate `useAthlete` to `useQuery`**

In `frontend/src/api/auth.ts`, replace the `import { useEffect, useState } from "react";` line with:
```ts
import { useQuery } from "@tanstack/react-query";
```
and replace the entire `UseAthlete` type + `useAthlete` function with:
```ts
export type UseAthlete = {
  data: Athlete | null;
  isLoading: boolean;
  error: Error | null;
};

/** Loads the current athlete; a 401 surfaces as `error` (no retry). */
export function useAthlete(): UseAthlete {
  const { data, isLoading, error } = useQuery({
    queryKey: ["athlete"],
    queryFn: fetchAthlete,
  });
  return { data: data ?? null, isLoading, error: (error as Error) ?? null };
}
```

- [ ] **Step 8: Run the frontend suite to verify it passes**

Run: `cd frontend && npm test`
Expected: all pass (the new hook test, the existing `auth.test.ts` cases, `AppHome.test.tsx` which mocks `useAthlete`, `App.test.tsx`, `router.test.tsx`).

- [ ] **Step 9: Lint, build, commit**

```bash
cd frontend && npm run lint && npm run build
git add frontend/package.json frontend/package-lock.json frontend/src/App.tsx frontend/src/app/providers/QueryProvider.tsx frontend/src/test/providers.tsx frontend/src/api/auth.ts frontend/src/api/auth.test.ts
git commit -m "feat(frontend): adopt TanStack Query; migrate useAthlete"
```

---

## Task 8: shared app shell — Sidebar, Topbar, AppShell (frontend)

**Files:**
- Create: `frontend/src/components/app-shell/Sidebar.tsx`, `frontend/src/components/app-shell/Topbar.tsx`, `frontend/src/components/app-shell/AppShell.tsx`
- Test: `frontend/src/components/app-shell/AppShell.test.tsx`

**Interfaces:**
- Consumes: `Logo` (`@/components/Logo`), `ThemeToggle` (`@/components/ThemeToggle`), `Athlete` (`@/types/athlete`), `useTheme` (via ThemeToggle).
- Produces (presentational, props only — no data fetching inside):
  - `Sidebar({ navActive: string; athlete: Athlete | null; syncLabel: string; onLogout: () => void })`
  - `Topbar({ title: string; subtitle?: string; right?: ReactNode })`
  - `AppShell({ navActive, athlete, syncLabel, onLogout, title, subtitle?, headerRight?, children })`
- Nav labels (fixed order): `Overview`, `Activities`, `Segments`, `Trends`, `Goals`. Only the one matching `navActive` is highlighted; the rest render muted/non-interactive in 3a.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/app-shell/AppShell.test.tsx`:
```tsx
import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/providers";
import { AppShell } from "./AppShell";

const athlete = {
  id: 99, name: "Ada Lovelace", avatar_url: null,
  settings: { units: "metric", theme: "dark", default_period: "week" },
};

describe("AppShell", () => {
  it("renders nav, title, and the athlete name", () => {
    renderWithProviders(
      <AppShell navActive="Overview" athlete={athlete} syncLabel="Up to date"
        onLogout={() => {}} title="Overview">
        <div>body</div>
      </AppShell>
    );
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Activities")).toBeInTheDocument();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("body")).toBeInTheDocument();
  });

  it("calls onLogout when the logout button is clicked", () => {
    const onLogout = vi.fn();
    renderWithProviders(
      <AppShell navActive="Overview" athlete={athlete} syncLabel="Up to date"
        onLogout={onLogout} title="Overview">
        <div>body</div>
      </AppShell>
    );
    fireEvent.click(screen.getByRole("button", { name: /log out/i }));
    expect(onLogout).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/app-shell/AppShell.test.tsx`
Expected: FAIL — cannot resolve `./AppShell`.

- [ ] **Step 3: Implement Sidebar**

Create `frontend/src/components/app-shell/Sidebar.tsx`:
```tsx
import { LogOut } from "lucide-react";
import { Logo } from "@/components/Logo";
import type { Athlete } from "@/types/athlete";

const NAV_ITEMS = ["Overview", "Activities", "Segments", "Trends", "Goals"];

function initials(name: string): string {
  return name.split(" ").map((p) => p[0]).filter(Boolean).slice(0, 2).join("").toUpperCase();
}

export function Sidebar({
  navActive,
  athlete,
  syncLabel,
  onLogout,
}: {
  navActive: string;
  athlete: Athlete | null;
  syncLabel: string;
  onLogout: () => void;
}) {
  return (
    <div className="w-[236px] flex-none border-r border-line2 flex flex-col p-[22px_16px] bg-surface-sidebar max-[760px]:hidden">
      <div className="px-2 mb-[30px]">
        <Logo />
      </div>
      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map((label) => {
          const active = label === navActive;
          return (
            <div
              key={label}
              className={`flex items-center gap-[11px] px-[11px] py-[9px] rounded-[9px] ${
                active ? "bg-strava-soft" : ""
              }`}
            >
              <span
                className={`w-[6px] h-[6px] rounded-full ${
                  active ? "bg-strava" : "bg-muted5"
                }`}
              />
              <span
                className={`text-[14px] font-medium ${
                  active ? "text-ink2" : "text-subtle"
                }`}
              >
                {label}
              </span>
            </div>
          );
        })}
      </nav>
      <div className="flex-1" />
      <div className="border-t border-line2 pt-4 flex items-center gap-[11px]">
        {athlete?.avatar_url ? (
          <img
            src={athlete.avatar_url}
            alt=""
            aria-hidden
            className="w-9 h-9 rounded-full object-cover flex-none"
          />
        ) : (
          <div className="w-9 h-9 rounded-full flex-none flex items-center justify-center font-display font-semibold text-[14px] text-white bg-gradient-to-br from-strava to-strava-deep">
            {athlete ? initials(athlete.name) : "--"}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="text-[13px] font-medium text-ink2 truncate">
            {athlete?.name ?? "…"}
          </div>
          <div className="font-mono text-[10px] text-faint flex items-center gap-[5px]">
            <span className="w-[6px] h-[6px] rounded-full bg-strava" />
            {syncLabel}
          </div>
        </div>
        <button
          title="Log out"
          aria-label="Log out"
          onClick={onLogout}
          className="w-8 h-8 flex-none rounded-[8px] bg-transparent border border-line text-body cursor-pointer flex items-center justify-center transition-colors hover:text-strava hover:border-strava/40"
        >
          <LogOut size={16} aria-hidden />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Implement Topbar**

Create `frontend/src/components/app-shell/Topbar.tsx`:
```tsx
import type { ReactNode } from "react";
import { ThemeToggle } from "@/components/ThemeToggle";

export function Topbar({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <div className="h-[70px] flex-none border-b border-line2 flex items-center justify-between px-8">
      <div className="flex items-center gap-[14px]">
        <h1 className="font-display font-semibold text-[22px] m-0 tracking-[-0.01em] text-ink">
          {title}
        </h1>
        {subtitle ? (
          <span className="font-mono text-[11px] text-faint">{subtitle}</span>
        ) : null}
      </div>
      <div className="flex items-center gap-[14px]">
        {right}
        <ThemeToggle />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Implement AppShell**

Create `frontend/src/components/app-shell/AppShell.tsx`:
```tsx
import type { ReactNode } from "react";
import type { Athlete } from "@/types/athlete";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell({
  navActive,
  athlete,
  syncLabel,
  onLogout,
  title,
  subtitle,
  headerRight,
  children,
}: {
  navActive: string;
  athlete: Athlete | null;
  syncLabel: string;
  onLogout: () => void;
  title: string;
  subtitle?: string;
  headerRight?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="relative flex min-h-screen h-screen bg-surface-page text-ink overflow-hidden">
      <Sidebar navActive={navActive} athlete={athlete} syncLabel={syncLabel} onLogout={onLogout} />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar title={title} subtitle={subtitle} right={headerRight} />
        <div className="flex-1 min-h-0 relative overflow-hidden">{children}</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/app-shell/AppShell.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 7: Lint, build, commit**

```bash
cd frontend && npm run lint && npm run build
git add frontend/src/components/app-shell
git commit -m "feat(frontend): shared app shell (sidebar + topbar)"
```

---

## Task 9: sync types + api hooks (frontend)

**Files:**
- Create: `frontend/src/types/sync.ts`, `frontend/src/api/sync.ts`
- Test: `frontend/src/api/sync.test.ts`

**Interfaces:**
- Produces:
  - `SyncStatusValue` union + `SyncStatus` type (`{ status, progress, synced, last_backfill_at, last_sync_at }`).
  - `fetchSyncStatus(): Promise<SyncStatus>`, `startSync(): Promise<SyncStatus>`, `refreshSync(): Promise<{ synced: number }>`.
  - `SYNC_POLL_MS` (number), `syncRefetchInterval(status?: SyncStatus): number | false`.
  - `useSyncStatus()` (`useQuery`, key `['sync','status']`), `useStartSync()`, `useRefreshSync()` (mutations invalidating `['sync','status']`).
- Consumes: `apiFetch` (`@/api/client`), TanStack Query.

- [ ] **Step 1: Add the type**

Create `frontend/src/types/sync.ts`:
```ts
export type SyncStatusValue = "never_synced" | "backfilling" | "idle" | "error";

export type SyncStatus = {
  status: SyncStatusValue;
  progress: number;
  synced: number;
  last_backfill_at: string | null;
  last_sync_at: string | null;
};
```

- [ ] **Step 2: Write the failing test**

Create `frontend/src/api/sync.test.ts`:
```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SyncStatus } from "@/types/sync";
import { fetchSyncStatus, refreshSync, startSync, syncRefetchInterval, SYNC_POLL_MS } from "./sync";

afterEach(() => vi.restoreAllMocks());

const status: SyncStatus = {
  status: "backfilling", progress: 40, synced: 88,
  last_backfill_at: null, last_sync_at: null,
};

describe("sync api", () => {
  it("fetchSyncStatus GETs /sync/status with credentials", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(status), {
        status: 200, headers: { "content-type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(fetchSyncStatus()).resolves.toEqual(status);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/sync/status"),
      expect.objectContaining({ credentials: "include" })
    );
  });

  it("startSync POSTs /sync/start", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(status), {
        status: 200, headers: { "content-type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);
    await startSync();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/sync/start"),
      expect.objectContaining({ method: "POST", credentials: "include" })
    );
  });

  it("refreshSync POSTs /sync/refresh", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ synced: 3 }), {
        status: 200, headers: { "content-type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(refreshSync()).resolves.toEqual({ synced: 3 });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/sync/refresh"),
      expect.objectContaining({ method: "POST", credentials: "include" })
    );
  });

  it("polls only while backfilling", () => {
    expect(syncRefetchInterval(status)).toBe(SYNC_POLL_MS);
    expect(syncRefetchInterval({ ...status, status: "idle" })).toBe(false);
    expect(syncRefetchInterval(undefined)).toBe(false);
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/api/sync.test.ts`
Expected: FAIL — cannot resolve `./sync`.

- [ ] **Step 4: Implement the api module**

Create `frontend/src/api/sync.ts`:
```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { SyncStatus } from "@/types/sync";
import { apiFetch } from "./client";

export const SYNC_POLL_MS = 1500;

export function fetchSyncStatus(): Promise<SyncStatus> {
  return apiFetch<SyncStatus>("/sync/status");
}

export function startSync(): Promise<SyncStatus> {
  return apiFetch<SyncStatus>("/sync/start", { method: "POST" });
}

export function refreshSync(): Promise<{ synced: number }> {
  return apiFetch<{ synced: number }>("/sync/refresh", { method: "POST" });
}

/** Poll every SYNC_POLL_MS while a backfill is running; otherwise stop. */
export function syncRefetchInterval(status?: SyncStatus): number | false {
  return status?.status === "backfilling" ? SYNC_POLL_MS : false;
}

export function useSyncStatus() {
  return useQuery({
    queryKey: ["sync", "status"],
    queryFn: fetchSyncStatus,
    refetchInterval: (query) => syncRefetchInterval(query.state.data),
  });
}

export function useStartSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: startSync,
    onSuccess: (data) => {
      queryClient.setQueryData(["sync", "status"], data);
    },
  });
}

export function useRefreshSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: refreshSync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sync", "status"] });
    },
  });
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/api/sync.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 6: Lint, build, commit**

```bash
cd frontend && npm run lint && npm run build
git add frontend/src/types/sync.ts frontend/src/api/sync.ts frontend/src/api/sync.test.ts
git commit -m "feat(frontend): sync api module + status/start/refresh hooks"
```

---

## Task 10: sync screen + route (frontend)

**Files:**
- Create: `frontend/src/pages/sync/SyncPage.tsx`, `frontend/src/pages/sync/SyncPage.test.tsx`
- Modify: `frontend/src/app/router.tsx`

**Interfaces:**
- Consumes: `useSyncStatus`/`useStartSync` (`@/api/sync`), `useAthlete`/`logout` (`@/api/auth`), `AppShell` (`@/components/app-shell/AppShell`), `useNavigate` (`react-router`).
- Produces: default-exported `SyncPage` mounted at `/sync`. Faithful port of `docs/design/Peakstats Sync.dc.html` (overlay layout). States: backfilling (progress + 4-stage checklist), `ready` (done → "Go to dashboard" → `/home`), `empty` (idle + 0 synced → "Refresh from Strava" / "Skip" → `/home`), `error` (retry → re-run start).

> Optional: vendor the source for reference with the design MCP — `DesignSync get_file` `Peakstats Sync.dc.html` from project `646622a9-126e-4e80-b91c-8b2ccf507529` into `docs/design/`. Not required; the full component is below.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/pages/sync/SyncPage.test.tsx`:
```tsx
import { fireEvent, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/providers";

const mockNavigate = vi.fn();
vi.mock("react-router", async () => {
  const actual = await vi.importActual<typeof import("react-router")>("react-router");
  return { ...actual, useNavigate: () => mockNavigate };
});

const startMutate = vi.fn();
const useSyncStatus = vi.fn();
vi.mock("@/api/sync", () => ({
  useSyncStatus: () => useSyncStatus(),
  useStartSync: () => ({ mutate: startMutate }),
}));

vi.mock("@/api/auth", () => ({
  useAthlete: () => ({ data: { id: 1, name: "Ada", avatar_url: null,
    settings: { units: "metric", theme: "dark", default_period: "week" } },
    isLoading: false, error: null }),
  logout: vi.fn(),
}));

import SyncPage from "./SyncPage";

function renderPage() {
  renderWithProviders(<MemoryRouter><SyncPage /></MemoryRouter>);
}

afterEach(() => vi.clearAllMocks());

describe("SyncPage", () => {
  it("starts the backfill on mount", () => {
    useSyncStatus.mockReturnValue({ data: { status: "never_synced", progress: 0, synced: 0,
      last_backfill_at: null, last_sync_at: null } });
    renderPage();
    expect(startMutate).toHaveBeenCalled();
  });

  it("shows progress while backfilling", () => {
    useSyncStatus.mockReturnValue({ data: { status: "backfilling", progress: 40, synced: 88,
      last_backfill_at: null, last_sync_at: null } });
    renderPage();
    expect(screen.getByText("40")).toBeInTheDocument();
    expect(screen.getByText(/importing your rides/i)).toBeInTheDocument();
  });

  it("shows Go to dashboard when done and navigates home", () => {
    useSyncStatus.mockReturnValue({ data: { status: "idle", progress: 100, synced: 218,
      last_backfill_at: "T", last_sync_at: "T" } });
    renderPage();
    const cta = screen.getByRole("button", { name: /go to dashboard/i });
    fireEvent.click(cta);
    expect(mockNavigate).toHaveBeenCalledWith("/home");
  });

  it("shows the empty state when no rides were found", () => {
    useSyncStatus.mockReturnValue({ data: { status: "idle", progress: 100, synced: 0,
      last_backfill_at: "T", last_sync_at: "T" } });
    renderPage();
    expect(screen.getByText(/no rides found/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /refresh from strava/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/sync/SyncPage.test.tsx`
Expected: FAIL — cannot resolve `./SyncPage`.

- [ ] **Step 3: Implement SyncPage**

Create `frontend/src/pages/sync/SyncPage.tsx`:
```tsx
import { Check } from "lucide-react";
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router";
import { logout, useAthlete } from "@/api/auth";
import { useStartSync, useSyncStatus } from "@/api/sync";
import { AppShell } from "@/components/app-shell/AppShell";

const STAGE_DEFS = [
  { label: "Connect your Strava account", start: 0 },
  { label: "Fetch activity history", start: 8 },
  { label: "Process ride metrics", start: 55 },
  { label: "Build your stats", start: 86 },
];

export default function SyncPage() {
  const navigate = useNavigate();
  const { data: athlete } = useAthlete();
  const { data: status } = useSyncStatus();
  const start = useStartSync();
  const started = useRef(false);

  useEffect(() => {
    if (!started.current) {
      started.current = true;
      start.mutate();
    }
  }, [start]);

  const pct = status?.progress ?? 0;
  const synced = status?.synced ?? 0;
  const state = status?.status ?? "never_synced";
  const isError = state === "error";
  const isDone = state === "idle" && synced > 0;
  const isEmpty = state === "idle" && synced === 0;
  const isSyncing = !isError && !isDone && !isEmpty;

  const activeIdx = isDone
    ? STAGE_DEFS.length
    : STAGE_DEFS.reduce((acc, s, i) => (pct >= s.start ? i : acc), 0);

  const handleLogout = async () => {
    await logout();
    navigate("/", { replace: true });
  };

  return (
    <AppShell
      navActive="Overview"
      athlete={athlete}
      syncLabel={isDone ? "Up to date" : isEmpty ? "No rides yet" : "Syncing…"}
      onLogout={handleLogout}
      title="Setting up your dashboard"
      subtitle="FIRST SYNC"
    >
      {/* blurred skeleton backdrop */}
      <div className="absolute inset-0 p-7 blur-[1.5px] opacity-60 pointer-events-none">
        <div className="grid grid-cols-4 gap-4 mb-[18px]">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="bg-surface-card border border-line rounded-2xl p-5">
              <div className="h-[9px] w-[54px] rounded bg-skel mb-4 animate-pkskel" />
              <div className="h-[26px] w-[88px] rounded bg-skel mb-[14px] animate-pkskel" />
              <div className="h-4 w-[46px] rounded-full bg-skel animate-pkskel" />
            </div>
          ))}
        </div>
        <div className="bg-surface-card border border-line rounded-2xl p-5 mb-[18px]">
          <div className="h-[11px] w-[150px] rounded bg-skel mb-5 animate-pkskel" />
          <div className="h-[180px] rounded-[10px] bg-skel animate-pkskel" />
        </div>
      </div>

      {/* overlay card */}
      <div className="absolute inset-0 bg-overlay flex items-center justify-center p-6">
        <div className="w-[480px] max-w-full bg-surface-card border border-line-strong rounded-[20px] p-[32px_32px_30px] shadow-[0_30px_80px_rgba(0,0,0,0.45)]">
          <div className="flex items-center gap-[11px] mb-6">
            <div className="w-[30px] h-[30px] rounded-[8px] bg-strava flex items-center justify-center flex-none">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="#fff" aria-hidden>
                <path d="M8.6 0 3.2 10.6h3.2L8.6 6.2l2.2 4.4h3.2L8.6 0z" />
                <path d="M13.6 10.6 12 13.8l1.6 3.2 3.2-6.4h-3.2z" />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[13.5px] font-medium text-ink2">Connected to Strava</div>
              <div className="font-mono text-[10.5px] text-faint">
                {athlete?.name ?? "athlete"} · authorized
              </div>
            </div>
            <span className="flex items-center gap-[5px] font-mono text-[10px] text-good bg-good-soft px-[10px] py-[5px] rounded-full">
              <Check size={11} aria-hidden /> LINKED
            </span>
          </div>

          <div className="font-display font-semibold text-[21px] tracking-[-0.01em] mb-[6px] text-ink">
            {isEmpty ? "No rides found" : isDone ? "You're all set" : "Importing your rides"}
          </div>
          <div className="text-[13.5px] leading-[1.55] text-body mb-6">
            {isEmpty
              ? "Your Strava account is linked, but there's nothing to import yet."
              : isDone
                ? `We imported ${synced} activities and crunched your stats. Your dashboard is ready.`
                : "Hang tight while we pull your full ride history from Strava and build your analytics. This usually takes under a minute."}
          </div>

          {isEmpty ? (
            <div className="flex gap-[10px]">
              <button
                onClick={() => start.mutate()}
                className="flex-1 h-[46px] rounded-[11px] border-none bg-strava text-white font-display font-semibold text-[14px] cursor-pointer hover:bg-strava-hover"
              >
                Refresh from Strava
              </button>
              <button
                onClick={() => navigate("/home")}
                className="flex-none px-[18px] h-[46px] rounded-[11px] border border-line-strong bg-transparent text-ink2 font-display font-medium text-[14px] cursor-pointer hover:border-strava/40"
              >
                Skip
              </button>
            </div>
          ) : (
            <>
              <div className="flex items-baseline justify-between mb-[11px]">
                <div className="flex items-baseline gap-2">
                  <span className="font-display font-semibold text-[34px] leading-none tracking-[-0.02em] text-ink">
                    {Math.round(pct)}
                  </span>
                  <span className="font-mono text-[12px] text-muted2">%</span>
                </div>
                <span className="font-mono text-[11.5px] text-subtle">
                  {synced} activities
                </span>
              </div>

              <div className="h-[10px] rounded-full bg-track overflow-hidden relative mb-[26px]">
                <div
                  className="h-full bg-gradient-to-r from-strava to-strava-light rounded-full relative overflow-hidden transition-[width] duration-200"
                  style={{ width: `${pct}%` }}
                >
                  {isSyncing ? (
                    <div className="absolute top-0 left-0 h-full w-[60px] bg-gradient-to-r from-transparent via-white/45 to-transparent animate-pkshimmer" />
                  ) : null}
                </div>
              </div>

              <div className="flex flex-col gap-[3px] mb-[26px]">
                {STAGE_DEFS.map((stage, i) => {
                  const done = isDone || i < activeIdx;
                  const active = !isDone && i === activeIdx;
                  return (
                    <div key={stage.label} className="flex items-center gap-3 px-1 py-2">
                      <span className="w-[22px] h-[22px] flex-none flex items-center justify-center">
                        {done ? (
                          <span className="w-[22px] h-[22px] rounded-full bg-strava flex items-center justify-center">
                            <Check size={12} color="#fff" aria-hidden />
                          </span>
                        ) : active ? (
                          <span className="w-[18px] h-[18px] rounded-full border-[2.5px] border-strava-soft border-t-strava animate-pkspin" />
                        ) : (
                          <span className="w-4 h-4 rounded-full border-2 border-track" />
                        )}
                      </span>
                      <span
                        className={`flex-1 text-[13.5px] font-medium ${
                          done || active ? "text-ink2" : "text-subtle"
                        }`}
                      >
                        {stage.label}
                      </span>
                      <span className="font-mono text-[10.5px] text-faint">
                        {done ? "done" : active ? "in progress" : "waiting"}
                      </span>
                    </div>
                  );
                })}
              </div>

              {isError ? (
                <button
                  onClick={() => start.mutate()}
                  className="w-full h-[46px] rounded-[11px] border-none bg-strava text-white font-display font-semibold text-[14.5px] cursor-pointer hover:bg-strava-hover"
                >
                  Sync failed — retry
                </button>
              ) : isDone ? (
                <button
                  onClick={() => navigate("/home")}
                  className="w-full h-[46px] rounded-[11px] border-none bg-strava text-white font-display font-semibold text-[14.5px] cursor-pointer flex items-center justify-center gap-2 hover:bg-strava-hover animate-pkrise"
                >
                  Go to dashboard →
                </button>
              ) : null}
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 4: Add the route**

In `frontend/src/app/router.tsx`, add the import and route. Change the imports to include:
```tsx
import SyncPage from "@/pages/sync/SyncPage";
```
and add to the `routes` array (after the `/home` entry, before the catch-all):
```tsx
  { path: "/sync", element: <SyncPage /> },
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/sync/SyncPage.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 6: Lint, build, commit**

```bash
cd frontend && npm run lint && npm run build
git add frontend/src/pages/sync frontend/src/app/router.tsx
git commit -m "feat(frontend): sync screen (overlay) + /sync route"
```

---

## Task 11: minimal /home Overview shell + sync redirect (frontend)

**Files:**
- Modify: `frontend/src/pages/app-home/AppHome.tsx`, `frontend/src/pages/app-home/AppHome.test.tsx`

**Interfaces:**
- Consumes: `useAthlete`/`logout`/`disconnect` (`@/api/auth`), `useSyncStatus` (`@/api/sync`), `AppShell` (`@/components/app-shell/AppShell`), `useNavigate` (`react-router`).
- Produces: `AppHome` rendered inside `AppShell` (navActive `Overview`). Redirects to `/sync` when status is `never_synced`; redirects to `/` on auth error. Minimal Overview body: placeholder KPI/chart/recent skeleton panels + a "Disconnect Strava" action. (The "Refresh from Strava" button is added in Task 12.)

- [ ] **Step 1: Rewrite the test**

Replace `frontend/src/pages/app-home/AppHome.test.tsx` with:
```tsx
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/providers";

const mockNavigate = vi.fn();
vi.mock("react-router", async () => {
  const actual = await vi.importActual<typeof import("react-router")>("react-router");
  return { ...actual, useNavigate: () => mockNavigate };
});

const useAthlete = vi.fn();
vi.mock("@/api/auth", () => ({
  useAthlete: () => useAthlete(),
  logout: vi.fn(),
  disconnect: vi.fn(),
}));

const useSyncStatus = vi.fn();
vi.mock("@/api/sync", () => ({
  useSyncStatus: () => useSyncStatus(),
}));

import { disconnect, logout } from "@/api/auth";
import AppHome from "./AppHome";

const athlete = {
  id: 99, name: "Ada Lovelace", avatar_url: null,
  settings: { units: "metric", theme: "dark", default_period: "week" },
};

function renderPage() {
  renderWithProviders(<MemoryRouter><AppHome /></MemoryRouter>);
}

afterEach(() => vi.clearAllMocks());

describe("AppHome", () => {
  it("shows the athlete name once synced", () => {
    useAthlete.mockReturnValue({ data: athlete, isLoading: false, error: null });
    useSyncStatus.mockReturnValue({ data: { status: "idle", progress: 100, synced: 200,
      last_backfill_at: "T", last_sync_at: "T" } });
    renderPage();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
  });

  it("redirects to /sync when never synced", async () => {
    useAthlete.mockReturnValue({ data: athlete, isLoading: false, error: null });
    useSyncStatus.mockReturnValue({ data: { status: "never_synced", progress: 0, synced: 0,
      last_backfill_at: null, last_sync_at: null } });
    renderPage();
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/sync", { replace: true }));
  });

  it("redirects to landing when unauthenticated", async () => {
    useAthlete.mockReturnValue({ data: null, isLoading: false, error: new Error("401") });
    useSyncStatus.mockReturnValue({ data: undefined });
    renderPage();
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true }));
  });

  it("logs out from the sidebar", async () => {
    (logout as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    useAthlete.mockReturnValue({ data: athlete, isLoading: false, error: null });
    useSyncStatus.mockReturnValue({ data: { status: "idle", progress: 100, synced: 200,
      last_backfill_at: "T", last_sync_at: "T" } });
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /log out/i }));
    await waitFor(() => expect(logout).toHaveBeenCalled());
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true }));
  });

  it("disconnects from the overview", async () => {
    (disconnect as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    useAthlete.mockReturnValue({ data: athlete, isLoading: false, error: null });
    useSyncStatus.mockReturnValue({ data: { status: "idle", progress: 100, synced: 200,
      last_backfill_at: "T", last_sync_at: "T" } });
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /disconnect/i }));
    await waitFor(() => expect(disconnect).toHaveBeenCalled());
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true }));
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/app-home/AppHome.test.tsx`
Expected: FAIL — current `AppHome` doesn't use `AppShell`/`useSyncStatus`, no `/sync` redirect.

- [ ] **Step 3: Rebuild AppHome**

Replace `frontend/src/pages/app-home/AppHome.tsx` with:
```tsx
import { useEffect } from "react";
import { useNavigate } from "react-router";
import { disconnect, logout, useAthlete } from "@/api/auth";
import { useSyncStatus } from "@/api/sync";
import { AppShell } from "@/components/app-shell/AppShell";

function SkeletonPanels() {
  return (
    <div className="p-7">
      <div className="grid grid-cols-4 gap-4 mb-[18px] max-[1024px]:grid-cols-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="bg-surface-card border border-line rounded-2xl p-5">
            <div className="h-[9px] w-[54px] rounded bg-skel mb-4 animate-pkskel" />
            <div className="h-[26px] w-[88px] rounded bg-skel mb-[14px] animate-pkskel" />
            <div className="h-4 w-[46px] rounded-full bg-skel animate-pkskel" />
          </div>
        ))}
      </div>
      <div className="bg-surface-card border border-line rounded-2xl p-5">
        <div className="h-[11px] w-[150px] rounded bg-skel mb-5 animate-pkskel" />
        <div className="h-[180px] rounded-[10px] bg-skel animate-pkskel" />
      </div>
    </div>
  );
}

export default function AppHome() {
  const { data: athlete, error } = useAthlete();
  const { data: status } = useSyncStatus();
  const navigate = useNavigate();

  useEffect(() => {
    if (error) navigate("/", { replace: true });
  }, [error, navigate]);

  useEffect(() => {
    if (status?.status === "never_synced") navigate("/sync", { replace: true });
  }, [status, navigate]);

  const handleLogout = async () => {
    await logout();
    navigate("/", { replace: true });
  };

  const handleDisconnect = async () => {
    await disconnect();
    navigate("/", { replace: true });
  };

  return (
    <AppShell
      navActive="Overview"
      athlete={athlete}
      syncLabel="Up to date"
      onLogout={handleLogout}
      title="Overview"
      subtitle="UP TO DATE"
    >
      <div className="h-full overflow-y-auto">
        <SkeletonPanels />
        <div className="px-7 pb-10">
          <button
            onClick={handleDisconnect}
            className="font-mono text-[11px] text-faint bg-transparent border-none cursor-pointer hover:text-strava"
          >
            Disconnect Strava
          </button>
        </div>
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/app-home/AppHome.test.tsx`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the full frontend suite**

Run: `cd frontend && npm test`
Expected: all pass.

- [ ] **Step 6: Lint, build, commit**

```bash
cd frontend && npm run lint && npm run build
git add frontend/src/pages/app-home/AppHome.tsx frontend/src/pages/app-home/AppHome.test.tsx
git commit -m "feat(frontend): /home Overview shell + never-synced redirect"
```

---

## Task 12: manual refresh — backend + button (full slice)

**Files:**
- Modify: `backend/app/models/sync.py`, `backend/app/services/sync.py`, `backend/app/routers/sync.py`
- Modify: `frontend/src/pages/app-home/AppHome.tsx`, `frontend/src/pages/app-home/AppHome.test.tsx`
- Test: `backend/tests/services/test_sync.py` (append), `backend/tests/routers/test_sync.py` (append)

**Interfaces:**
- Produces:
  - `app.models.sync.RefreshResponse(synced: int)`.
  - `app.services.sync.refresh(settings, athlete_id) -> RefreshResponse`.
  - Route `POST /sync/refresh` → `RefreshResponse` (502 on Strava/network failure).
  - `AppHome` "Refresh from Strava" button wired to `useRefreshSync` (Task 9).

- [ ] **Step 1: Write the failing backend tests**

Append to `backend/tests/services/test_sync.py`:
```python
def test_refresh_pulls_since_last_sync(monkeypatch):
    captured = {}

    class FakeStrava:
        def list_activities(self, access_token, *, page, per_page=200, after=None):
            captured["after"] = after
            return [] if page > 1 else [{"id": 1, "name": "R", "type": "Ride",
                                         "start_date": "2026-06-20T08:00:00Z", "distance": 1.0,
                                         "moving_time": 1, "elapsed_time": 1,
                                         "total_elevation_gain": 0.0}]

        def close(self):
            pass

    monkeypatch.setattr(sync_service, "build_supabase", lambda settings: object())
    monkeypatch.setattr(sync_service, "build_strava", lambda settings: FakeStrava())
    monkeypatch.setattr(sync_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    monkeypatch.setattr(sync_service.sync_state_db, "get_sync_state",
                        lambda supabase, athlete_id: {"status": "idle", "progress": 100,
                                                      "last_backfill_at": "2026-06-01T00:00:00+00:00",
                                                      "last_sync_at": "2026-06-19T00:00:00+00:00",
                                                      "last_webhook_event_id": None})
    monkeypatch.setattr(sync_service.activities_db, "upsert_activities",
                        lambda supabase, rows: None)
    monkeypatch.setattr(sync_service.sync_state_db, "upsert_sync_state",
                        lambda supabase, athlete_id, fields: None)

    result = sync_service.refresh(settings=object(), athlete_id=7)
    assert result.synced == 1
    assert captured["after"] is not None
```

Append to `backend/tests/routers/test_sync.py`:
```python
from app.models.sync import RefreshResponse


def test_refresh_returns_count(client, monkeypatch):
    monkeypatch.setattr(sync_service, "refresh",
                        lambda settings, athlete_id: RefreshResponse(synced=4))
    _auth(client)
    response = client.post("/sync/refresh")
    assert response.status_code == 200
    assert response.json() == {"synced": 4}


def test_refresh_requires_session(client):
    assert client.post("/sync/refresh").status_code == 401
```

- [ ] **Step 2: Run the backend tests to verify they fail**

Run: `cd backend && python -m pytest tests/services/test_sync.py::test_refresh_pulls_since_last_sync tests/routers/test_sync.py -k refresh -v`
Expected: FAIL — `RefreshResponse`/`refresh`/route not defined.

- [ ] **Step 3: Add the model**

Append to `backend/app/models/sync.py`:
```python
class RefreshResponse(BaseModel):
    synced: int
```

- [ ] **Step 4: Add the refresh service**

In `backend/app/services/sync.py`, update the model import line to:
```python
from app.models.sync import RefreshResponse, SyncStatusResponse
```
and append this function:
```python
def refresh(settings: Settings, athlete_id: int) -> RefreshResponse:
    supabase = build_supabase(settings)
    strava = build_strava(settings)
    try:
        access_token = get_valid_access_token(supabase, strava, athlete_id)
        row = sync_state_db.get_sync_state(supabase, athlete_id)
        after: int | None = None
        if row is not None and row["last_sync_at"] is not None:
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
        now = datetime.now(timezone.utc).isoformat()
        sync_state_db.upsert_sync_state(
            supabase, athlete_id, {"status": "idle", "last_sync_at": now}
        )
        return RefreshResponse(synced=count)
    finally:
        supabase.close()
        strava.close()
```

- [ ] **Step 5: Add the route**

In `backend/app/routers/sync.py`, update the fastapi import line to add `HTTPException`:
```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
```
update the model import to:
```python
from app.models.sync import RefreshResponse, SyncStatusResponse
```
and append the route:
```python
@router.post("/refresh", response_model=RefreshResponse)
def refresh(
    athlete_id: int = Depends(get_current_athlete_id),
    settings: Settings = Depends(get_settings),
) -> RefreshResponse:
    try:
        return sync_service.refresh(settings, athlete_id)
    except Exception as exc:  # noqa: BLE001 - surface upstream failures as 502
        raise HTTPException(status_code=502, detail="Refresh from Strava failed") from exc
```

- [ ] **Step 6: Run the backend suite, lint, type-check, commit**

```bash
cd backend && python -m pytest -v && ruff check . && mypy
git add backend/app/models/sync.py backend/app/services/sync.py backend/app/routers/sync.py backend/tests/services/test_sync.py backend/tests/routers/test_sync.py
git commit -m "feat(backend): manual incremental refresh (POST /sync/refresh)"
```

- [ ] **Step 7: Write the failing frontend test**

Append to `frontend/src/pages/app-home/AppHome.test.tsx` a refresh mock and test. First update the `@/api/sync` mock at the top to include `useRefreshSync`:
```tsx
const refreshMutate = vi.fn();
const useSyncStatus = vi.fn();
vi.mock("@/api/sync", () => ({
  useSyncStatus: () => useSyncStatus(),
  useRefreshSync: () => ({ mutate: refreshMutate, isPending: false }),
}));
```
(Replace the existing `vi.mock("@/api/sync", ...)` block with the above.) Then append the test:
```tsx
describe("AppHome refresh", () => {
  it("refreshes from Strava", () => {
    useAthlete.mockReturnValue({ data: athlete, isLoading: false, error: null });
    useSyncStatus.mockReturnValue({ data: { status: "idle", progress: 100, synced: 200,
      last_backfill_at: "T", last_sync_at: "T" } });
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /refresh from strava/i }));
    expect(refreshMutate).toHaveBeenCalled();
  });
});
```

- [ ] **Step 8: Run the frontend test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/app-home/AppHome.test.tsx`
Expected: FAIL — no "Refresh from Strava" button yet.

- [ ] **Step 9: Add the refresh button to AppHome**

In `frontend/src/pages/app-home/AppHome.tsx`, add the import:
```tsx
import { useRefreshSync, useSyncStatus } from "@/api/sync";
```
(replace the existing `import { useSyncStatus } from "@/api/sync";` line). Inside the component, after the `useSyncStatus` call, add:
```tsx
  const refreshSync = useRefreshSync();
```
Then pass a header action into `AppShell` by adding the `headerRight` prop:
```tsx
      headerRight={
        <button
          onClick={() => refreshSync.mutate()}
          disabled={refreshSync.isPending}
          className="h-[38px] px-4 rounded-[10px] bg-strava text-white font-display font-medium text-[13px] cursor-pointer hover:bg-strava-hover disabled:opacity-60"
        >
          Refresh from Strava
        </button>
      }
```
(Add it to the `<AppShell ...>` props alongside `title`/`subtitle`.)

- [ ] **Step 10: Run the frontend suite, lint, build, commit**

```bash
cd frontend && npm test && npm run lint && npm run build
git add frontend/src/pages/app-home/AppHome.tsx frontend/src/pages/app-home/AppHome.test.tsx
git commit -m "feat(frontend): Refresh from Strava on /home"
```

---

## Final verification (after all tasks)

- [ ] **Backend:** `cd backend && python -m pytest -v && ruff check . && mypy` — all green (incl. `test_architecture.py`).
- [ ] **Frontend:** `cd frontend && npm test && npm run lint && npm run build` — all green.
- [ ] **Manual (deployed stack, live Strava):** connect → land on `/home` → redirect to `/sync` → watch progress climb → "You're all set" → "Go to dashboard" → `/home` shows the Overview shell → "Refresh from Strava" returns without error. Verify both light and dark themes via the topbar toggle, and the landing page still renders correctly on the unified system.
