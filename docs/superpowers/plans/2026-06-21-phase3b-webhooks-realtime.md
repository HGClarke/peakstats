# Phase 3b — Webhook Ingest (auto-sync after every ride) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-sync an athlete's rides by subscribing to Strava push subscriptions — ingest activity create/update/delete events server-side and keep an open dashboard fresh via cheap polling.

**Architecture:** Strava → `POST /webhooks/strava` returns `200` immediately and hands the Strava fetch/upsert to in-process `BackgroundTasks` (the same pattern Phase 3a uses for backfill). The background task builds its own short-lived Supabase/Strava clients, maps `owner_id` → our athlete (our `athletes.id` **is** the Strava athlete id), and upserts or deletes the one activity. The browser stays current with TanStack Query `refetchOnWindowFocus` + a 60s interval on the overview query — no WebSocket/SSE.

**Tech Stack:** Python 3.12 · FastAPI · httpx (sync, PostgREST + Strava) · pydantic / pydantic-settings · pytest + `httpx.MockTransport` · ruff + mypy. Frontend: React 19 · Vite · TypeScript · TanStack Query · Vitest.

**Spec:** `docs/superpowers/specs/2026-06-21-phase3b-webhooks-realtime-design.md`

## Global Constraints

- **Layering (enforced by `tests/test_architecture.py`):** routers → services → db. Services import **no** `fastapi`. Routers do **not** import `app.db.*` (go through a service). db imports no upper layers.
- **Type annotations on every public function** (params + return). `mypy` (`files = ["app", "tests"]`) and `ruff check .` must be clean. `warn_unused_ignores = true` — only add a `# type: ignore[...]` where mypy actually needs it.
- **No secrets in code or logs** — never log token values or full webhook payloads.
- **Routers thin:** parse request → call one service → return response. HTTP exceptions live in routers only.
- **Async only when you `await`** — use plain `def` otherwise.
- **Reuse, don't duplicate:** map Strava activities with the existing `app.services.sync._to_activity_row`; build clients with `app.clients.build_supabase` / `build_strava`.
- **No schema change:** reuse the existing `sync_state.last_webhook_event_id bigint` column.
- **Webhook routes are public** (Strava has no session) — they are **not** behind `get_current_athlete_id`.
- **Backend test idiom:** `httpx.Client(transport=httpx.MockTransport(handler))` for Strava/PostgREST; service tests `monkeypatch` `build_supabase`/`build_strava` and db functions (mirror `tests/services/test_sync.py`); router tests use the `client` fixture from `tests/conftest.py` and patch at the service boundary (mirror `tests/routers/test_sync.py`).
- **Each commit ends with the repo's `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer.** Commit subjects below show the headline only.
- **Run from `backend/` with the worktree venv:** `./.venv/bin/pytest`, `./.venv/bin/ruff check .`, `./.venv/bin/mypy`. Frontend from `frontend/`: `npm test -- --run`, `npm run lint`, `npm run build`.

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/strava.py` (modify) | Add `get_activity` + push-subscription methods to `StravaClient` |
| `backend/app/db/activities.py` (modify) | Add `delete_activity` (athlete-scoped PostgREST DELETE) |
| `backend/app/models/webhooks.py` (create) | `StravaWebhookEvent` pydantic schema |
| `backend/app/services/webhooks.py` (create) | `process_event` — subscription/owner gating, fetch+upsert / delete, marker write; fastapi-free |
| `backend/app/config.py` + `.env.example` (modify) | Add optional `strava_webhook_subscription_id` |
| `backend/app/routers/webhooks.py` (create) | `GET /webhooks/strava` (challenge) + `POST /webhooks/strava` (fast-ack + enqueue) |
| `backend/app/main.py` (modify) | Register the webhooks router at prefix `/webhooks` |
| `backend/scripts/strava_webhook.py` (create) | One-time CLI: create / view / delete the push subscription |
| `frontend/src/api/overview.ts` (modify) | Overview query gains `refetchOnWindowFocus` + 60s interval |
| Tests | `tests/test_strava.py`, `tests/db/test_activities.py`, `tests/services/test_webhooks.py`, `tests/routers/test_webhooks.py`, `frontend/src/api/overview.test.ts` |

---

# Increment 1 — Strava client + db primitives

### Task 1: `StravaClient.get_activity`

**Files:**
- Modify: `backend/app/strava.py` (add method to `StravaClient`, after `list_activities`)
- Test: `backend/tests/test_strava.py` (append)

**Interfaces:**
- Consumes: existing `StravaClient` (`self._http`, `API_BASE_URL`).
- Produces: `StravaClient.get_activity(access_token: str, activity_id: int) -> dict` — authenticated `GET {API_BASE_URL}/activities/{activity_id}`; raises on non-2xx; returns the DetailedActivity JSON.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_strava.py`:

```python
def test_get_activity_sends_bearer_and_path():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/activities/12345"
        assert request.headers["authorization"] == "Bearer AT"
        return httpx.Response(200, json={"id": 12345, "name": "Evening ride"})

    activity = _client(handler).get_activity("AT", 12345)
    assert activity["id"] == 12345
    assert activity["name"] == "Evening ride"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/test_strava.py::test_get_activity_sends_bearer_and_path -v`
Expected: FAIL — `AttributeError: 'StravaClient' object has no attribute 'get_activity'`.

- [ ] **Step 3: Write minimal implementation**

In `backend/app/strava.py`, add to `StravaClient` (after `list_activities`, before `close`):

```python
    def get_activity(self, access_token: str, activity_id: int) -> dict:
        """Fetch a single detailed activity by id; raises on HTTP error."""
        response = self._http.get(
            f"{API_BASE_URL}/activities/{activity_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/test_strava.py::test_get_activity_sends_bearer_and_path -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
./.venv/bin/ruff check . && ./.venv/bin/mypy
git add app/strava.py tests/test_strava.py
git commit -m "feat(strava): add get_activity for single-activity fetch"
```

---

### Task 2: `StravaClient` push-subscription methods

**Files:**
- Modify: `backend/app/strava.py` (add three methods + a `PUSH_SUBSCRIPTIONS_URL` constant)
- Test: `backend/tests/test_strava.py` (append)

**Interfaces:**
- Produces:
  - `create_push_subscription(callback_url: str, verify_token: str) -> int` — `POST {API_BASE_URL}/push_subscriptions` with `client_id` + `client_secret` + `callback_url` + `verify_token` as **form** data; returns the new subscription id.
  - `list_push_subscriptions() -> list[dict]` — `GET {API_BASE_URL}/push_subscriptions` with `client_id` + `client_secret` query params.
  - `delete_push_subscription(subscription_id: int) -> None` — `DELETE {API_BASE_URL}/push_subscriptions/{id}` with `client_id` + `client_secret` query params.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_strava.py`:

```python
def test_create_push_subscription_posts_app_credentials():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = dict(httpx.QueryParams(request.content.decode()))
        return httpx.Response(201, json={"id": 42})

    sub_id = _client(handler).create_push_subscription(
        "https://api.example.com/webhooks/strava", "VT"
    )
    assert sub_id == 42
    assert seen["path"] == "/api/v3/push_subscriptions"
    assert seen["body"]["client_id"] == "cid"
    assert seen["body"]["client_secret"] == "secret"
    assert seen["body"]["callback_url"] == "https://api.example.com/webhooks/strava"
    assert seen["body"]["verify_token"] == "VT"


def test_list_push_subscriptions_sends_app_credentials():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/push_subscriptions"
        assert request.url.params["client_id"] == "cid"
        assert request.url.params["client_secret"] == "secret"
        return httpx.Response(200, json=[{"id": 42}])

    assert _client(handler).list_push_subscriptions() == [{"id": 42}]


def test_delete_push_subscription_targets_id_with_credentials():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        return httpx.Response(204)

    _client(handler).delete_push_subscription(42)
    assert seen["method"] == "DELETE"
    assert seen["path"] == "/api/v3/push_subscriptions/42"
    assert seen["params"]["client_id"] == "cid"
    assert seen["params"]["client_secret"] == "secret"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/pytest tests/test_strava.py -k push_subscription -v`
Expected: FAIL — `AttributeError: ... has no attribute 'create_push_subscription'`.

- [ ] **Step 3: Write minimal implementation**

In `backend/app/strava.py`, add a module constant near the other URLs (after `API_BASE_URL`):

```python
PUSH_SUBSCRIPTIONS_URL = f"{API_BASE_URL}/push_subscriptions"
```

Add to `StravaClient` (after `get_activity`):

```python
    def create_push_subscription(self, callback_url: str, verify_token: str) -> int:
        """Create the app-level Strava push subscription; returns its id."""
        response = self._http.post(
            PUSH_SUBSCRIPTIONS_URL,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "callback_url": callback_url,
                "verify_token": verify_token,
            },
        )
        response.raise_for_status()
        return int(response.json()["id"])

    def list_push_subscriptions(self) -> list[dict]:
        """List the app's current push subscriptions."""
        response = self._http.get(
            PUSH_SUBSCRIPTIONS_URL,
            params={"client_id": self._client_id, "client_secret": self._client_secret},
        )
        response.raise_for_status()
        return response.json()

    def delete_push_subscription(self, subscription_id: int) -> None:
        """Delete the app's push subscription by id; raises on HTTP error."""
        response = self._http.request(
            "DELETE",
            f"{PUSH_SUBSCRIPTIONS_URL}/{subscription_id}",
            params={"client_id": self._client_id, "client_secret": self._client_secret},
        )
        response.raise_for_status()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/pytest tests/test_strava.py -k push_subscription -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
./.venv/bin/ruff check . && ./.venv/bin/mypy
git add app/strava.py tests/test_strava.py
git commit -m "feat(strava): add push-subscription create/list/delete"
```

---

### Task 3: `db.activities.delete_activity`

**Files:**
- Modify: `backend/app/db/activities.py` (add function)
- Test: `backend/tests/db/test_activities.py` (append)

**Interfaces:**
- Produces: `delete_activity(client: httpx.Client, athlete_id: int, activity_id: int) -> None` — PostgREST `DELETE /activities?id=eq.{activity_id}&athlete_id=eq.{athlete_id}`; raises on HTTP error. Athlete-scoped so one athlete's event cannot delete another's row.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/db/test_activities.py`:

```python
def test_delete_activity_scopes_by_athlete_and_id():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["params"] = dict(request.url.params)
        return httpx.Response(204)

    activities.delete_activity(_client(handler), athlete_id=7, activity_id=123)
    assert seen["method"] == "DELETE"
    assert seen["params"]["id"] == "eq.123"
    assert seen["params"]["athlete_id"] == "eq.7"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/db/test_activities.py::test_delete_activity_scopes_by_athlete_and_id -v`
Expected: FAIL — `AttributeError: module 'app.db.activities' has no attribute 'delete_activity'`.

- [ ] **Step 3: Write minimal implementation**

Append to `backend/app/db/activities.py`:

```python
def delete_activity(client: httpx.Client, athlete_id: int, activity_id: int) -> None:
    response = client.request(
        "DELETE",
        "/activities",
        params={"id": f"eq.{activity_id}", "athlete_id": f"eq.{athlete_id}"},
    )
    response.raise_for_status()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/pytest tests/db/test_activities.py::test_delete_activity_scopes_by_athlete_and_id -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
./.venv/bin/ruff check . && ./.venv/bin/mypy
git add app/db/activities.py tests/db/test_activities.py
git commit -m "feat(db): add athlete-scoped delete_activity"
```

---

# Increment 2 — Webhook ingest

### Task 4: Event model + `process_event` service

**Files:**
- Create: `backend/app/models/webhooks.py`
- Create: `backend/app/services/webhooks.py`
- Modify: `backend/app/config.py` (add `strava_webhook_subscription_id`)
- Modify: `backend/.env.example` (add `STRAVA_WEBHOOK_SUBSCRIPTION_ID`)
- Test: `backend/tests/services/test_webhooks.py`

**Interfaces:**
- Consumes: `app.clients.build_supabase`/`build_strava`; `app.services.tokens.get_valid_access_token`; `app.services.sync._to_activity_row`; `app.db.activities.upsert_activities`/`delete_activity`; `app.db.athletes.get_athlete`; `app.db.sync_state.upsert_sync_state`; `StravaClient.get_activity`.
- Produces:
  - `StravaWebhookEvent` (pydantic) — fields `aspect_type: str`, `object_type: str`, `object_id: int`, `owner_id: int`, `subscription_id: int`, `event_time: int`, `updates: dict` (default `{}`).
  - `process_event(settings: Settings, event: StravaWebhookEvent) -> None` — ignores non-`activity`, foreign-subscription (when `strava_webhook_subscription_id` is set), and unknown-owner events; on create/update fetches + upserts the activity; on delete removes the row; writes `sync_state.last_webhook_event_id = event_time` on success; swallows + logs all errors.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/services/test_webhooks.py`:

```python
from app.config import Settings
from app.models.webhooks import StravaWebhookEvent
from app.services import webhooks as webhooks_service

# subscription_id 0 => the optional subscription gate is disabled (default).
SETTINGS = Settings(strava_webhook_subscription_id=0)


class FakeSupabase:
    def close(self) -> None:
        pass


class FakeStrava:
    def __init__(self) -> None:
        self.fetched: list[int] = []

    def get_activity(self, access_token, activity_id):
        self.fetched.append(activity_id)
        return {"id": activity_id, "name": "Ride", "type": "Ride",
                "start_date": "2026-06-21T08:00:00Z", "distance": 1000.0,
                "moving_time": 100, "elapsed_time": 110, "total_elevation_gain": 5.0}

    def close(self) -> None:
        pass


def _event(**overrides) -> StravaWebhookEvent:
    base = {"aspect_type": "create", "object_type": "activity", "object_id": 555,
            "owner_id": 7, "subscription_id": 1, "event_time": 1_700_000_000}
    base.update(overrides)
    return StravaWebhookEvent(**base)


def _wire(monkeypatch, *, athlete=True):
    strava = FakeStrava()
    monkeypatch.setattr(webhooks_service, "build_supabase", lambda settings: FakeSupabase())
    monkeypatch.setattr(webhooks_service, "build_strava", lambda settings: strava)
    monkeypatch.setattr(webhooks_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    monkeypatch.setattr(webhooks_service.athletes_db, "get_athlete",
                        lambda supabase, athlete_id: {"id": athlete_id} if athlete else None)
    return strava


def test_create_event_fetches_and_upserts(monkeypatch):
    upserts = []
    states = []
    strava = _wire(monkeypatch)
    monkeypatch.setattr(webhooks_service.activities_db, "upsert_activities",
                        lambda supabase, rows: upserts.append(rows))
    monkeypatch.setattr(webhooks_service.sync_state_db, "upsert_sync_state",
                        lambda supabase, athlete_id, fields: states.append(fields))

    webhooks_service.process_event(SETTINGS, _event(aspect_type="create"))

    assert strava.fetched == [555]
    assert upserts[0][0]["id"] == 555
    assert upserts[0][0]["athlete_id"] == 7
    assert states[-1] == {"last_webhook_event_id": 1_700_000_000}


def test_delete_event_removes_row_without_fetch(monkeypatch):
    deleted = {}
    strava = _wire(monkeypatch)
    monkeypatch.setattr(webhooks_service.activities_db, "delete_activity",
                        lambda supabase, athlete_id, activity_id: deleted.update(
                            athlete_id=athlete_id, activity_id=activity_id))
    monkeypatch.setattr(webhooks_service.sync_state_db, "upsert_sync_state",
                        lambda supabase, athlete_id, fields: None)

    webhooks_service.process_event(SETTINGS, _event(aspect_type="delete"))

    assert strava.fetched == []
    assert deleted == {"athlete_id": 7, "activity_id": 555}


def test_unknown_owner_is_ignored(monkeypatch):
    strava = _wire(monkeypatch, athlete=False)

    def fail_upsert(*a, **k):
        raise AssertionError("must not upsert for unknown owner")

    monkeypatch.setattr(webhooks_service.activities_db, "upsert_activities", fail_upsert)
    webhooks_service.process_event(SETTINGS, _event())
    assert strava.fetched == []


def test_non_activity_event_builds_no_clients(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("must not build clients for non-activity events")

    monkeypatch.setattr(webhooks_service, "build_supabase", fail)
    monkeypatch.setattr(webhooks_service, "build_strava", fail)
    webhooks_service.process_event(SETTINGS, _event(object_type="athlete", aspect_type="update"))


def test_foreign_subscription_id_is_ignored(monkeypatch):
    def fail(*a, **k):
        raise AssertionError("must not build clients for a foreign subscription id")

    monkeypatch.setattr(webhooks_service, "build_supabase", fail)
    monkeypatch.setattr(webhooks_service, "build_strava", fail)
    settings = Settings(strava_webhook_subscription_id=999)
    # Event carries subscription_id=1, which does not match the configured 999.
    webhooks_service.process_event(settings, _event(subscription_id=1))


def test_fetch_error_is_swallowed(monkeypatch):
    _wire(monkeypatch)

    def boom(access_token, activity_id):
        raise RuntimeError("strava 500")

    # Replace the fake strava's get_activity with a raising one.
    monkeypatch.setattr(webhooks_service, "build_strava",
                        lambda settings: type("S", (), {"get_activity": staticmethod(boom),
                                                         "close": lambda self: None})())

    def fail_state(*a, **k):
        raise AssertionError("must not record marker when processing failed")

    monkeypatch.setattr(webhooks_service.sync_state_db, "upsert_sync_state", fail_state)
    # Should not raise.
    webhooks_service.process_event(SETTINGS, _event(aspect_type="update"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/pytest tests/services/test_webhooks.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.webhooks'`.

- [ ] **Step 3: Add the optional subscription-id env var**

In `backend/app/config.py`, add to `Settings` (immediately after `strava_webhook_verify_token`):

```python
    strava_webhook_subscription_id: int = 0
```

In `backend/.env.example`, add after the `STRAVA_WEBHOOK_VERIFY_TOKEN=` line (use a numeric default so a copied `.env` parses as `int`):

```
STRAVA_WEBHOOK_SUBSCRIPTION_ID=0
```

- [ ] **Step 4: Write the model**

Create `backend/app/models/webhooks.py`:

```python
from pydantic import BaseModel, Field


class StravaWebhookEvent(BaseModel):
    """A Strava push-subscription event payload."""

    aspect_type: str
    object_type: str
    object_id: int
    owner_id: int
    subscription_id: int
    event_time: int
    updates: dict = Field(default_factory=dict)
```

- [ ] **Step 5: Write the service**

Create `backend/app/services/webhooks.py`:

```python
import logging

from app.clients import build_strava, build_supabase
from app.config import Settings
from app.db import activities as activities_db
from app.db import athletes as athletes_db
from app.db import sync_state as sync_state_db
from app.models.webhooks import StravaWebhookEvent
from app.services import sync as sync_service
from app.services.tokens import get_valid_access_token

logger = logging.getLogger(__name__)


def process_event(settings: Settings, event: StravaWebhookEvent) -> None:
    """Ingest one Strava webhook event: fetch+upsert or delete the activity.

    Runs as a background task. Builds its own clients; ignores non-activity,
    foreign-subscription, and unknown-owner events; and swallows errors (we have
    already returned 200 to Strava).
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

    supabase = build_supabase(settings)
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
            activities_db.upsert_activities(supabase, [row])  # type: ignore[arg-type]

        sync_state_db.upsert_sync_state(
            supabase, event.owner_id, {"last_webhook_event_id": event.event_time}
        )
    except Exception:
        logger.exception("Failed to process webhook for athlete %s", event.owner_id)
    finally:
        supabase.close()
        strava.close()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `./.venv/bin/pytest tests/services/test_webhooks.py -v`
Expected: PASS (6 tests).

- [ ] **Step 7: Verify architecture + lint + types**

Run: `./.venv/bin/pytest tests/test_architecture.py -v && ./.venv/bin/ruff check . && ./.venv/bin/mypy`
Expected: PASS / clean (the new service imports no `fastapi`).

- [ ] **Step 8: Commit**

```bash
git add app/config.py app/models/webhooks.py app/services/webhooks.py tests/services/test_webhooks.py .env.example
git commit -m "feat(webhooks): ingest service for activity create/update/delete"
```

---

### Task 5: Webhook router + registration

**Files:**
- Create: `backend/app/routers/webhooks.py`
- Modify: `backend/app/main.py` (import + register router at prefix `/webhooks`)
- Test: `backend/tests/routers/test_webhooks.py`

**Interfaces:**
- Consumes: `StravaWebhookEvent`; `app.services.webhooks.process_event`; `app.config.get_settings`.
- Produces (HTTP):
  - `GET /webhooks/strava?hub.mode=&hub.verify_token=&hub.challenge=` → `200 {"hub.challenge": <value>}` when the verify token matches `settings.strava_webhook_verify_token`, else `403`.
  - `POST /webhooks/strava` → `200 {"status": "accepted"}` and schedules `process_event` via `BackgroundTasks`; malformed/unparseable body → `200 {"status": "ignored"}` and schedules nothing. Neither route requires a session.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/routers/test_webhooks.py`:

```python
from app.config import Settings, get_settings
from app.services import webhooks as webhooks_service


def _with_verify_token(client, token: str) -> None:
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        session_secret="test-secret", strava_webhook_verify_token=token
    )


def test_get_challenge_echoes_when_token_matches(client):
    _with_verify_token(client, "VT")
    response = client.get(
        "/webhooks/strava",
        params={"hub.mode": "subscribe", "hub.verify_token": "VT",
                "hub.challenge": "ping-123"},
    )
    assert response.status_code == 200
    assert response.json() == {"hub.challenge": "ping-123"}


def test_get_challenge_rejects_bad_token(client):
    _with_verify_token(client, "VT")
    response = client.get(
        "/webhooks/strava",
        params={"hub.mode": "subscribe", "hub.verify_token": "WRONG",
                "hub.challenge": "ping-123"},
    )
    assert response.status_code == 403


def test_post_accepts_and_schedules_processing(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(webhooks_service, "process_event",
                        lambda settings, event: seen.update(owner=event.owner_id,
                                                            obj=event.object_id))
    response = client.post("/webhooks/strava", json={
        "aspect_type": "create", "object_type": "activity", "object_id": 555,
        "owner_id": 7, "subscription_id": 1, "event_time": 1_700_000_000,
    })
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    assert seen == {"owner": 7, "obj": 555}


def test_post_ignores_malformed_payload(client, monkeypatch):
    def fail(settings, event):
        raise AssertionError("must not schedule processing for malformed payload")

    monkeypatch.setattr(webhooks_service, "process_event", fail)
    response = client.post("/webhooks/strava", json={"hello": "world"})
    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/pytest tests/routers/test_webhooks.py -v`
Expected: FAIL — all `404` (route not registered) / import errors.

- [ ] **Step 3: Write the router**

Create `backend/app/routers/webhooks.py`:

```python
import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.models.webhooks import StravaWebhookEvent
from app.services import webhooks as webhooks_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/strava")
def validate_subscription(
    hub_challenge: str = Query("", alias="hub.challenge"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    if not hmac.compare_digest(hub_verify_token, settings.strava_webhook_verify_token):
        raise HTTPException(status_code=403, detail="Invalid verify token")
    return {"hub.challenge": hub_challenge}


@router.post("/strava")
async def receive_event(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    try:
        payload = await request.json()
        event = StravaWebhookEvent.model_validate(payload)
    except (ValueError, ValidationError):
        logger.warning("Ignoring malformed Strava webhook payload")
        return {"status": "ignored"}
    background_tasks.add_task(webhooks_service.process_event, settings, event)
    return {"status": "accepted"}
```

- [ ] **Step 4: Register the router**

In `backend/app/main.py`, add `webhooks` to the routers import and register it (after the `sync` router):

```python
from app.routers import activities, athletes, auth, health, sync, webhooks
```

```python
    app.include_router(sync.router, prefix="/sync")
    app.include_router(webhooks.router, prefix="/webhooks")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/bin/pytest tests/routers/test_webhooks.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Verify architecture + full suite + lint + types**

Run: `./.venv/bin/pytest && ./.venv/bin/ruff check . && ./.venv/bin/mypy`
Expected: all green (router imports no `app.db`; `test_architecture.py` passes).

- [ ] **Step 7: Commit**

```bash
git add app/routers/webhooks.py app/main.py tests/routers/test_webhooks.py
git commit -m "feat(webhooks): GET challenge + POST fast-ack ingest endpoint"
```

---

# Increment 3 — Subscription CLI

### Task 6: `scripts/strava_webhook.py`

**Files:**
- Create: `backend/scripts/strava_webhook.py`

**Interfaces:**
- Consumes: `app.config.get_settings`, `app.clients.build_strava`, and the `StravaClient` push-subscription methods from Task 2.
- Produces: a CLI with subcommands `create --callback-url <url>`, `view`, `delete --id <n>`.

**Note on testing:** the underlying client methods are already unit-tested in Task 2; this script adds only argument wiring. It is **not** imported by any test (keeping `mypy`'s `files = ["app", "tests"]` scope clean — `scripts/` is outside it), and is verified by `--help` here and end-to-end in Increment 5. It must still pass `ruff check .`, so annotate `main() -> None`.

- [ ] **Step 1: Write the script**

Create `backend/scripts/strava_webhook.py`:

```python
"""One-time CLI to manage the single Strava webhook push subscription.

Run from backend/ with the app environment, e.g.:
    ./.venv/bin/python scripts/strava_webhook.py create \
        --callback-url https://peakstats-api.onrender.com/webhooks/strava
    ./.venv/bin/python scripts/strava_webhook.py view
    ./.venv/bin/python scripts/strava_webhook.py delete --id 42
"""

import argparse

from app.clients import build_strava
from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the Strava webhook subscription")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="Create the push subscription")
    create.add_argument("--callback-url", required=True)
    sub.add_parser("view", help="List current push subscriptions")
    delete = sub.add_parser("delete", help="Delete a push subscription by id")
    delete.add_argument("--id", type=int, required=True)
    args = parser.parse_args()

    settings = get_settings()
    strava = build_strava(settings)
    try:
        if args.command == "create":
            sub_id = strava.create_push_subscription(
                args.callback_url, settings.strava_webhook_verify_token
            )
            print(f"Created subscription {sub_id}")
        elif args.command == "view":
            print(strava.list_push_subscriptions())
        elif args.command == "delete":
            strava.delete_push_subscription(args.id)
            print(f"Deleted subscription {args.id}")
    finally:
        strava.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it loads and shows help**

Run: `./.venv/bin/python scripts/strava_webhook.py --help`
Expected: argparse usage text listing `create`, `view`, `delete`; exit code 0.

Run: `./.venv/bin/python scripts/strava_webhook.py create --help`
Expected: usage showing the required `--callback-url`.

- [ ] **Step 3: Lint**

Run: `./.venv/bin/ruff check .`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add scripts/strava_webhook.py
git commit -m "feat(webhooks): one-time CLI to manage the Strava subscription"
```

---

# Increment 4 — Frontend cheap polling

### Task 7: Overview query polls on focus + interval

**Files:**
- Modify: `frontend/src/api/overview.ts`
- Test: `frontend/src/api/overview.test.ts` (append)

**Interfaces:**
- Produces:
  - `OVERVIEW_REFETCH_INTERVAL_MS = 60_000` (exported constant).
  - `overviewQueryOptions()` — returns the `useQuery` options object (`queryKey`, `queryFn`, `refetchOnWindowFocus: true`, `refetchInterval: OVERVIEW_REFETCH_INTERVAL_MS`).
  - `useOverview()` — unchanged return shape; now calls `useQuery(overviewQueryOptions())`.

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/api/overview.test.ts`:

```typescript
import { overviewQueryOptions, OVERVIEW_REFETCH_INTERVAL_MS } from "./overview";

describe("overviewQueryOptions", () => {
  it("refetches on window focus and on a 60s interval", () => {
    const opts = overviewQueryOptions();
    expect(opts.refetchOnWindowFocus).toBe(true);
    expect(opts.refetchInterval).toBe(OVERVIEW_REFETCH_INTERVAL_MS);
    expect(OVERVIEW_REFETCH_INTERVAL_MS).toBe(60_000);
  });
});
```

(Keep the existing top-of-file imports; add the named import above or merge it into the existing `./overview` import line.)

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npm test -- --run src/api/overview.test.ts`
Expected: FAIL — `overviewQueryOptions` / `OVERVIEW_REFETCH_INTERVAL_MS` are not exported.

- [ ] **Step 3: Implement the options seam**

In `frontend/src/api/overview.ts`, replace the `useOverview` block at the bottom with:

```typescript
export const OVERVIEW_REFETCH_INTERVAL_MS = 60_000;

export function overviewQueryOptions() {
  return {
    queryKey: ["activities", "overview"] as const,
    queryFn: fetchOverview,
    refetchOnWindowFocus: true,
    refetchInterval: OVERVIEW_REFETCH_INTERVAL_MS,
  };
}

export function useOverview() {
  return useQuery(overviewQueryOptions());
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `frontend/`): `npm test -- --run src/api/overview.test.ts`
Expected: PASS (new test + existing `toOverview` tests).

- [ ] **Step 5: Full frontend gate**

Run (from `frontend/`): `npm test -- --run && npm run lint && npm run build`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/api/overview.ts src/api/overview.test.ts
git commit -m "feat(overview): poll on window focus + 60s interval for webhook freshness"
```

---

# Increment 5 — Live setup + end-to-end verification

### Task 8: Roll out the subscription and verify (manual)

This task has no code; it wires the deployed stack and confirms a real ride flows in. Do it after Increments 1–4 are merged and the backend is deployed with the `/webhooks/strava` routes live. Requires access to the Render dashboard and a live Strava account.

- [ ] **Step 1: Set a real verify token on Render**

In the Render dashboard for service `peakstats-api`, set `STRAVA_WEBHOOK_VERIFY_TOKEN` to a fresh random value (replacing the placeholder). Trigger/await a deploy so the env var is live.

- [ ] **Step 2: Confirm the challenge endpoint answers**

Run (substituting the same token):

```bash
curl -s "https://peakstats-api.onrender.com/webhooks/strava?hub.mode=subscribe&hub.verify_token=<TOKEN>&hub.challenge=ping123"
```

Expected: `{"hub.challenge":"ping123"}`. A wrong token must return `403`.

- [ ] **Step 3: Create the subscription**

From `backend/` with prod `STRAVA_CLIENT_ID`/`STRAVA_CLIENT_SECRET`/`STRAVA_WEBHOOK_VERIFY_TOKEN` in the environment:

```bash
./.venv/bin/python scripts/strava_webhook.py create \
  --callback-url https://peakstats-api.onrender.com/webhooks/strava
```

Expected: `Created subscription <id>`. Strava calls the GET challenge during this step; if it prints an error, re-check Steps 1–2. (Only one subscription may exist per app — `view` first if unsure; `delete --id` to clear a stale one.)

- [ ] **Step 4: Record the subscription id and enable the gate (recommended)**

Note the returned id and set `STRAVA_WEBHOOK_SUBSCRIPTION_ID` to it on Render. Once non-zero, `process_event` drops any POST whose `subscription_id` doesn't match (mitigates forged events — notably a forged `delete` for a known athlete). Re-deploy, then `view` to confirm:

```bash
./.venv/bin/python scripts/strava_webhook.py view
```

- [ ] **Step 5: End-to-end check**

On the connected Strava account: create (or edit, then delete) an activity. Within a minute (or on refocusing the dashboard tab), the Overview reflects the change. Confirm in the Render logs that `POST /webhooks/strava` returned `200` and the background task processed the event (no token/payload values logged). Confirm in Supabase that the `activities` row was upserted/removed and `sync_state.last_webhook_event_id` advanced.

- [ ] **Step 6: Finish the branch**

With all increments verified, use `superpowers:finishing-a-development-branch` to merge/PR `worktree-phase3b-webhooks-realtime` into `main`.

---

## Notes for the executor

- **Deviation from spec:** the GET challenge returns a plain `dict[str, str]` rather than a `WebhookValidationResponse` model — the dotted key `hub.challenge` is awkward to express as a pydantic response model and the echo carries no logic. This is an intentional simplification.
- **Why `process_event` reuses `sync_service._to_activity_row`:** it is the single source of truth for the Strava-summary → `activities`-row mapping (Strava's DetailedActivity is a superset of the summary fields it reads), so webhook-ingested rows match backfilled rows exactly.
- **Ordering:** Tasks 1–5 are backend and strictly ordered (each builds on the prior). Task 7 (frontend) is independent and may be done in parallel. Task 8 is last and manual.
