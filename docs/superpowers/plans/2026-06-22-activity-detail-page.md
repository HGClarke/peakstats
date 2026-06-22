# Activity Detail Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `/activities/:id` ride-detail page from the imported Claude Design — hero route over a theme-matched map, power chart, power/HR zone panels, elevation profile, and a climbs table — wired to real Strava stream data.

**Architecture:** FastAPI `routers → services → db` gains lazily-fetched, cached activity streams plus a pure `services/analysis.py` for NP/zones/VAM; two endpoints (`GET /activities/{id}`, `GET /activities/{id}/streams`) and `ftp_w`/`hr_max` settings. The React SPA adds an api-layer data module feeding presentational panels; Leaflet renders the route, Recharts renders the graphs, all colors flow through `index.css` tokens so light/dark match.

**Tech Stack:** Python 3.12 / FastAPI / Pydantic / supabase-py / pytest+respx; React 19 / Vite / TypeScript / Tailwind v4 / TanStack Query / Recharts 3 / react-leaflet 5 + leaflet / Vitest + RTL.

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-06-22-activity-detail-page-design.md`.
- **Backend layering** (enforced by `tests/test_architecture.py`): `routers` import services, `services` import db + clients and **never** `fastapi`; HTTPExceptions live only in routers; services raise domain errors.
- **Streams JSONB shape:** flat object-of-arrays `{"watts":[…],"altitude":[…]}` — never array-of-objects, never one row per sample.
- **OAuth scope is `read,activity:read_all`** — do not add scopes. Streams are covered; zones/FTP come from manual Settings, not Strava.
- **Frontend rules** (`frontend/CLAUDE.md`): `@/` imports; pages compose / components render; **data + formatting live in the `api/` layer**, components are presentational; **token utilities only — no raw hex, no `text-[#..] dark:text-[#..]` pairs**; new colors go in BOTH `:root` and `.dark` in `index.css` and are mapped under `@theme inline`; icons via `lucide-react`; `erasableSyntaxOnly` is on (no enums / no constructor param-properties); in-app nav via react-router `<Link>`.
- **Done bar:** backend `pytest` green; frontend `npm test && npm run lint && npm run build` green. Run from `backend/` and `frontend/` respectively.
- **Commits:** one per task (or per tight test+impl pair); end messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **Branch:** `feat/activity-detail-page` (already checked out; spec already committed).

---

## INCREMENT 1 — Streams foundation

Goal: lazily fetch + cache Strava activity streams and serve them. End state: `GET /activities/{id}/streams` returns cached channel arrays.

### Task 1: Migration `0006` — `activity_streams` table

**Files:**
- Create: `supabase/migrations/0006_activity_streams.sql`

- [ ] **Step 1: Write the migration**

```sql
-- Cached raw Strava streams for one activity, stored as a flat object-of-arrays
-- JSONB: {"time":[…],"distance":[…],"altitude":[…],"heartrate":[…],"watts":[…],
--         "velocity_smooth":[…]}. One row per activity; computed-on-read panels
-- (zones, charts) derive from this. A sentinel row with data='{}' / point_count=0
-- marks activities Strava has no streams for, so we never refetch.
create table if not exists activity_streams (
  activity_id bigint primary key references activities(id) on delete cascade,
  athlete_id  bigint not null references athletes(id) on delete cascade,
  data        jsonb  not null,
  resolution  text   not null,
  point_count integer not null,
  fetched_at  timestamptz not null default now()
);

alter table activity_streams enable row level security;

create policy activity_streams_self_read on activity_streams
  for select using (athlete_id = (auth.jwt() ->> 'athlete_id')::bigint);
```

- [ ] **Step 2: Apply to Supabase**

Apply via the Supabase MCP `apply_migration` (name `activity_streams`, the SQL above) or the dashboard SQL editor. Confirm the table appears via `list_tables`.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/0006_activity_streams.sql
git commit -m "feat(db): activity_streams table for cached Strava streams"
```

### Task 2: `strava.get_activity_streams`

**Files:**
- Modify: `backend/app/strava.py` (add method after `get_activity`)
- Test: `backend/tests/test_strava.py` (create if absent; else append)

**Interfaces:**
- Produces: `StravaClient.get_activity_streams(access_token: str, activity_id: int, keys: list[str], resolution: str = "high") -> dict[str, list]` — returns the **flat** object-of-arrays (Strava's `{"watts":{"data":[…]}}` flattened to `{"watts":[…]}`). Channels Strava omits are absent from the dict.

- [ ] **Step 1: Write the failing test**

```python
import respx
from httpx import Response
from app.strava import StravaClient, API_BASE_URL
import httpx


def _client() -> StravaClient:
    return StravaClient(httpx.Client(), "cid", "sec", "http://cb")


@respx.mock
def test_get_activity_streams_flattens_and_passes_params():
    route = respx.get(f"{API_BASE_URL}/activities/555/streams").mock(
        return_value=Response(200, json={
            "watts": {"data": [100, 200], "type": "watts"},
            "altitude": {"data": [10.0, 12.5], "type": "altitude"},
        })
    )
    out = _client().get_activity_streams("tok", 555, ["watts", "altitude"])
    assert out == {"watts": [100, 200], "altitude": [10.0, 12.5]}
    params = route.calls.last.request.url.params
    assert params["keys"] == "watts,altitude"
    assert params["key_by_type"] == "true"
    assert params["resolution"] == "high"
    assert route.calls.last.request.headers["Authorization"] == "Bearer tok"
```

- [ ] **Step 2: Run it — expect FAIL** (`AttributeError: 'StravaClient' object has no attribute 'get_activity_streams'`)

Run: `cd backend && python -m pytest tests/test_strava.py -v`

- [ ] **Step 3: Implement**

Add to `StravaClient` in `app/strava.py`:

```python
    def get_activity_streams(
        self,
        access_token: str,
        activity_id: int,
        keys: list[str],
        resolution: str = "high",
    ) -> dict[str, list]:
        """Fetch activity streams, flattened to {channel: [values]}.

        Strava returns {"watts": {"data": [...], "type": "watts"}, ...} when
        key_by_type=true; we flatten to {"watts": [...]}. Omitted channels are
        absent. Raises on HTTP error.
        """
        response = self._http.get(
            f"{API_BASE_URL}/activities/{activity_id}/streams",
            params={
                "keys": ",".join(keys),
                "key_by_type": "true",
                "resolution": resolution,
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        payload = response.json()
        return {
            channel: body["data"]
            for channel, body in payload.items()
            if isinstance(body, dict) and "data" in body
        }
```

- [ ] **Step 4: Run it — expect PASS**

Run: `cd backend && python -m pytest tests/test_strava.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/strava.py backend/tests/test_strava.py
git commit -m "feat(strava): get_activity_streams client method"
```

### Task 3: `db/streams.py`

**Files:**
- Create: `backend/app/db/streams.py`
- Test: `backend/tests/db/test_streams.py`

**Interfaces:**
- Produces:
  - `StreamRow` TypedDict: `{activity_id: int, athlete_id: int, data: dict, resolution: str, point_count: int}`
  - `get_streams(client: Client, activity_id: int) -> StreamRow | None`
  - `upsert_streams(client: Client, row: StreamRow) -> None`

- [ ] **Step 1: Write the failing test**

```python
import respx
from app.db import streams
from httpx import Response
from supabase import create_client

CLIENT = create_client("https://proj.supabase.co", "svc")


@respx.mock
def test_get_streams_returns_row_or_none():
    respx.route(method="GET", path="/rest/v1/activity_streams").mock(
        return_value=Response(200, json=[{"activity_id": 5, "athlete_id": 7,
                                          "data": {"watts": [1, 2]},
                                          "resolution": "high", "point_count": 2}])
    )
    row = streams.get_streams(CLIENT, 5)
    assert row is not None and row["point_count"] == 2 and row["data"] == {"watts": [1, 2]}


@respx.mock
def test_get_streams_none_when_missing():
    respx.route(method="GET", path="/rest/v1/activity_streams").mock(
        return_value=Response(200, json=[])
    )
    assert streams.get_streams(CLIENT, 5) is None


@respx.mock
def test_upsert_streams_posts_with_merge():
    route = respx.route(method="POST", path="/rest/v1/activity_streams").mock(
        return_value=Response(201, json=[])
    )
    streams.upsert_streams(CLIENT, {"activity_id": 5, "athlete_id": 7,
                                    "data": {}, "resolution": "high", "point_count": 0})
    req = route.calls.last.request
    assert req.url.params["on_conflict"] == "activity_id"
    assert "merge-duplicates" in req.headers.get("prefer", "")
```

- [ ] **Step 2: Run it — expect FAIL** (`ModuleNotFoundError: app.db.streams`)

Run: `cd backend && python -m pytest tests/db/test_streams.py -v`

- [ ] **Step 3: Implement** `app/db/streams.py`

```python
from typing import Any, TypedDict, cast

from supabase import Client


class StreamRow(TypedDict):
    activity_id: int
    athlete_id: int
    data: dict
    resolution: str
    point_count: int


def get_streams(client: Client, activity_id: int) -> StreamRow | None:
    resp = (
        client.table("activity_streams")
        .select("activity_id, athlete_id, data, resolution, point_count")
        .eq("activity_id", activity_id)
        .execute()
    )
    return cast(StreamRow, resp.data[0]) if resp.data else None


def upsert_streams(client: Client, row: StreamRow) -> None:
    client.table("activity_streams").upsert(
        cast(dict[str, Any], row), on_conflict="activity_id"
    ).execute()
```

- [ ] **Step 4: Run it — expect PASS**

Run: `cd backend && python -m pytest tests/db/test_streams.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/streams.py backend/tests/db/test_streams.py
git commit -m "feat(db): activity_streams read/upsert"
```

### Task 4: `ensure_streams` + streams endpoint

**Files:**
- Modify: `backend/app/models/activities.py` (add `ActivityStreamsResponse`)
- Modify: `backend/app/services/activities.py` (add `STREAM_KEYS`, `ensure_streams`, `get_streams_payload`)
- Modify: `backend/app/routers/activities.py` (add `GET /{activity_id}/streams`)
- Test: `backend/tests/services/test_activities_streams.py`, `backend/tests/routers/test_activities.py` (append)

**Interfaces:**
- Consumes: `db.streams.get_streams/upsert_streams`, `strava.get_activity_streams`, `services.tokens.get_valid_access_token`, `db.activities` (existing).
- Produces:
  - `STREAM_KEYS: list[str] = ["time","distance","altitude","heartrate","watts","velocity_smooth"]`
  - `ensure_streams(supabase, strava, athlete_id: int, activity_id: int) -> dict[str, list]` — returns the cached `data` dict (`{}` if none); fetches+persists on miss (incl. sentinel).
  - `get_streams_payload(supabase, strava, athlete_id, activity_id) -> ActivityStreamsResponse`
  - `ActivityStreamsResponse(point_count: int, time, distance, altitude, watts, heartrate, velocity_smooth)` — each channel `list | None`.

- [ ] **Step 1: Write the failing service test**

```python
from app.services import activities as svc


class _Strava:
    def __init__(self): self.calls = 0
    def get_activity_streams(self, token, aid, keys, resolution="high"):
        self.calls += 1
        return {"time": [0, 1], "distance": [0.0, 5.0], "watts": [100, 200]}


def test_ensure_streams_returns_cached_without_fetch(monkeypatch):
    monkeypatch.setattr(svc.streams_db, "get_streams",
        lambda c, aid: {"activity_id": aid, "athlete_id": 7,
                        "data": {"watts": [1]}, "resolution": "high", "point_count": 1})
    strava = _Strava()
    data = svc.ensure_streams(object(), strava, 7, 5)
    assert data == {"watts": [1]} and strava.calls == 0


def test_ensure_streams_fetches_persists_on_miss(monkeypatch):
    saved = {}
    monkeypatch.setattr(svc.streams_db, "get_streams", lambda c, aid: None)
    monkeypatch.setattr(svc.streams_db, "upsert_streams",
                        lambda c, row: saved.update(row))
    monkeypatch.setattr(svc, "get_valid_access_token", lambda c, s, a: "tok")
    data = svc.ensure_streams(object(), _Strava(), 7, 5)
    assert data["watts"] == [100, 200]
    assert saved["point_count"] == 2 and saved["activity_id"] == 5 and saved["athlete_id"] == 7


def test_ensure_streams_sentinel_when_strava_empty(monkeypatch):
    saved = {}
    monkeypatch.setattr(svc.streams_db, "get_streams", lambda c, aid: None)
    monkeypatch.setattr(svc.streams_db, "upsert_streams", lambda c, row: saved.update(row))
    monkeypatch.setattr(svc, "get_valid_access_token", lambda c, s, a: "tok")

    class Empty:
        def get_activity_streams(self, *a, **k): return {}
    data = svc.ensure_streams(object(), Empty(), 7, 5)
    assert data == {} and saved["point_count"] == 0


def test_get_streams_payload_shapes_channels(monkeypatch):
    monkeypatch.setattr(svc, "ensure_streams",
        lambda c, s, a, aid: {"time": [0, 1], "distance": [0.0, 5.0], "watts": [100, 200]})
    out = svc.get_streams_payload(object(), object(), 7, 5)
    assert out.point_count == 2
    assert out.watts == [100, 200] and out.altitude is None and out.heartrate is None
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `cd backend && python -m pytest tests/services/test_activities_streams.py -v`

- [ ] **Step 3: Add the model** to `app/models/activities.py`

```python
class ActivityStreamsResponse(BaseModel):
    point_count: int
    time: list[int] | None = None
    distance: list[float] | None = None
    altitude: list[float] | None = None
    watts: list[float | None] | None = None
    heartrate: list[int | None] | None = None
    velocity_smooth: list[float] | None = None
```

- [ ] **Step 4: Implement the service** — add imports + functions to `app/services/activities.py`

```python
from app.db import streams as streams_db
from app.models.activities import ActivityStreamsResponse
from app.services.tokens import get_valid_access_token
from app.clients import build_strava  # only if a strava client isn't passed in

STREAM_KEYS = ["time", "distance", "altitude", "heartrate", "watts", "velocity_smooth"]


def ensure_streams(supabase, strava, athlete_id: int, activity_id: int) -> dict[str, list]:
    """Return cached stream data for the activity, fetching from Strava on miss.

    Stores a sentinel (empty data, point_count 0) when Strava has no streams, so
    we never refetch. `data` is the flat object-of-arrays.
    """
    existing = streams_db.get_streams(supabase, activity_id)
    if existing is not None:
        return existing["data"]
    token = get_valid_access_token(supabase, strava, athlete_id)
    data = strava.get_activity_streams(token, activity_id, STREAM_KEYS)
    point_count = len(data.get("time") or data.get("distance") or [])
    streams_db.upsert_streams(supabase, {
        "activity_id": activity_id, "athlete_id": athlete_id,
        "data": data, "resolution": "high", "point_count": point_count,
    })
    return data


def get_streams_payload(supabase, strava, athlete_id: int, activity_id: int) -> ActivityStreamsResponse:
    data = ensure_streams(supabase, strava, athlete_id, activity_id)
    return ActivityStreamsResponse(
        point_count=len(data.get("time") or data.get("distance") or []),
        time=data.get("time"),
        distance=data.get("distance"),
        altitude=data.get("altitude"),
        watts=data.get("watts"),
        heartrate=data.get("heartrate"),
        velocity_smooth=data.get("velocity_smooth"),
    )
```

> Note: do **not** add `from app.clients import build_strava` unless used. The router passes the `strava` client in via `Depends(get_strava)`.

- [ ] **Step 5: Run service test — expect PASS**

Run: `cd backend && python -m pytest tests/services/test_activities_streams.py -v`

- [ ] **Step 6: Add the router** — `app/routers/activities.py`

Add imports `ActivityStreamsResponse`, `get_strava`, `StravaClient`, then:

```python
@router.get("/{activity_id}/streams", response_model=ActivityStreamsResponse)
def activity_streams(
    activity_id: int,
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: Client = Depends(get_supabase),
    strava: StravaClient = Depends(get_strava),
) -> ActivityStreamsResponse:
    return activities_service.get_streams_payload(supabase, strava, athlete_id, activity_id)
```

> Place this route **after** `/overview` so the literal path isn't shadowed by `{activity_id}`.

- [ ] **Step 7: Write + run the router test** in `tests/routers/test_activities.py`

```python
from app.models.activities import ActivityStreamsResponse


def test_streams_requires_session(client):
    assert client.get("/activities/5/streams").status_code == 401


def test_streams_returns_body(client, monkeypatch):
    monkeypatch.setattr(activities_service, "get_streams_payload",
        lambda supabase, strava, athlete_id, activity_id:
            ActivityStreamsResponse(point_count=2, time=[0, 1], distance=[0.0, 5.0],
                                    watts=[100, 200]))
    _auth(client)
    body = client.get("/activities/5/streams").json()
    assert body["point_count"] == 2 and body["watts"] == [100, 200]
    assert body["altitude"] is None
```

Run: `cd backend && python -m pytest tests/ -v`  → all green.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/activities.py backend/app/services/activities.py backend/app/routers/activities.py backend/tests/
git commit -m "feat(activities): lazy stream fetch+cache and GET /activities/{id}/streams"
```

**INCREMENT 1 VERIFY:** With a logged-in session, `GET /activities/<real id>/streams` returns channel arrays on first call (fetched from Strava + a row appears in `activity_streams`); second call returns identical data without a Strava call. An activity with no streams returns `point_count: 0` and is not refetched.

---

## INCREMENT 2 — Hero + page shell

Goal: clickable Activities rows open `/activities/:id` showing the route map + identity + 6 primary stat tiles, theme- and unit-aware.

### Task 5: Pure stream stats (`services/analysis.py`)

**Files:**
- Create: `backend/app/services/analysis.py`
- Test: `backend/tests/services/test_analysis.py`

**Interfaces:**
- Produces (pure, no I/O):
  - `deltas(time: list[int]) -> list[float]` — per-sample Δt; first sample weight = first gap (or 1.0 for a single sample).
  - `weighted_mean(time, series) -> float | None` — Δt-weighted mean, skipping `None` samples; `None` if no valid samples.
  - `normalized_power(time, watts) -> float | None` — 30 s rolling avg → 4th power → mean → 4th root; `None` if `watts` falsy.
  - `total_work_kj(time, watts) -> float | None` — Σ(watts·Δt)/1000; `None` if `watts` falsy.

- [ ] **Step 1: Write the failing test**

```python
from app.services import analysis


def test_deltas_uses_gaps_with_first_gap_backfilled():
    assert analysis.deltas([0, 1, 3, 6]) == [1.0, 1.0, 2.0, 3.0]
    assert analysis.deltas([5]) == [1.0]
    assert analysis.deltas([]) == []


def test_weighted_mean_skips_none_and_weights_by_dt():
    # deltas([0,1,4]) = [1,1,3] (first gap back-filled); (100*1 + 200*1 + 200*3)/5 = 180
    assert analysis.weighted_mean([0, 1, 4], [100, 200, 200]) == 180.0
    # None samples are skipped (their dt excluded): (100*1 + 200*1)/(1+1) = 150
    assert analysis.weighted_mean([0, 1, 2], [100, None, 200]) == 150.0
    assert analysis.weighted_mean([0, 1, 2], [None, None, None]) is None


def test_total_work_kj():
    # 200 W held ~3600 s ≈ 720 kJ
    time = list(range(0, 3601))
    watts = [200] * 3601
    assert round(analysis.total_work_kj(time, watts)) == 720
    assert analysis.total_work_kj([0, 1], None) is None


def test_normalized_power_constant_equals_power():
    time = list(range(0, 600))
    watts = [250] * 600
    assert round(analysis.normalized_power(time, watts)) == 250


def test_normalized_power_none_without_watts():
    assert analysis.normalized_power([0, 1], None) is None
    assert analysis.normalized_power([0, 1], []) is None
```

- [ ] **Step 2: Run it — expect FAIL** (`ModuleNotFoundError`)

Run: `cd backend && python -m pytest tests/services/test_analysis.py -v`

- [ ] **Step 3: Implement** `app/services/analysis.py`

```python
"""Pure ride-analytics math. No I/O, no fastapi — heavily unit-tested."""


def deltas(time: list[int]) -> list[float]:
    """Per-sample Δt seconds. First sample is weighted by the first gap (or 1.0)."""
    if not time:
        return []
    gaps = [float(time[i] - time[i - 1]) for i in range(1, len(time))]
    first = gaps[0] if gaps else 1.0
    return [first, *gaps]


def weighted_mean(time: list[int], series: list) -> float | None:
    """Δt-weighted mean of `series`, skipping None samples. None if no valid data."""
    if not series:
        return None
    dt = deltas(time)
    total_w = 0.0
    acc = 0.0
    for w, v in zip(dt, series, strict=False):
        if v is None:
            continue
        acc += v * w
        total_w += w
    return acc / total_w if total_w > 0 else None


def total_work_kj(time: list[int], watts: list | None) -> float | None:
    """Sum of watts·Δt over the ride, in kJ. None if no watts."""
    if not watts:
        return None
    dt = deltas(time)
    joules = sum((w or 0) * d for w, d in zip(watts, dt, strict=False))
    return joules / 1000.0


def normalized_power(time: list[int], watts: list | None) -> float | None:
    """30 s rolling-avg power → 4th power → mean → 4th root. None if no watts."""
    if not watts:
        return None
    clean = [w if w is not None else 0 for w in watts]
    window = 30
    if len(clean) < window:
        avg = sum(clean) / len(clean)
        return float(avg)
    rolling = []
    running = sum(clean[:window])
    rolling.append(running / window)
    for i in range(window, len(clean)):
        running += clean[i] - clean[i - window]
        rolling.append(running / window)
    fourth = sum(p**4 for p in rolling) / len(rolling)
    return float(fourth ** 0.25)
```

- [ ] **Step 4: Run it — expect PASS**

Run: `cd backend && python -m pytest tests/services/test_analysis.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/analysis.py backend/tests/services/test_analysis.py
git commit -m "feat(analysis): pure stream stats (deltas, weighted_mean, NP, work)"
```

### Task 6: `GET /activities/{id}` detail (header + primary stats)

**Files:**
- Modify: `backend/app/db/activities.py` (add `get_activity`)
- Modify: `backend/app/models/activities.py` (add `ActivityDetailResponse`)
- Modify: `backend/app/services/activities.py` (add `ActivityNotFoundError`, `get_detail`)
- Modify: `backend/app/routers/activities.py` (add `GET /{activity_id}`)
- Test: `backend/tests/db/test_activities.py`, `tests/services/test_activities_detail.py`, `tests/routers/test_activities.py`

**Interfaces:**
- Produces:
  - `db.activities.get_activity(client, athlete_id, activity_id) -> ActivityRow | None`
  - `ActivityNotFoundError(Exception)`
  - `get_detail(supabase, strava, athlete_id, activity_id) -> ActivityDetailResponse`
  - `ActivityDetailResponse` fields: `id, name, type, start_date, start_date_local, location: str|None, distance_m, moving_time_s, elev_gain_m, avg_speed_ms: float|None, avg_power_w: float|None, normalized_power_w: float|None, work_kj: float|None, avg_hr: int|None, summary_polyline: str|None`.

- [ ] **Step 1: db test + impl** — add to `tests/db/test_activities.py`:

```python
@respx.mock
def test_get_activity_scopes_to_athlete():
    route = respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(200, json=[{"id": 5, "athlete_id": 7, "name": "Ride"}]))
    row = activities.get_activity(CLIENT, 7, 5)
    params = route.calls.last.request.url.params
    assert params["id"] == "eq.5" and params["athlete_id"] == "eq.7"
    assert row is not None and row["id"] == 5


@respx.mock
def test_get_activity_none_when_missing():
    respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(200, json=[]))
    assert activities.get_activity(CLIENT, 7, 5) is None
```

Add to `app/db/activities.py`:

```python
def get_activity(client: Client, athlete_id: int, activity_id: int) -> ActivityRow | None:
    resp = (
        client.table("activities").select("*")
        .eq("id", activity_id).eq("athlete_id", athlete_id).execute()
    )
    return cast(ActivityRow, resp.data[0]) if resp.data else None
```

Run: `cd backend && python -m pytest tests/db/test_activities.py -v` → PASS.

- [ ] **Step 2: Add the model** to `app/models/activities.py`

```python
class ActivityDetailResponse(BaseModel):
    id: int
    name: str
    type: str
    start_date: str
    start_date_local: str | None = None
    location: str | None = None
    distance_m: float
    moving_time_s: int
    elev_gain_m: float
    avg_speed_ms: float | None = None
    avg_power_w: float | None = None
    normalized_power_w: float | None = None
    work_kj: float | None = None
    avg_hr: int | None = None
    summary_polyline: str | None = None
```

- [ ] **Step 3: Write the failing service test** — `tests/services/test_activities_detail.py`

```python
import pytest
from app.services import activities as svc

ROW = {"id": 5, "athlete_id": 7, "name": "Saturday Gravel Loop", "type": "Ride",
       "start_date": "2026-06-21T14:42:00Z", "start_date_local": "2026-06-21T07:42:00",
       "distance_m": 84300.0, "moving_time_s": 11820, "elapsed_time_s": 12000,
       "elev_gain_m": 1284.0, "avg_speed_ms": 7.13, "avg_hr": 148,
       "summary_polyline": "abc"}


def test_get_detail_maps_header_and_power_stats(monkeypatch):
    monkeypatch.setattr(svc.activities_db, "get_activity", lambda c, a, aid: dict(ROW))
    monkeypatch.setattr(svc, "ensure_streams",
        lambda c, s, a, aid: {"time": [0, 1, 2], "watts": [200, 200, 200]})
    d = svc.get_detail(object(), object(), 7, 5)
    assert d.name == "Saturday Gravel Loop" and d.distance_m == 84300.0
    assert d.avg_hr == 148 and d.summary_polyline == "abc"
    assert round(d.avg_power_w) == 200
    assert d.normalized_power_w is not None and d.work_kj is not None


def test_get_detail_nulls_power_without_watts(monkeypatch):
    monkeypatch.setattr(svc.activities_db, "get_activity", lambda c, a, aid: dict(ROW))
    monkeypatch.setattr(svc, "ensure_streams", lambda c, s, a, aid: {"time": [0, 1]})
    d = svc.get_detail(object(), object(), 7, 5)
    assert d.avg_power_w is None and d.normalized_power_w is None and d.work_kj is None


def test_get_detail_raises_when_missing(monkeypatch):
    monkeypatch.setattr(svc.activities_db, "get_activity", lambda c, a, aid: None)
    with pytest.raises(svc.ActivityNotFoundError):
        svc.get_detail(object(), object(), 7, 5)
```

- [ ] **Step 4: Run it — expect FAIL**

Run: `cd backend && python -m pytest tests/services/test_activities_detail.py -v`

- [ ] **Step 5: Implement** — add to `app/services/activities.py`

```python
from app.models.activities import ActivityDetailResponse
from app.services import analysis


class ActivityNotFoundError(Exception):
    """Raised when an activity does not exist for the requesting athlete."""


def get_detail(supabase, strava, athlete_id: int, activity_id: int) -> ActivityDetailResponse:
    row = activities_db.get_activity(supabase, athlete_id, activity_id)
    if row is None:
        raise ActivityNotFoundError(f"activity {activity_id} not found for athlete")
    data = ensure_streams(supabase, strava, athlete_id, activity_id)
    time = data.get("time") or []
    watts = data.get("watts")
    return ActivityDetailResponse(
        id=row["id"], name=row["name"], type=row["type"],
        start_date=row["start_date"], start_date_local=row.get("start_date_local"),
        location=None,
        distance_m=row["distance_m"], moving_time_s=row["moving_time_s"],
        elev_gain_m=row["elev_gain_m"], avg_speed_ms=row.get("avg_speed_ms"),
        avg_power_w=analysis.weighted_mean(time, watts) if watts else None,
        normalized_power_w=analysis.normalized_power(time, watts),
        work_kj=analysis.total_work_kj(time, watts),
        avg_hr=row.get("avg_hr"),
        summary_polyline=row.get("summary_polyline"),
    )
```

- [ ] **Step 6: Run service test — expect PASS**

Run: `cd backend && python -m pytest tests/services/test_activities_detail.py -v`

- [ ] **Step 7: Add the router** — `app/routers/activities.py` (after `/overview`, before `/{activity_id}/streams` is fine; both are siblings)

```python
from fastapi import HTTPException
from app.models.activities import ActivityDetailResponse


@router.get("/{activity_id}", response_model=ActivityDetailResponse)
def activity_detail(
    activity_id: int,
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: Client = Depends(get_supabase),
    strava: StravaClient = Depends(get_strava),
) -> ActivityDetailResponse:
    try:
        return activities_service.get_detail(supabase, strava, athlete_id, activity_id)
    except activities_service.ActivityNotFoundError:
        raise HTTPException(status_code=404, detail="Activity not found")
```

- [ ] **Step 8: Router tests** — add to `tests/routers/test_activities.py`

```python
from app.models.activities import ActivityDetailResponse


def _detail() -> ActivityDetailResponse:
    return ActivityDetailResponse(
        id=5, name="Gravel", type="Ride", start_date="2026-06-21T14:42:00Z",
        distance_m=84300.0, moving_time_s=11820, elev_gain_m=1284.0,
        avg_speed_ms=7.13, avg_power_w=198.0, normalized_power_w=221.0,
        work_kj=2342.0, avg_hr=148, summary_polyline="abc")


def test_detail_requires_session(client):
    assert client.get("/activities/5").status_code == 401


def test_detail_returns_body(client, monkeypatch):
    monkeypatch.setattr(activities_service, "get_detail",
        lambda supabase, strava, athlete_id, activity_id: _detail())
    _auth(client)
    body = client.get("/activities/5").json()
    assert body["name"] == "Gravel" and body["avg_hr"] == 148


def test_detail_404_when_missing(client, monkeypatch):
    def boom(*a, **k): raise activities_service.ActivityNotFoundError("nope")
    monkeypatch.setattr(activities_service, "get_detail", boom)
    _auth(client)
    assert client.get("/activities/5").status_code == 404
```

Run: `cd backend && python -m pytest tests/ -v` → all green.

- [ ] **Step 9: Commit**

```bash
git add backend/app/ backend/tests/
git commit -m "feat(activities): GET /activities/{id} detail (header + power stats)"
```

### Task 7: Frontend types + api data layer

**Files:**
- Create: `frontend/src/types/activity-detail.ts`
- Create: `frontend/src/api/activity-detail.ts`
- Test: `frontend/src/api/activity-detail.test.ts`

**Interfaces:**
- Produces:
  - DTOs: `ActivityDetailDTO` (mirrors backend `ActivityDetailResponse`), `ActivityStreamsDTO` (mirrors `ActivityStreamsResponse`), `PrimaryStat { label: string; value: string; unit: string }`.
  - `fetchActivityDetail(id: number): Promise<ActivityDetailDTO>`, `useActivityDetail(id)`.
  - `fetchActivityStreams(id: number): Promise<ActivityStreamsDTO>`, `useActivityStreams(id)`.
  - `toPrimaryStats(d: ActivityDetailDTO, units: Units): PrimaryStat[]` — the 6 hero tiles.
  - `metaLabel(d: ActivityDetailDTO): string` — e.g. `"Sat · Jun 21, 2026 · 7:42 AM"` from `start_date_local ?? start_date`.

- [ ] **Step 1: Write the failing test** — `frontend/src/api/activity-detail.test.ts`

```ts
import { describe, expect, it } from "vitest";
import type { ActivityDetailDTO } from "@/types/activity-detail";
import { metaLabel, toPrimaryStats } from "./activity-detail";

const d = (o: Partial<ActivityDetailDTO> = {}): ActivityDetailDTO => ({
  id: 5, name: "Gravel", type: "Ride",
  start_date: "2026-06-21T14:42:00Z", start_date_local: "2026-06-21T07:42:00",
  location: null, distance_m: 84300, moving_time_s: 11820, elev_gain_m: 1284,
  avg_speed_ms: 7.13, avg_power_w: 198, normalized_power_w: 221, work_kj: 2342,
  avg_hr: 148, summary_polyline: "abc", ...o,
});

describe("toPrimaryStats", () => {
  it("builds 6 tiles in metric", () => {
    const s = toPrimaryStats(d(), "metric");
    expect(s.map((t) => t.label)).toEqual([
      "DISTANCE", "MOVING TIME", "ELEV GAIN", "AVG POWER", "AVG SPEED", "WORK",
    ]);
    expect(s[0]).toEqual({ label: "DISTANCE", value: "84.3", unit: "km" });
    expect(s[2]).toEqual({ label: "ELEV GAIN", value: "1,284", unit: "m" });
    expect(s[3]).toEqual({ label: "AVG POWER", value: "198", unit: "W" });
    expect(s[5]).toEqual({ label: "WORK", value: "2,342", unit: "kJ" });
  });
  it("shows em dash when power is missing", () => {
    const s = toPrimaryStats(d({ avg_power_w: null, work_kj: null }), "metric");
    expect(s[3].value).toBe("—");
    expect(s[5].value).toBe("—");
  });
  it("converts distance for imperial", () => {
    expect(toPrimaryStats(d(), "imperial")[0].unit).toBe("mi");
  });
});

describe("metaLabel", () => {
  it("formats the local date/time", () => {
    expect(metaLabel(d())).toBe("Sat · Jun 21, 2026 · 7:42 AM");
  });
});
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `cd frontend && npx vitest run src/api/activity-detail.test.ts`

- [ ] **Step 3: Implement types** — `frontend/src/types/activity-detail.ts`

```ts
export interface ActivityDetailDTO {
  id: number;
  name: string;
  type: string;
  start_date: string;
  start_date_local: string | null;
  location: string | null;
  distance_m: number;
  moving_time_s: number;
  elev_gain_m: number;
  avg_speed_ms: number | null;
  avg_power_w: number | null;
  normalized_power_w: number | null;
  work_kj: number | null;
  avg_hr: number | null;
  summary_polyline: string | null;
}

export interface ActivityStreamsDTO {
  point_count: number;
  time: number[] | null;
  distance: number[] | null;
  altitude: number[] | null;
  watts: (number | null)[] | null;
  heartrate: (number | null)[] | null;
  velocity_smooth: number[] | null;
}

export interface PrimaryStat {
  label: string;
  value: string;
  unit: string;
}
```

- [ ] **Step 4: Implement api** — `frontend/src/api/activity-detail.ts`

```ts
import { useQuery } from "@tanstack/react-query";
import { fmtDuration } from "@/lib/format";
import { fmtDistance, fmtElevation, fmtSpeed, type Units } from "@/lib/units";
import type {
  ActivityDetailDTO, ActivityStreamsDTO, PrimaryStat,
} from "@/types/activity-detail";
import { apiFetch } from "./client";

const WD = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MO = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "Sat · Jun 21, 2026 · 7:42 AM" from start_date_local (fallback start_date). */
export function metaLabel(d: ActivityDetailDTO): string {
  // start_date_local is a naive wall-clock string (no zone); start_date ends in Z.
  // Append Z to naive strings so `new Date` parses them as UTC and getUTC* returns
  // the intended wall-clock components regardless of the machine's timezone.
  const raw = d.start_date_local ?? d.start_date;
  const iso = raw.endsWith("Z") || /[+-]\d\d:\d\d$/.test(raw) ? raw : `${raw}Z`;
  const t = new Date(iso);
  const h = t.getUTCHours();
  const m = t.getUTCMinutes();
  const ampm = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 === 0 ? 12 : h % 12;
  const clock = `${h12}:${String(m).padStart(2, "0")} ${ampm}`;
  return `${WD[t.getUTCDay()]} · ${MO[t.getUTCMonth()]} ${t.getUTCDate()}, ${t.getUTCFullYear()} · ${clock}`;
}

export function toPrimaryStats(d: ActivityDetailDTO, units: Units): PrimaryStat[] {
  const dist = fmtDistance(d.distance_m, units);
  const elev = fmtElevation(d.elev_gain_m, units);
  const speed = d.avg_speed_ms === null
    ? { value: "—", unit: "" } : fmtSpeed(d.avg_speed_ms, units);
  const round = (v: number | null) =>
    v === null ? "—" : Math.round(v).toLocaleString("en-US");
  return [
    { label: "DISTANCE", value: dist.value, unit: dist.unit },
    { label: "MOVING TIME", value: fmtDuration(d.moving_time_s), unit: "" },
    { label: "ELEV GAIN", value: elev.value, unit: elev.unit },
    { label: "AVG POWER", value: round(d.avg_power_w), unit: "W" },
    { label: "AVG SPEED", value: speed.value, unit: speed.unit },
    { label: "WORK", value: round(d.work_kj), unit: "kJ" },
  ];
}

export function fetchActivityDetail(id: number): Promise<ActivityDetailDTO> {
  return apiFetch<ActivityDetailDTO>(`/activities/${id}`);
}

export function useActivityDetail(id: number) {
  return useQuery({
    queryKey: ["activities", "detail", id],
    queryFn: () => fetchActivityDetail(id),
  });
}

export function fetchActivityStreams(id: number): Promise<ActivityStreamsDTO> {
  return apiFetch<ActivityStreamsDTO>(`/activities/${id}/streams`);
}

export function useActivityStreams(id: number) {
  return useQuery({
    queryKey: ["activities", "streams", id],
    queryFn: () => fetchActivityStreams(id),
  });
}
```

- [ ] **Step 5: Run it — expect PASS**

Run: `cd frontend && npx vitest run src/api/activity-detail.test.ts`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/activity-detail.ts frontend/src/api/activity-detail.ts frontend/src/api/activity-detail.test.ts
git commit -m "feat(web): activity-detail types + api data layer"
```

### Task 8: `lib/polyline.ts` — decode + normalize

**Files:**
- Create: `frontend/src/lib/polyline.ts`
- Test: `frontend/src/lib/polyline.test.ts`

**Interfaces:**
- Produces:
  - `decodePolyline(encoded: string): [number, number][]` — `[lat, lng]` pairs (Google encoded-polyline algorithm, precision 5).
  - `type LatLng = [number, number]`
  - `boundsOf(points: LatLng[]): { south: number; west: number; north: number; east: number } | null`

- [ ] **Step 1: Write the failing test** — `frontend/src/lib/polyline.test.ts`

```ts
import { describe, expect, it } from "vitest";
import { boundsOf, decodePolyline } from "./polyline";

describe("decodePolyline", () => {
  it("decodes the canonical Google example", () => {
    // "_p~iF~ps|U_ulLnnqC_mqNvxq`@" -> known reference points
    const pts = decodePolyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@");
    expect(pts.length).toBe(3);
    expect(pts[0][0]).toBeCloseTo(38.5, 5);
    expect(pts[0][1]).toBeCloseTo(-120.2, 5);
    expect(pts[1][0]).toBeCloseTo(40.7, 5);
    expect(pts[2][1]).toBeCloseTo(-126.453, 3);
  });
  it("returns [] for empty input", () => {
    expect(decodePolyline("")).toEqual([]);
  });
});

describe("boundsOf", () => {
  it("computes the bounding box", () => {
    expect(boundsOf([[1, 2], [3, -1], [-2, 5]])).toEqual({
      south: -2, west: -1, north: 3, east: 5,
    });
  });
  it("returns null for no points", () => {
    expect(boundsOf([])).toBeNull();
  });
});
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `cd frontend && npx vitest run src/lib/polyline.test.ts`

- [ ] **Step 3: Implement** `frontend/src/lib/polyline.ts`

```ts
export type LatLng = [number, number];

/** Decode a Google encoded polyline (precision 5) into [lat, lng] pairs. */
export function decodePolyline(encoded: string): LatLng[] {
  const points: LatLng[] = [];
  let index = 0;
  let lat = 0;
  let lng = 0;
  while (index < encoded.length) {
    let result = 0;
    let shift = 0;
    let byte: number;
    do {
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    lat += result & 1 ? ~(result >> 1) : result >> 1;
    result = 0;
    shift = 0;
    do {
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    lng += result & 1 ? ~(result >> 1) : result >> 1;
    points.push([lat / 1e5, lng / 1e5]);
  }
  return points;
}

export function boundsOf(points: LatLng[]) {
  if (points.length === 0) return null;
  let south = points[0][0];
  let north = points[0][0];
  let west = points[0][1];
  let east = points[0][1];
  for (const [la, ln] of points) {
    south = Math.min(south, la);
    north = Math.max(north, la);
    west = Math.min(west, ln);
    east = Math.max(east, ln);
  }
  return { south, west, north, east };
}
```

- [ ] **Step 4: Run it — expect PASS**

Run: `cd frontend && npx vitest run src/lib/polyline.test.ts`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/polyline.ts frontend/src/lib/polyline.test.ts
git commit -m "feat(web): polyline decode + bounds (renderer-agnostic)"
```

### Task 9: `lib/map-tiles.ts` + `RouteHero`

**Files:**
- Create: `frontend/src/lib/map-tiles.ts`
- Create: `frontend/src/pages/activity-detail/components/RouteHero.tsx`
- Modify: `frontend/src/index.css` (one line — import Leaflet CSS) OR import in `RouteHero`
- Test: `frontend/src/pages/activity-detail/components/RouteHero.test.tsx`

**Interfaces:**
- Consumes: `decodePolyline`, `boundsOf` (Task 8), `ActivityDetailDTO`, `metaLabel` (Task 7), `useSettings` (`isDark`).
- Produces: `mapTiles: { light: { url; attribution }, dark: { url; attribution } }`; `RouteHero({ detail }: { detail: ActivityDetailDTO })` default export.

- [ ] **Step 1: Implement tiles config** — `frontend/src/lib/map-tiles.ts`

```ts
/** Theme-matched raster basemaps. Swap to a keyed provider here later. */
export const mapTiles = {
  light: {
    url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    attribution: '&copy; OpenStreetMap &copy; CARTO',
  },
  dark: {
    url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    attribution: '&copy; OpenStreetMap &copy; CARTO',
  },
} as const;
```

- [ ] **Step 2: Write the failing test** — `RouteHero.test.tsx`

react-leaflet can't render in jsdom, so mock it to record props:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ActivityDetailDTO } from "@/types/activity-detail";

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="map">{children}</div>,
  TileLayer: ({ url }: { url: string }) => <div data-testid="tiles" data-url={url} />,
  Polyline: () => <div data-testid="route" />,
  CircleMarker: () => <div data-testid="marker" />,
  useMap: () => ({ fitBounds: vi.fn() }),
}));
vi.mock("@/app/providers/settings-context", () => ({ useSettings: () => ({ isDark: true }) }));

import RouteHero from "./RouteHero";

const detail: ActivityDetailDTO = {
  id: 5, name: "Saturday Gravel Loop", type: "Ride",
  start_date: "2026-06-21T14:42:00Z", start_date_local: "2026-06-21T07:42:00",
  location: "Marin Headlands", distance_m: 84300, moving_time_s: 11820, elev_gain_m: 1284,
  avg_speed_ms: 7.13, avg_power_w: 198, normalized_power_w: 221, work_kj: 2342,
  avg_hr: 148, summary_polyline: "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
};

describe("RouteHero", () => {
  it("renders the dark tiles, route, and caption", () => {
    render(<RouteHero detail={detail} />);
    expect(screen.getByTestId("tiles").getAttribute("data-url")).toContain("dark_all");
    expect(screen.getByTestId("route")).toBeInTheDocument();
    expect(screen.getByText("Saturday Gravel Loop")).toBeInTheDocument();
    expect(screen.getByText("RIDE")).toBeInTheDocument();
  });

  it("shows the caption over a panel when there is no polyline", () => {
    render(<RouteHero detail={{ ...detail, summary_polyline: null }} />);
    expect(screen.queryByTestId("map")).not.toBeInTheDocument();
    expect(screen.getByText("Saturday Gravel Loop")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run it — expect FAIL**

Run: `cd frontend && npx vitest run src/pages/activity-detail/components/RouteHero.test.tsx`

- [ ] **Step 4: Implement** `RouteHero.tsx`

```tsx
import "leaflet/dist/leaflet.css";
import { useEffect } from "react";
import { CircleMarker, MapContainer, Polyline, TileLayer, useMap } from "react-leaflet";
import { useSettings } from "@/app/providers/settings-context";
import { mapTiles } from "@/lib/map-tiles";
import { boundsOf, decodePolyline, type LatLng } from "@/lib/polyline";
import { metaLabel } from "@/api/activity-detail";
import type { ActivityDetailDTO } from "@/types/activity-detail";

function FitBounds({ points }: { points: LatLng[] }) {
  const map = useMap();
  useEffect(() => {
    const b = boundsOf(points);
    if (b) map.fitBounds([[b.south, b.west], [b.north, b.east]], { padding: [24, 24] });
  }, [map, points]);
  return null;
}

function Caption({ detail }: { detail: ActivityDetailDTO }) {
  return (
    <div className="absolute left-0 right-0 bottom-0 px-[22px] pt-[46px] pb-[18px] z-[500]
                    bg-gradient-to-t from-surface-panel2 via-surface-panel2/80 to-transparent">
      <div className="flex items-center gap-[10px] mb-2">
        <span className="font-mono text-[9.5px] tracking-[0.1em] text-strava bg-strava-soft px-[9px] py-[3px] rounded-md uppercase">
          {detail.type}
        </span>
        <span className="font-mono text-[11px] text-subtle">{metaLabel(detail)}</span>
      </div>
      <div className="font-display font-semibold text-[26px] leading-[1.1] tracking-[-0.01em] text-ink">
        {detail.name}
      </div>
      {detail.location && (
        <div className="text-[13px] text-body mt-1">{detail.location}</div>
      )}
    </div>
  );
}

export default function RouteHero({ detail }: { detail: ActivityDetailDTO }) {
  const { isDark } = useSettings();
  const tiles = isDark ? mapTiles.dark : mapTiles.light;
  const points = detail.summary_polyline ? decodePolyline(detail.summary_polyline) : [];
  const start = points[0];
  const end = points[points.length - 1];

  return (
    <div className="relative bg-surface-panel2 border border-line rounded-[18px] overflow-hidden min-h-[330px]">
      {points.length > 0 && (
        <MapContainer
          className="absolute inset-0 h-full w-full"
          zoomControl={false}
          attributionControl
          dragging={false}
          scrollWheelZoom={false}
          doubleClickZoom={false}
          center={start}
          zoom={12}
        >
          <TileLayer url={tiles.url} attribution={tiles.attribution} />
          <Polyline positions={points} pathOptions={{ color: "#fc4c02", weight: 4 }} />
          {start && <CircleMarker center={start} radius={6}
            pathOptions={{ color: "#fff", weight: 2, fillColor: "#34d399", fillOpacity: 1 }} />}
          {end && <CircleMarker center={end} radius={6}
            pathOptions={{ color: "#fff", weight: 2, fillColor: "#fc4c02", fillOpacity: 1 }} />}
          <FitBounds points={points} />
        </MapContainer>
      )}
      <span className="absolute top-[14px] left-4 z-[500] font-mono text-[10px] tracking-[0.1em] text-white bg-black/70 px-[9px] py-[5px] rounded-md">
        GPS ROUTE
      </span>
      <Caption detail={detail} />
    </div>
  );
}
```

> Note: the caption uppercases via CSS `uppercase`; the test asserts `"RIDE"` so set the badge content to `detail.type` and rely on the `uppercase` class (jsdom preserves text content as `"Ride"` — **change the assertion to `getByText("Ride")`** if running jsdom, since CSS text-transform doesn't alter `textContent`). Use `getByText("Ride")` in the test.

- [ ] **Step 5: Fix the test assertion** to `expect(screen.getByText("Ride"))` (CSS uppercase doesn't change `textContent`), then run — expect PASS.

Run: `cd frontend && npx vitest run src/pages/activity-detail/components/RouteHero.test.tsx`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/map-tiles.ts frontend/src/pages/activity-detail/components/RouteHero.tsx frontend/src/pages/activity-detail/components/RouteHero.test.tsx
git commit -m "feat(web): RouteHero leaflet map + themed tiles + route overlay"
```

### Task 10: `PrimaryStats` component

**Files:**
- Create: `frontend/src/pages/activity-detail/components/PrimaryStats.tsx`
- Test: `frontend/src/pages/activity-detail/components/PrimaryStats.test.tsx`

**Interfaces:**
- Consumes: `PrimaryStat` (Task 7).
- Produces: `PrimaryStats({ stats }: { stats: PrimaryStat[] })`.

- [ ] **Step 1: Write the failing test**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PrimaryStats } from "./PrimaryStats";

describe("PrimaryStats", () => {
  it("renders each tile's label, value, and unit", () => {
    render(<PrimaryStats stats={[
      { label: "DISTANCE", value: "84.3", unit: "km" },
      { label: "AVG POWER", value: "198", unit: "W" },
    ]} />);
    expect(screen.getByText("DISTANCE")).toBeInTheDocument();
    expect(screen.getByText("84.3")).toBeInTheDocument();
    expect(screen.getByText("km")).toBeInTheDocument();
    expect(screen.getByText("198")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run — expect FAIL.** `cd frontend && npx vitest run src/pages/activity-detail/components/PrimaryStats.test.tsx`

- [ ] **Step 3: Implement** `PrimaryStats.tsx`

```tsx
import type { PrimaryStat } from "@/types/activity-detail";

export function PrimaryStats({ stats }: { stats: PrimaryStat[] }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      {stats.map((s) => (
        <div key={s.label} className="bg-surface-card border border-line rounded-[14px] px-[17px] py-[15px] flex flex-col justify-center">
          <div className="font-mono text-[9px] tracking-[0.1em] text-subtle mb-2">{s.label}</div>
          <div className="font-display font-semibold text-[23px] leading-none tracking-[-0.01em] text-ink">
            {s.value}
            {s.unit && <span className="text-[12px] text-body font-normal"> {s.unit}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run — expect PASS.**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/activity-detail/components/PrimaryStats.tsx frontend/src/pages/activity-detail/components/PrimaryStats.test.tsx
git commit -m "feat(web): PrimaryStats hero tiles"
```

### Task 11: Page + route + clickable rows

**Files:**
- Create: `frontend/src/pages/activity-detail/ActivityDetailPage.tsx`
- Test: `frontend/src/pages/activity-detail/ActivityDetailPage.test.tsx`
- Modify: `frontend/src/app/router.tsx` (add route)
- Modify: `frontend/src/app/router.test.tsx` (assert route renders)
- Modify: `frontend/src/pages/activities/components/ActivityTable.tsx` (wrap rows in `<Link>`)
- Modify: `frontend/src/pages/activities/ActivitiesPage.test.tsx` (assert link target if it checks rows)

**Interfaces:**
- Consumes: `useActivityDetail`, `toPrimaryStats`, `RouteHero`, `PrimaryStats`, `AppShell`, `useAthlete`, `useSyncStatus`, `useSettings`.

- [ ] **Step 1: Add the route** — `app/router.tsx`

Add import `import ActivityDetailPage from "@/pages/activity-detail/ActivityDetailPage";` and the route **before** `*`:

```tsx
  { path: "/activities/:id", element: <ActivityDetailPage /> },
```

- [ ] **Step 2: Write the failing page test** — `ActivityDetailPage.test.tsx`

```tsx
import { screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/providers";
import type { ActivityDetailDTO } from "@/types/activity-detail";

vi.mock("react-router", async () => {
  const actual = await vi.importActual<typeof import("react-router")>("react-router");
  return { ...actual, useNavigate: () => vi.fn(), useParams: () => ({ id: "5" }) };
});
vi.mock("@/api/auth", () => ({ useAthlete: () => ({ data: { id: 9, name: "Ada", avatar_url: null, settings: {} }, error: null }), logout: vi.fn() }));
vi.mock("@/api/sync", () => ({ useSyncStatus: () => ({ data: { status: "idle" } }) }));
vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TileLayer: () => null, Polyline: () => null, CircleMarker: () => null, useMap: () => ({ fitBounds: vi.fn() }),
}));
const useActivityDetail = vi.fn();
const useActivityStreams = vi.fn();
vi.mock("@/api/activity-detail", async () => {
  const actual = await vi.importActual<typeof import("@/api/activity-detail")>("@/api/activity-detail");
  return { ...actual, useActivityDetail: (id: number) => useActivityDetail(id), useActivityStreams: (id: number) => useActivityStreams(id) };
});

import ActivityDetailPage from "./ActivityDetailPage";

const detail: ActivityDetailDTO = {
  id: 5, name: "Saturday Gravel Loop", type: "Ride",
  start_date: "2026-06-21T14:42:00Z", start_date_local: "2026-06-21T07:42:00",
  location: null, distance_m: 84300, moving_time_s: 11820, elev_gain_m: 1284,
  avg_speed_ms: 7.13, avg_power_w: 198, normalized_power_w: 221, work_kj: 2342,
  avg_hr: 148, summary_polyline: "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
};

beforeEach(() => {
  useActivityDetail.mockReturnValue({ data: detail, isLoading: false, error: null });
  useActivityStreams.mockReturnValue({ data: undefined, isLoading: true });
});
afterEach(() => vi.clearAllMocks());

describe("ActivityDetailPage", () => {
  it("renders the title and primary stats", () => {
    renderWithProviders(<MemoryRouter><ActivityDetailPage /></MemoryRouter>);
    expect(screen.getByText("Saturday Gravel Loop")).toBeInTheDocument();
    expect(screen.getByText("84.3")).toBeInTheDocument();
    expect(screen.getByText("DISTANCE")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run — expect FAIL.** `cd frontend && npx vitest run src/pages/activity-detail/ActivityDetailPage.test.tsx`

- [ ] **Step 4: Implement** `ActivityDetailPage.tsx`

```tsx
import { useNavigate, useParams } from "react-router";
import { logout, useAthlete } from "@/api/auth";
import { useActivityDetail, toPrimaryStats } from "@/api/activity-detail";
import { useSyncStatus } from "@/api/sync";
import { useSettings } from "@/app/providers/settings-context";
import { AppShell } from "@/components/app-shell/AppShell";
import RouteHero from "./components/RouteHero";
import { PrimaryStats } from "./components/PrimaryStats";

export default function ActivityDetailPage() {
  const { id } = useParams();
  const activityId = Number(id);
  const { data: athlete } = useAthlete();
  const { data: status } = useSyncStatus();
  const { data: detail, isLoading, error } = useActivityDetail(activityId);
  const { units } = useSettings();
  const navigate = useNavigate();
  const handleLogout = async () => { await logout(); navigate("/", { replace: true }); };

  return (
    <AppShell
      navActive="Activities"
      athlete={athlete ?? null}
      syncLabel={status?.status === "idle" ? "Up to date" : "Syncing…"}
      onLogout={handleLogout}
      title={detail?.name ?? "Activity"}
      subtitle="RIDE DETAIL"
      backTo="/activities"
    >
      <div className="h-full overflow-y-auto p-7">
        {isLoading || !detail ? (
          error ? (
            <div className="text-subtle text-[14px] py-12 text-center">Activity not found.</div>
          ) : (
            <div role="status" aria-label="Loading activity" className="h-[330px] rounded-[18px] bg-skel animate-pkskel" />
          )
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-4 mb-4">
            <RouteHero detail={detail} />
            <PrimaryStats stats={toPrimaryStats(detail, units)} />
          </div>
        )}
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 5: Run page test — expect PASS.**

- [ ] **Step 6: Make rows clickable** — in `ActivityTable.tsx`, wrap each row. Add `import { Link } from "react-router";` and change the row `<div key={r.id} ...>` to:

```tsx
        <Link
          key={r.id}
          to={`/activities/${r.id}`}
          className={`${grid} px-[18px] py-[15px] rounded-[11px] hover:bg-surface-inset transition-colors`}
        >
```

…and close with `</Link>` instead of the row `</div>`. (Keep the inner cells unchanged; `grid` provides `display:grid`, valid on an `<a>`.)

- [ ] **Step 7: Update `router.test.tsx`** — add an assertion that `/activities/5` mounts the detail page. Mirror the existing route-table test; if it iterates known paths, add `"/activities/5"` expecting it not to render `NotFoundPage`. Run the existing test file to confirm shape, then add the case.

- [ ] **Step 8: Run the whole frontend suite + lint + build**

Run: `cd frontend && npm test && npm run lint && npm run build` → all green. Fix any `ActivitiesPage.test.tsx` row assertions that now find an `<a>` (query by role `link` with name, or by text — adjust as needed).

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/activity-detail/ frontend/src/app/router.tsx frontend/src/app/router.test.tsx frontend/src/pages/activities/
git commit -m "feat(web): activity detail page, route, clickable activity rows"
```

**INCREMENT 2 VERIFY:** `cd frontend && npm run dev`, log in, open Activities, click a ride → detail page shows the route on a CARTO map (Positron in light, Dark Matter in dark — toggle theme to confirm) with green-start/orange-end markers and the six stat tiles in the chosen units. A ride with no GPS shows the caption over a plain panel without errors.

---

## INCREMENT 3 — Charts (power + elevation)

Goal: render watts-over-distance (with avg + NP lines) and altitude-over-distance from the streams hook.

### Task 12: Chart-point transform in the api layer

**Files:**
- Modify: `frontend/src/api/activity-detail.ts` (add `toChartPoints`)
- Test: `frontend/src/api/activity-detail.test.ts` (append)

**Interfaces:**
- Produces:
  - `interface ChartPoint { x: number; y: number }` (x = display distance, y = value)
  - `toChartPoints(distance: number[] | null, series: (number|null)[] | null, units: Units, opts?: { maxPoints?: number }): ChartPoint[]` — downsamples to ≤ `maxPoints` (default 320), converts distance m→km/mi, drops null y.
  - `xAxisLabels(distanceMeters: number, units: Units): string[]` — 5 labels `[0, .25, .5, .75, 1]·dist`.

- [ ] **Step 1: Write the failing test** (append)

```ts
import { toChartPoints, xAxisLabels } from "./activity-detail";

describe("toChartPoints", () => {
  it("converts distance to km and pairs with the series", () => {
    const pts = toChartPoints([0, 1000, 2000], [100, 150, 200], "metric");
    expect(pts).toEqual([{ x: 0, y: 100 }, { x: 1, y: 150 }, { x: 2, y: 200 }]);
  });
  it("downsamples to maxPoints", () => {
    const d = Array.from({ length: 1000 }, (_, i) => i);
    const s = Array.from({ length: 1000 }, () => 200);
    expect(toChartPoints(d, s, "metric", { maxPoints: 100 }).length).toBeLessThanOrEqual(100);
  });
  it("is empty when a channel is null", () => {
    expect(toChartPoints(null, [1, 2], "metric")).toEqual([]);
    expect(toChartPoints([0, 1], null, "metric")).toEqual([]);
  });
});

describe("xAxisLabels", () => {
  it("returns 5 quarter labels", () => {
    expect(xAxisLabels(84300, "metric")).toEqual(["0.0", "21.1", "42.2", "63.2", "84.3"]);
  });
});
```

- [ ] **Step 2: Run — expect FAIL.** `cd frontend && npx vitest run src/api/activity-detail.test.ts`

- [ ] **Step 3: Implement** — append to `api/activity-detail.ts`

```ts
import { fmtDistance } from "@/lib/units"; // already imported above — reuse

export interface ChartPoint { x: number; y: number }

export function toChartPoints(
  distance: number[] | null,
  series: (number | null)[] | null,
  units: Units,
  opts: { maxPoints?: number } = {},
): ChartPoint[] {
  if (!distance || !series) return [];
  const max = opts.maxPoints ?? 320;
  const n = Math.min(distance.length, series.length);
  const stride = Math.max(1, Math.ceil(n / max));
  const toX = (m: number) =>
    units === "imperial" ? m / 1609.344 : m / 1000;
  const out: ChartPoint[] = [];
  for (let i = 0; i < n; i += stride) {
    const y = series[i];
    if (y === null || y === undefined) continue;
    out.push({ x: Number(toX(distance[i]).toFixed(3)), y });
  }
  return out;
}

export function xAxisLabels(distanceMeters: number, units: Units): string[] {
  return [0, 0.25, 0.5, 0.75, 1].map(
    (f) => fmtDistance(distanceMeters * f, units).value,
  );
}
```

- [ ] **Step 4: Run — expect PASS.** Commit:

```bash
git add frontend/src/api/activity-detail.ts frontend/src/api/activity-detail.test.ts
git commit -m "feat(web): chart-point transform + x-axis labels"
```

### Task 13: `PowerChart` + `ElevationChart`

**Files:**
- Create: `frontend/src/pages/activity-detail/components/PowerChart.tsx`
- Create: `frontend/src/pages/activity-detail/components/ElevationChart.tsx`
- Test: `frontend/src/pages/activity-detail/components/Charts.test.tsx`
- Modify: `ActivityDetailPage.tsx` (render them from the streams hook)

**Interfaces:**
- Consumes: `ChartPoint`, `toChartPoints`, `xAxisLabels`, `useActivityStreams`, `ActivityDetailDTO`, `useSettings`.
- Produces: `PowerChart({ detail, streams })`, `ElevationChart({ detail, streams })` where `streams: ActivityStreamsDTO | undefined`.

Follow the `WeekChart` pattern: `ResponsiveContainer` + `AreaChart` + `linearGradient` + custom mono ticks; pass color literals keyed on `isDark`. Use `ReferenceLine` for avg + NP. Recharts renders nothing in jsdom (zero size), so tests assert the **header/legend text + empty states**, not SVG paths.

- [ ] **Step 1: Write the failing test** — `Charts.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ActivityDetailDTO, ActivityStreamsDTO } from "@/types/activity-detail";

vi.mock("@/app/providers/settings-context", () => ({ useSettings: () => ({ isDark: true, units: "metric" }) }));

import { PowerChart } from "./PowerChart";
import { ElevationChart } from "./ElevationChart";

const detail = { distance_m: 84300, avg_power_w: 198, normalized_power_w: 221 } as ActivityDetailDTO;
const streams: ActivityStreamsDTO = {
  point_count: 3, time: [0, 1, 2], distance: [0, 1000, 2000],
  altitude: [10, 20, 15], watts: [100, 200, 150], heartrate: null, velocity_smooth: null,
};

describe("charts", () => {
  it("PowerChart shows avg + NP legend", () => {
    render(<PowerChart detail={detail} streams={streams} />);
    expect(screen.getByText(/AVG 198 W/)).toBeInTheDocument();
    expect(screen.getByText(/NP 221 W/)).toBeInTheDocument();
  });
  it("PowerChart shows an empty state without watts", () => {
    render(<PowerChart detail={detail} streams={{ ...streams, watts: null }} />);
    expect(screen.getByText(/No power data/i)).toBeInTheDocument();
  });
  it("ElevationChart renders its title", () => {
    render(<ElevationChart detail={detail} streams={streams} />);
    expect(screen.getByText("Elevation profile")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run — expect FAIL.** `cd frontend && npx vitest run src/pages/activity-detail/components/Charts.test.tsx`

- [ ] **Step 3: Implement** `PowerChart.tsx`

```tsx
import { Area, AreaChart, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { toChartPoints } from "@/api/activity-detail";
import { useSettings } from "@/app/providers/settings-context";
import type { ActivityDetailDTO, ActivityStreamsDTO } from "@/types/activity-detail";

const card = "bg-surface-card border border-line rounded-[16px] px-[22px] py-5 mb-4";
const title = "font-display font-medium text-[15px] text-ink";
const meta = "font-mono text-[11px] text-faint";

export function PowerChart({ detail, streams }: { detail: ActivityDetailDTO; streams?: ActivityStreamsDTO }) {
  const { isDark } = useSettings();
  const pts = toChartPoints(streams?.distance ?? null, streams?.watts ?? null, "metric");
  const gridColor = isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.08)";
  return (
    <div className={card}>
      <div className="flex items-center justify-between mb-3.5">
        <span className={title}>Power</span>
        <div className={`flex items-center gap-4 ${meta}`}>
          {detail.avg_power_w !== null && (
            <span className="flex items-center gap-1.5"><span className="w-3.5 h-0.5 bg-strava" />AVG {Math.round(detail.avg_power_w)} W</span>
          )}
          {detail.normalized_power_w !== null && (
            <span className="flex items-center gap-1.5"><span className="w-3.5 border-t-2 border-dashed border-subtle" />NP {Math.round(detail.normalized_power_w)} W</span>
          )}
        </div>
      </div>
      {pts.length === 0 ? (
        <div className="h-[140px] flex items-center justify-center text-subtle text-[13px]">No power data for this ride</div>
      ) : (
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={pts} margin={{ top: 8, right: 4, bottom: 0, left: 4 }}>
            <defs>
              <linearGradient id="pwFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#fc4c02" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#fc4c02" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="x" hide />
            <YAxis hide domain={[0, "dataMax"]} />
            {detail.avg_power_w !== null && (
              <ReferenceLine y={detail.avg_power_w} stroke="#fc4c02" strokeDasharray="4 4" strokeOpacity={0.5} />
            )}
            {detail.normalized_power_w !== null && (
              <ReferenceLine y={detail.normalized_power_w} stroke={gridColor} strokeDasharray="4 4" />
            )}
            <Area type="monotone" dataKey="y" stroke="#fc4c02" strokeWidth={2.2} fill="url(#pwFill)" dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Implement** `ElevationChart.tsx`

```tsx
import { Area, AreaChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { toChartPoints } from "@/api/activity-detail";
import { useSettings } from "@/app/providers/settings-context";
import { elevationLabel } from "@/lib/units";
import type { ActivityDetailDTO, ActivityStreamsDTO } from "@/types/activity-detail";

const card = "bg-surface-card border border-line rounded-[16px] px-[22px] py-5 mb-4";

export function ElevationChart({ detail, streams }: { detail: ActivityDetailDTO; streams?: ActivityStreamsDTO }) {
  const { isDark, units } = useSettings();
  const stroke = isDark ? "#c4cad4" : "#3a414b";
  const pts = toChartPoints(streams?.distance ?? null, streams?.altitude ?? null, units === "imperial" ? "imperial" : "metric");
  return (
    <div className={card}>
      <div className="flex items-center justify-between mb-3.5">
        <span className="font-display font-medium text-[15px] text-ink">Elevation profile</span>
        <span className="font-mono text-[11px] text-faint">+{elevationLabel(detail.elev_gain_m, units)}</span>
      </div>
      {pts.length === 0 ? (
        <div className="h-[140px] flex items-center justify-center text-subtle text-[13px]">No elevation data</div>
      ) : (
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={pts} margin={{ top: 8, right: 4, bottom: 0, left: 4 }}>
            <defs>
              <linearGradient id="elFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#8b93a1" stopOpacity={0.28} />
                <stop offset="100%" stopColor="#8b93a1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="x" hide />
            <YAxis hide domain={["dataMin", "dataMax"]} />
            <Area type="monotone" dataKey="y" stroke={stroke} strokeWidth={2} fill="url(#elFill)" dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
```

> Note: altitude values from Strava are in metres; `toChartPoints` only converts the **x** (distance) axis. For a correct imperial **y**, convert altitude in the elevation case before passing in, OR keep metres for the (hidden-axis) profile shape — the shape is identical either way since the axis is hidden. Keep metres for the y series (shape only); the `+elev gain` label is already unit-correct via `elevationLabel`.

- [ ] **Step 5: Run — expect PASS.** `cd frontend && npx vitest run src/pages/activity-detail/components/Charts.test.tsx`

- [ ] **Step 6: Wire into the page** — in `ActivityDetailPage.tsx`, call `const { data: streams } = useActivityStreams(activityId);` and render below the hero grid (inside the `else`):

```tsx
            <PowerChart detail={detail} streams={streams} />
            <ElevationChart detail={detail} streams={streams} />
```

Add the imports. (The page test already mocks `useActivityStreams`.)

- [ ] **Step 7: Run full suite + lint + build**

Run: `cd frontend && npm test && npm run lint && npm run build` → green.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/activity-detail/
git commit -m "feat(web): power + elevation charts from streams"
```

**INCREMENT 3 VERIFY:** On the detail page, the Power chart shows the watts area with dashed avg (orange) + NP (grey) lines and a legend; Elevation shows the altitude profile + total gain. A no-power ride shows "No power data". Both look correct in light + dark.

---

## INCREMENT 4 — Zones + Settings (FTP / max HR)

Goal: power + HR zone panels computed from streams + the athlete's FTP/max-HR, entered in Settings.

### Task 14: Zone math in `analysis.py`

**Files:**
- Modify: `backend/app/services/analysis.py`
- Test: `backend/tests/services/test_analysis.py` (append)

**Interfaces:**
- Produces:
  - `POWER_ZONES: list[tuple[str, str, float, float | None]]` — `(z, name, lo_frac, hi_frac)` per spec table.
  - `HR_ZONE_BOUNDS = [0.68, 0.78, 0.88, 0.95]`; names Recovery/Endurance/Tempo/Threshold/Maximum.
  - `power_zones(ftp: int) -> list[dict]` → each `{"z","name","range","lo","hi"}` (`hi=None` for top), watts ints.
  - `hr_zones(hr_max: int) -> list[dict]` → same shape, bpm ints.
  - `time_in_zones(time, series, zones) -> list[dict]` → each `{"z","name","range","seconds","pct"}` (pct 0–100, rounded 1dp; sums to ~100).

- [ ] **Step 1: Write the failing test** (append)

```python
def test_power_zones_boundaries_at_ftp_280():
    z = analysis.power_zones(280)
    assert [b["z"] for b in z] == ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6", "Z7"]
    assert z[0]["hi"] == 154   # 0.55*280
    assert z[1]["lo"] == 154 and z[1]["hi"] == 210  # 0.75*280
    assert z[6]["hi"] is None
    assert z[3]["name"] == "Threshold"


def test_hr_zones_boundaries():
    z = analysis.hr_zones(190)
    assert [b["z"] for b in z] == ["Z1", "Z2", "Z3", "Z4", "Z5"]
    assert z[0]["hi"] == round(0.68 * 190)
    assert z[4]["hi"] is None
    assert z[0]["name"] == "Recovery"


def test_time_in_zones_dt_weighted_sums_to_total():
    zones = analysis.power_zones(200)  # Z1 <110, Z2 110-150, ...
    time = [0, 1, 2, 3]               # 1s each (first gap backfilled to 1)
    watts = [50, 130, 130, 600]       # Z1, Z2, Z2, Z7
    buckets = analysis.time_in_zones(time, watts, zones)
    by_z = {b["z"]: b for b in buckets}
    assert by_z["Z1"]["seconds"] == 1
    assert by_z["Z2"]["seconds"] == 2
    assert by_z["Z7"]["seconds"] == 1
    assert round(sum(b["pct"] for b in buckets)) == 100
```

- [ ] **Step 2: Run — expect FAIL.** `cd backend && python -m pytest tests/services/test_analysis.py -v`

- [ ] **Step 3: Implement** — append to `analysis.py`

```python
POWER_ZONES = [
    ("Z1", "Active Rec.",   0.0,  0.55),
    ("Z2", "Endurance",     0.55, 0.75),
    ("Z3", "Tempo",         0.75, 0.90),
    ("Z4", "Threshold",     0.90, 1.05),
    ("Z5", "VO₂ Max",       1.05, 1.20),
    ("Z6", "Anaerobic",     1.20, 1.50),
    ("Z7", "Neuromuscular", 1.50, None),
]
HR_ZONE_BOUNDS = [0.68, 0.78, 0.88, 0.95]
HR_ZONE_NAMES = ["Recovery", "Endurance", "Tempo", "Threshold", "Maximum"]


def _fmt_range(lo: int, hi: int | None, unit: str) -> str:
    if lo == 0 and hi is not None:
        return f"< {hi} {unit}"
    if hi is None:
        return f"> {lo} {unit}"
    return f"{lo}–{hi} {unit}"


def power_zones(ftp: int) -> list[dict]:
    out = []
    for z, name, lo_f, hi_f in POWER_ZONES:
        lo = round(lo_f * ftp)
        hi = round(hi_f * ftp) if hi_f is not None else None
        out.append({"z": z, "name": name, "range": _fmt_range(lo, hi, "W"), "lo": lo, "hi": hi})
    return out


def hr_zones(hr_max: int) -> list[dict]:
    bounds = [round(b * hr_max) for b in HR_ZONE_BOUNDS]
    edges = [0, *bounds, None]
    out = []
    for i, name in enumerate(HR_ZONE_NAMES):
        lo = edges[i]
        hi = edges[i + 1]
        out.append({"z": f"Z{i+1}", "name": name, "range": _fmt_range(lo, hi, "bpm"), "lo": lo, "hi": hi})
    return out


def time_in_zones(time: list[int], series: list, zones: list[dict]) -> list[dict]:
    dt = deltas(time)
    secs = [0.0] * len(zones)
    for w, v in zip(dt, series, strict=False):
        if v is None:
            continue
        for i, z in enumerate(zones):
            hi = z["hi"]
            if v >= z["lo"] and (hi is None or v < hi):
                secs[i] += w
                break
    total = sum(secs) or 1.0
    return [
        {"z": z["z"], "name": z["name"], "range": z["range"],
         "seconds": round(secs[i]), "pct": round(secs[i] / total * 100, 1)}
        for i, z in enumerate(zones)
    ]
```

- [ ] **Step 4: Run — expect PASS.** Commit:

```bash
git add backend/app/services/analysis.py backend/tests/services/test_analysis.py
git commit -m "feat(analysis): power/HR zones + Δt-weighted time-in-zone"
```

### Task 15: Settings `ftp_w`/`hr_max` + zones in detail

**Files:**
- Modify: `backend/app/models/athlete.py` (`SettingsUpdate`)
- Modify: `backend/app/models/activities.py` (`ZoneBucket`, `ZonesBlock`, add fields to `ActivityDetailResponse`)
- Modify: `backend/app/services/activities.py` (`get_detail` builds zones)
- Test: `backend/tests/services/test_activities_detail.py` (append), `tests/routers/test_athletes.py` (append)

**Interfaces:**
- Produces:
  - `SettingsUpdate.ftp_w: int | None`, `SettingsUpdate.hr_max: int | None`; validator allows any one field.
  - `ZoneBucket(z, name, range, seconds, pct)`; `ZonesBlock(unset: bool, avg: float | None, buckets: list[ZoneBucket])`.
  - `ActivityDetailResponse.power_zones: ZonesBlock`, `.hr_zones: ZonesBlock`.

- [ ] **Step 1: Extend `SettingsUpdate`** — `app/models/athlete.py`

```python
class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    units: Literal["metric", "imperial"] | None = None
    theme: Literal["dark", "light"] | None = None
    ftp_w: int | None = None
    hr_max: int | None = None

    @model_validator(mode="after")
    def require_at_least_one(self) -> "SettingsUpdate":
        if all(v is None for v in (self.units, self.theme, self.ftp_w, self.hr_max)):
            raise ValueError("at least one of units, theme, ftp_w, hr_max is required")
        return self
```

- [ ] **Step 2: Add models** — `app/models/activities.py`

```python
class ZoneBucket(BaseModel):
    z: str
    name: str
    range: str
    seconds: int
    pct: float


class ZonesBlock(BaseModel):
    unset: bool
    avg: float | None = None
    buckets: list[ZoneBucket] = []
```

Add to `ActivityDetailResponse`:

```python
    power_zones: "ZonesBlock" = ZonesBlock(unset=True)
    hr_zones: "ZonesBlock" = ZonesBlock(unset=True)
```

> Define `ZonesBlock` **above** `ActivityDetailResponse` so the default value resolves.

- [ ] **Step 3: Write the failing service test** (append to `test_activities_detail.py`)

```python
def test_get_detail_builds_zones_from_settings(monkeypatch):
    row = dict(ROW)
    monkeypatch.setattr(svc.activities_db, "get_activity", lambda c, a, aid: row)
    monkeypatch.setattr(svc, "ensure_streams",
        lambda c, s, a, aid: {"time": [0, 1, 2, 3],
                              "watts": [50, 220, 220, 600],
                              "heartrate": [120, 150, 150, 180]})
    monkeypatch.setattr(svc.athletes_db, "get_athlete",
        lambda c, aid: {"id": 7, "name": "A", "avatar_url": None,
                        "settings": {"ftp_w": 280, "hr_max": 190}})
    d = svc.get_detail(object(), object(), 7, 5)
    assert d.power_zones.unset is False
    assert round(sum(b.pct for b in d.power_zones.buckets)) == 100
    assert d.hr_zones.unset is False and d.hr_zones.avg is not None


def test_get_detail_zones_unset_without_settings(monkeypatch):
    monkeypatch.setattr(svc.activities_db, "get_activity", lambda c, a, aid: dict(ROW))
    monkeypatch.setattr(svc, "ensure_streams", lambda c, s, a, aid: {"time": [0, 1], "watts": [200, 210]})
    monkeypatch.setattr(svc.athletes_db, "get_athlete",
        lambda c, aid: {"id": 7, "name": "A", "avatar_url": None, "settings": {}})
    d = svc.get_detail(object(), object(), 7, 5)
    assert d.power_zones.unset is True and d.hr_zones.unset is True
```

- [ ] **Step 4: Run — expect FAIL.** `cd backend && python -m pytest tests/services/test_activities_detail.py -v`

- [ ] **Step 5: Implement** — in `app/services/activities.py`, import `athletes` db + the models, and extend `get_detail`. Add a helper and call it:

```python
from app.db import athletes as athletes_db
from app.models.activities import ZoneBucket, ZonesBlock


def _zones_block(time, series, zone_defs, bound: int | None) -> ZonesBlock:
    if bound is None or not series:
        return ZonesBlock(unset=True)
    buckets = [ZoneBucket(**b) for b in analysis.time_in_zones(time, series, zone_defs)]
    return ZonesBlock(unset=False, avg=analysis.weighted_mean(time, series), buckets=buckets)
```

In `get_detail`, after computing `time`/`watts`, add:

```python
    hr = data.get("heartrate")
    settings = (athletes_db.get_athlete(supabase, athlete_id) or {}).get("settings", {})
    ftp = settings.get("ftp_w")
    hr_max = settings.get("hr_max")
    power_block = _zones_block(time, watts, analysis.power_zones(ftp), ftp) if ftp else ZonesBlock(unset=True)
    hr_block = _zones_block(time, hr, analysis.hr_zones(hr_max), hr_max) if hr_max else ZonesBlock(unset=True)
```

…and pass `power_zones=power_block, hr_zones=hr_block` into the `ActivityDetailResponse(...)`.

- [ ] **Step 6: Run service test — expect PASS.**

- [ ] **Step 7: PATCH router test** (append to `tests/routers/test_athletes.py`) — confirm `ftp_w` is accepted:

```python
def test_patch_settings_accepts_ftp_and_hr(client, monkeypatch):
    from app.services import athletes as athletes_service
    captured = {}
    def fake(supabase, athlete_id, patch):
        captured["ftp"] = patch.ftp_w
        captured["hr"] = patch.hr_max
        from app.models.athlete import AthleteResponse
        return AthleteResponse(id=athlete_id, name="A", avatar_url=None,
                               settings={"ftp_w": patch.ftp_w, "hr_max": patch.hr_max})
    monkeypatch.setattr(athletes_service, "update_settings", fake)
    _auth(client)  # reuse the helper present in this test module
    r = client.patch("/athlete/settings", json={"ftp_w": 280, "hr_max": 190})
    assert r.status_code == 200 and captured == {"ftp": 280, "hr": 190}
```

> If `tests/routers/test_athletes.py` lacks an `_auth` helper, copy the two-line helper from `test_activities.py` (sign a session cookie).

- [ ] **Step 8: Run all backend tests — expect PASS.**

Run: `cd backend && python -m pytest tests/ -v`

- [ ] **Step 9: Commit**

```bash
git add backend/app/ backend/tests/
git commit -m "feat(activities): FTP/maxHR settings + zones in detail response"
```

### Task 16: Zone tokens + frontend zone transforms

**Files:**
- Modify: `frontend/src/index.css` (zone color tokens in `:root`, `.dark`, `@theme inline`)
- Modify: `frontend/src/types/activity-detail.ts` (`ZoneBucketDTO`, `ZonesBlockDTO`, add to `ActivityDetailDTO`)
- Modify: `frontend/src/api/activity-detail.ts` (`zoneColor`, `toZoneRows`)
- Test: `frontend/src/api/activity-detail.test.ts` (append)

**Interfaces:**
- Produces:
  - Tokens `--color-zone-1 … --color-zone-7` (used for both power Z1–Z7 and HR Z1–Z5 by index).
  - `ZoneBucketDTO { z; name; range; seconds; pct }`, `ZonesBlockDTO { unset; avg; buckets }`.
  - `ZoneRowVM { z; name; range; color; barW: string; dur: string; pctLabel: string }`.
  - `toZoneRows(block: ZonesBlockDTO): ZoneRowVM[]` — color by index, `barW` = pct/maxPct·100, `dur` via `fmtDuration`, `pctLabel` = `"NN%"`.

- [ ] **Step 1: Add tokens** to `index.css`. In `:root` (light):

```css
    /* Training zones — light (zone-1 cool → zone-7 hot) */
    --zone-1: #6b7280; --zone-2: #2f8fd0; --zone-3: #1f9d63;
    --zone-4: #a16207; --zone-5: #c2410c; --zone-6: #d9534f; --zone-7: #b91c1c;
```

In `.dark`:

```css
    /* Training zones — dark */
    --zone-1: #6b7280; --zone-2: #38bdf8; --zone-3: #34d399;
    --zone-4: #eab308; --zone-5: #f59e0b; --zone-6: #fc4c02; --zone-7: #ef4444;
```

Under `@theme inline`:

```css
  --color-zone-1: var(--zone-1);
  --color-zone-2: var(--zone-2);
  --color-zone-3: var(--zone-3);
  --color-zone-4: var(--zone-4);
  --color-zone-5: var(--zone-5);
  --color-zone-6: var(--zone-6);
  --color-zone-7: var(--zone-7);
```

- [ ] **Step 2: Add types** to `activity-detail.ts`

```ts
export interface ZoneBucketDTO { z: string; name: string; range: string; seconds: number; pct: number }
export interface ZonesBlockDTO { unset: boolean; avg: number | null; buckets: ZoneBucketDTO[] }
```

Add to `ActivityDetailDTO`: `power_zones: ZonesBlockDTO; hr_zones: ZonesBlockDTO;`

- [ ] **Step 3: Write the failing test** (append to `activity-detail.test.ts`)

```ts
import { toZoneRows } from "./activity-detail";

describe("toZoneRows", () => {
  it("colors by index and scales bars to the max bucket", () => {
    const rows = toZoneRows({ unset: false, avg: 150, buckets: [
      { z: "Z1", name: "Active Rec.", range: "< 154 W", seconds: 600, pct: 20 },
      { z: "Z2", name: "Endurance", range: "154–210 W", seconds: 1200, pct: 40 },
    ]});
    expect(rows[0].color).toBe("var(--color-zone-1)");
    expect(rows[1].color).toBe("var(--color-zone-2)");
    expect(rows[0].barW).toBe("50.0%");   // 20/40*100
    expect(rows[1].barW).toBe("100.0%");
    expect(rows[0].pctLabel).toBe("20%");
    expect(rows[0].dur).toBe("10m");      // 600s
  });
});
```

- [ ] **Step 4: Run — expect FAIL.** `cd frontend && npx vitest run src/api/activity-detail.test.ts`

- [ ] **Step 5: Implement** — append to `api/activity-detail.ts` (and import `fmtDuration` already imported)

```ts
import type { ZoneBucketDTO, ZonesBlockDTO } from "@/types/activity-detail";

export interface ZoneRowVM {
  z: string; name: string; range: string; color: string;
  barW: string; dur: string; pctLabel: string;
}

export function zoneColor(index: number): string {
  return `var(--color-zone-${Math.min(index + 1, 7)})`;
}

export function toZoneRows(block: ZonesBlockDTO): ZoneRowVM[] {
  const maxPct = Math.max(1, ...block.buckets.map((b) => b.pct));
  return block.buckets.map((b, i) => ({
    z: b.z, name: b.name, range: b.range, color: zoneColor(i),
    barW: `${((b.pct / maxPct) * 100).toFixed(1)}%`,
    dur: fmtDuration(b.seconds),
    pctLabel: `${Math.round(b.pct)}%`,
  }));
}
```

- [ ] **Step 6: Run — expect PASS.** Commit:

```bash
git add frontend/src/index.css frontend/src/types/activity-detail.ts frontend/src/api/activity-detail.ts frontend/src/api/activity-detail.test.ts
git commit -m "feat(web): zone color tokens + zone-row transform"
```

### Task 17: `ZonesPanel` + Settings inputs

**Files:**
- Create: `frontend/src/pages/activity-detail/components/ZonesPanel.tsx`
- Test: `frontend/src/pages/activity-detail/components/ZonesPanel.test.tsx`
- Modify: `ActivityDetailPage.tsx` (render the two panels side by side)
- Modify: `frontend/src/api/settings.ts` (`SettingsPatch` gains `ftp_w`/`hr_max`)
- Modify: `frontend/src/pages/settings/SettingsPage.tsx` (FTP + max-HR number inputs)
- Modify: `frontend/src/pages/settings/SettingsPage.test.tsx` (assert inputs persist)

**Interfaces:**
- Consumes: `toZoneRows`, `ZonesBlockDTO`.
- Produces: `ZonesPanel({ title, meta, block }: { title: string; meta: string; block: ZonesBlockDTO })` — renders the stacked bar + rows, or an unset prompt linking to `/settings`.

- [ ] **Step 1: Write the failing test** — `ZonesPanel.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { ZonesPanel } from "./ZonesPanel";

describe("ZonesPanel", () => {
  it("renders zone rows when set", () => {
    render(<MemoryRouter><ZonesPanel title="Power zones" meta="TIME IN ZONE" block={{
      unset: false, avg: 150, buckets: [
        { z: "Z2", name: "Endurance", range: "154–210 W", seconds: 1200, pct: 40 },
      ],
    }} /></MemoryRouter>);
    expect(screen.getByText("Power zones")).toBeInTheDocument();
    expect(screen.getByText(/Z2 · Endurance/)).toBeInTheDocument();
    expect(screen.getByText("20m")).toBeInTheDocument();
  });

  it("renders an unset prompt linking to settings", () => {
    render(<MemoryRouter><ZonesPanel title="Power zones" meta="" block={{ unset: true, avg: null, buckets: [] }} /></MemoryRouter>);
    const link = screen.getByRole("link", { name: /settings/i });
    expect(link).toHaveAttribute("href", "/settings");
  });
});
```

- [ ] **Step 2: Run — expect FAIL.** `cd frontend && npx vitest run src/pages/activity-detail/components/ZonesPanel.test.tsx`

- [ ] **Step 3: Implement** `ZonesPanel.tsx`

```tsx
import { Link } from "react-router";
import { toZoneRows } from "@/api/activity-detail";
import type { ZonesBlockDTO } from "@/types/activity-detail";

export function ZonesPanel({ title, meta, block }: { title: string; meta: string; block: ZonesBlockDTO }) {
  const rows = toZoneRows(block);
  return (
    <div className="bg-surface-card border border-line rounded-[16px] px-[22px] py-5">
      <div className="flex items-center justify-between mb-4">
        <span className="font-display font-medium text-[15px] text-ink">{title}</span>
        <span className="font-mono text-[11px] text-faint">{meta}</span>
      </div>
      {block.unset ? (
        <div className="text-[13px] text-subtle py-6 text-center">
          Set your FTP and max HR in{" "}
          <Link to="/settings" className="text-strava hover:underline">Settings</Link>{" "}
          to see zones.
        </div>
      ) : (
        <>
          <div className="flex h-[9px] rounded-[5px] overflow-hidden mb-[18px]">
            {block.buckets.map((b, i) => (
              <div key={b.z} style={{ width: `${b.pct}%`, background: `var(--color-zone-${Math.min(i + 1, 7)})` }} />
            ))}
          </div>
          <div className="flex flex-col gap-[11px]">
            {rows.map((r) => (
              <div key={r.z} className="flex items-center gap-3">
                <span className="w-[9px] h-[9px] rounded-[3px] flex-none" style={{ background: r.color }} />
                <div className="w-[142px] flex-none">
                  <div className="text-[12.5px] font-medium text-ink2">{r.z} · {r.name}</div>
                  <div className="font-mono text-[9.5px] text-faint mt-px">{r.range}</div>
                </div>
                <div className="flex-1 h-[13px] bg-track rounded-[4px] overflow-hidden">
                  <div className="h-full rounded-[4px]" style={{ width: r.barW, background: r.color }} />
                </div>
                <span className="font-mono text-[11px] text-ink-hi w-[54px] text-right flex-none">{r.dur}</span>
                <span className="font-mono text-[11px] text-subtle w-[34px] text-right flex-none">{r.pctLabel}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run — expect PASS.**

- [ ] **Step 5: Wire panels into the page** — in `ActivityDetailPage.tsx`, after the charts (or per the design order: power chart → zones → elevation), add:

```tsx
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
              <ZonesPanel title="Power zones" meta="TIME IN ZONE" block={detail.power_zones} />
              <ZonesPanel title="Heart-rate zones"
                meta={detail.hr_zones.avg ? `AVG ${Math.round(detail.hr_zones.avg)} BPM` : ""}
                block={detail.hr_zones} />
            </div>
```

Import `ZonesPanel`. Update the page test's `detail` fixture to include `power_zones`/`hr_zones` (`{ unset: true, avg: null, buckets: [] }`) so it still renders.

- [ ] **Step 6: Add Settings inputs** — `frontend/src/api/settings.ts`:

```ts
export type SettingsPatch = {
  units?: Units;
  theme?: "dark" | "light";
  ftp_w?: number;
  hr_max?: number;
};
```

In `SettingsPage.tsx`, add a section with two number inputs that persist on blur via `patchSettings`. Read current values from `athlete.settings`:

```tsx
import { patchSettings } from "@/api/settings";
// inside component:
const ftp = (athlete?.settings as { ftp_w?: number })?.ftp_w ?? "";
const hrMax = (athlete?.settings as { hr_max?: number })?.hr_max ?? "";

// add this section in the JSX:
<div className={section}>
  <div className={heading}>Training zones</div>
  <div className={sub}>FTP and max heart rate power your zone breakdowns.</div>
  <div className="flex gap-4">
    <label className="flex flex-col gap-1 text-[12px] text-subtle">
      FTP (W)
      <input type="number" defaultValue={ftp} aria-label="FTP watts"
        onBlur={(e) => e.target.value && patchSettings({ ftp_w: Number(e.target.value) })}
        className="w-[120px] bg-surface-inset border border-line rounded-[8px] px-3 py-2 text-ink text-[14px]" />
    </label>
    <label className="flex flex-col gap-1 text-[12px] text-subtle">
      Max HR (bpm)
      <input type="number" defaultValue={hrMax} aria-label="Max heart rate"
        onBlur={(e) => e.target.value && patchSettings({ hr_max: Number(e.target.value) })}
        className="w-[120px] bg-surface-inset border border-line rounded-[8px] px-3 py-2 text-ink text-[14px]" />
    </label>
  </div>
</div>
```

- [ ] **Step 7: Settings test** — add to `SettingsPage.test.tsx`: render, type into "FTP watts", blur, assert `patchSettings` called with `{ ftp_w: <n> }`. Mock `@/api/settings` `patchSettings` with `vi.fn()`.

- [ ] **Step 8: Full suite + lint + build**

Run: `cd frontend && npm test && npm run lint && npm run build` → green.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/activity-detail/ frontend/src/api/settings.ts frontend/src/pages/settings/
git commit -m "feat(web): zone panels + FTP/maxHR settings inputs"
```

**INCREMENT 4 VERIFY:** With FTP/max-HR unset, both zone panels show the Settings prompt. Set them in Settings, reopen a ride → panels show the stacked bar + per-zone duration/% summing to ride time; HR header shows AVG BPM. Colors correct in light + dark.

---

## INCREMENT 5 — Climbs

Goal: a "Climbs on this ride" table from categorized segment efforts.

### Task 18: Migration `0007` + capture climb fields

**Files:**
- Create: `supabase/migrations/0007_segment_climbs.sql`
- Modify: `backend/app/db/segments.py` (`SegmentRow` gains `climb_category`, `elev_gain_m`)
- Modify: `backend/app/services/segments.py` (`extract_efforts` captures them)
- Test: `backend/tests/services/test_segments.py` (extend `test_extract_efforts...`)

- [ ] **Step 1: Write the migration** — `supabase/migrations/0007_segment_climbs.sql`

```sql
-- Categorized-climb fields off each segment, for the activity climbs table.
-- Backfilled for history by re-running the detail backfill (store_activity_efforts).
alter table segments add column if not exists climb_category smallint        not null default 0;
alter table segments add column if not exists elev_gain_m    double precision not null default 0;
```

Apply via Supabase MCP `apply_migration` (name `segment_climbs`); confirm columns via `list_tables`.

- [ ] **Step 2: Extend the failing test** — update `test_extract_efforts_maps_segment_and_effort_fields` and add a case:

```python
def test_extract_efforts_captures_climb_fields():
    detail = {"id": 1, "segment_efforts": [
        {"id": 9, "elapsed_time": 1089, "start_date": "2026-06-20T08:00:00Z",
         "average_watts": 240.0, "average_heartrate": 158.0,
         "segment": {"id": 5, "name": "Marincello", "distance": 4300.0,
                     "average_grade": 7.2, "climb_category": 2,
                     "elevation_high": 360.0, "elevation_low": 50.0}}]}
    segs, _ = svc.extract_efforts(7, detail)
    assert segs[0]["climb_category"] == 2
    assert segs[0]["elev_gain_m"] == 310.0   # 360 - 50
```

Also update the existing `segs[0] == {...}` assertion to include `"climb_category": 0, "elev_gain_m": 0.0` for the non-climb fixture (which has no climb fields → defaults).

- [ ] **Step 3: Run — expect FAIL.** `cd backend && python -m pytest tests/services/test_segments.py -v`

- [ ] **Step 4: Implement** — `db/segments.py` `SegmentRow`:

```python
class SegmentRow(TypedDict):
    id: int
    name: str
    distance_m: float
    avg_grade: float
    climb_category: int
    elev_gain_m: float
```

`services/segments.py` in `extract_efforts`, replace the `seg_by_id[seg_id] = {...}` block:

```python
        high = seg.get("elevation_high")
        low = seg.get("elevation_low")
        gain = (high - low) if (high is not None and low is not None) else seg.get("total_elevation_gain", 0.0)
        seg_by_id[seg_id] = {
            "id": seg_id,
            "name": seg.get("name") or "Segment",
            "distance_m": distance,
            "avg_grade": seg.get("average_grade", 0.0),
            "climb_category": seg.get("climb_category", 0) or 0,
            "elev_gain_m": float(gain or 0.0),
        }
```

- [ ] **Step 5: Run — expect PASS** (`tests/services/test_segments.py` + `tests/db/test_segments.py` if it asserts row shape — update those too).

- [ ] **Step 6: Commit**

```bash
git add supabase/migrations/0007_segment_climbs.sql backend/app/db/segments.py backend/app/services/segments.py backend/tests/
git commit -m "feat(segments): capture climb_category + elev gain on efforts"
```

### Task 19: `compute_climbs` + `list_activity_climbs` + detail wiring

**Files:**
- Modify: `backend/app/services/analysis.py` (`compute_climbs`)
- Modify: `backend/app/db/activities.py` (`list_activity_climbs`)
- Modify: `backend/app/models/activities.py` (`ClimbItem`; `ActivityDetailResponse.climbs`)
- Modify: `backend/app/services/activities.py` (`get_detail` adds climbs)
- Test: `tests/services/test_analysis.py`, `tests/db/test_activities.py`, `tests/services/test_activities_detail.py`

**Interfaces:**
- Produces:
  - `ClimbItem(name, climb_category, distance_m, avg_grade, elev_gain_m, time_s, vam)`.
  - `analysis.compute_climbs(rows: list[dict]) -> list[dict]` — input rows `{name, climb_category, distance_m, avg_grade, elev_gain_m, elapsed_time_s}`; output adds `vam = round(elev_gain_m / (elapsed_time_s/3600))`; sorted by `climb_category` desc then `elapsed_time_s` desc.
  - `db.activities.list_activity_climbs(client, athlete_id, activity_id) -> list[dict]` — efforts joined to segments where `climb_category > 0`.

- [ ] **Step 1: analysis test + impl**

```python
def test_compute_climbs_vam_and_sort():
    rows = [
        {"name": "Hawk Hill", "climb_category": 3, "distance_m": 1800, "avg_grade": 6.4,
         "elev_gain_m": 115, "elapsed_time_s": 421},
        {"name": "Marincello", "climb_category": 2, "distance_m": 4300, "avg_grade": 7.2,
         "elev_gain_m": 310, "elapsed_time_s": 1089},
    ]
    out = analysis.compute_climbs(rows)
    assert out[0]["name"] == "Hawk Hill"  # cat 3 before cat 2
    assert out[1]["vam"] == round(310 / (1089 / 3600))  # ≈ 1025
```

Append to `analysis.py`:

```python
def compute_climbs(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        secs = r["elapsed_time_s"]
        vam = round(r["elev_gain_m"] / (secs / 3600)) if secs else 0
        out.append({**r, "vam": vam})
    out.sort(key=lambda c: (c["climb_category"], c["elapsed_time_s"]), reverse=True)
    return out
```

Run: `cd backend && python -m pytest tests/services/test_analysis.py -v` → PASS.

- [ ] **Step 2: db test + impl** — `list_activity_climbs` joins via PostgREST embed. Add to `tests/db/test_activities.py`:

```python
@respx.mock
def test_list_activity_climbs_filters_categorized():
    route = respx.route(method="GET", path="/rest/v1/segment_efforts").mock(
        return_value=Response(200, json=[
            {"elapsed_time_s": 1089, "segments": {"name": "Marincello", "climb_category": 2,
             "distance_m": 4300.0, "avg_grade": 7.2, "elev_gain_m": 310.0}}]))
    rows = activities.list_activity_climbs(CLIENT, 7, 5)
    params = route.calls.last.request.url.params
    assert params["athlete_id"] == "eq.7" and params["activity_id"] == "eq.5"
    assert rows[0]["segments"]["climb_category"] == 2
```

Add to `db/activities.py`:

```python
def list_activity_climbs(client: Client, athlete_id: int, activity_id: int) -> list[dict]:
    resp = (
        client.table("segment_efforts")
        .select("elapsed_time_s, segments(name, climb_category, distance_m, avg_grade, elev_gain_m)")
        .eq("athlete_id", athlete_id).eq("activity_id", activity_id)
        .execute()
    )
    return cast(list[dict], resp.data)
```

Run db tests → PASS.

- [ ] **Step 3: Model** — `app/models/activities.py`:

```python
class ClimbItem(BaseModel):
    name: str
    climb_category: int
    distance_m: float
    avg_grade: float
    elev_gain_m: float
    time_s: int
    vam: int
```

Add to `ActivityDetailResponse`: `climbs: list[ClimbItem] = []`.

- [ ] **Step 4: Service test + impl** — append to `test_activities_detail.py`:

```python
def test_get_detail_includes_climbs(monkeypatch):
    monkeypatch.setattr(svc.activities_db, "get_activity", lambda c, a, aid: dict(ROW))
    monkeypatch.setattr(svc, "ensure_streams", lambda c, s, a, aid: {"time": [0, 1], "watts": [200, 200]})
    monkeypatch.setattr(svc.athletes_db, "get_athlete", lambda c, aid: {"settings": {}})
    monkeypatch.setattr(svc.activities_db, "list_activity_climbs", lambda c, a, aid: [
        {"elapsed_time_s": 1089, "segments": {"name": "Marincello", "climb_category": 2,
         "distance_m": 4300.0, "avg_grade": 7.2, "elev_gain_m": 310.0}}])
    d = svc.get_detail(object(), object(), 7, 5)
    assert d.climbs[0].name == "Marincello" and d.climbs[0].vam > 0
```

In `get_detail`, build climbs before constructing the response:

```python
    climb_rows = [
        {"name": r["segments"]["name"], "climb_category": r["segments"]["climb_category"],
         "distance_m": r["segments"]["distance_m"], "avg_grade": r["segments"]["avg_grade"],
         "elev_gain_m": r["segments"]["elev_gain_m"], "elapsed_time_s": r["elapsed_time_s"]}
        for r in activities_db.list_activity_climbs(supabase, athlete_id, activity_id)
        if r.get("segments")
    ]
    climbs = [
        ClimbItem(name=c["name"], climb_category=c["climb_category"], distance_m=c["distance_m"],
                  avg_grade=c["avg_grade"], elev_gain_m=c["elev_gain_m"],
                  time_s=c["elapsed_time_s"], vam=c["vam"])
        for c in analysis.compute_climbs(climb_rows)
    ]
```

Import `ClimbItem`; pass `climbs=climbs` into the response.

- [ ] **Step 5: Run all backend tests — expect PASS.** `cd backend && python -m pytest tests/ -v`

- [ ] **Step 6: Commit**

```bash
git add backend/app/ backend/tests/
git commit -m "feat(activities): climbs (VAM + sort) in detail response"
```

### Task 20: `ClimbsPanel` + cat tokens + page wiring

**Files:**
- Modify: `frontend/src/index.css` (climb-category color tokens)
- Modify: `frontend/src/types/activity-detail.ts` (`ClimbDTO`, add `climbs`)
- Modify: `frontend/src/api/activity-detail.ts` (`toClimbRows` + grade-color tokens; does **not** reuse the segments `gradeBadge`)
- Create: `frontend/src/pages/activity-detail/components/ClimbsPanel.tsx`
- Test: `frontend/src/api/activity-detail.test.ts`, `frontend/src/pages/activity-detail/components/ClimbsPanel.test.tsx`
- Modify: `ActivityDetailPage.tsx` (render panel)

**Interfaces:**
- Produces:
  - Tokens `--color-cat-4 … --color-cat-hc` (or reuse zone tokens by mapping).
  - `ClimbDTO { name; climb_category; distance_m; avg_grade; elev_gain_m; time_s; vam }`.
  - `ClimbRowVM { name; catLabel; catColor; length; grade; gradeColor; gain; vam; time }`.
  - `toClimbRows(climbs: ClimbDTO[], units: Units): ClimbRowVM[]`.

- [ ] **Step 1: Add category + grade tokens** to `index.css` (light `:root`, dark `.dark`, then `@theme inline`). Both come straight from the design's `catColor()` / `gradeColor()` light+dark palettes — each token resolves to the right value per theme, so one `var()` is correct in light and dark.

Category-badge tokens:

```css
/* light */    --cat-4:#2563c2; --cat-3:#0f9d58; --cat-2:#a16207; --cat-1:#c2410c; --cat-hc:#dc2626;
/* dark */     --cat-4:#60a5fa; --cat-3:#34d399; --cat-2:#eab308; --cat-1:#f59e0b; --cat-hc:#ef4444;
/* @theme */   --color-cat-4: var(--cat-4); --color-cat-3: var(--cat-3); --color-cat-2: var(--cat-2);
               --color-cat-1: var(--cat-1); --color-cat-hc: var(--cat-hc);
```

Grade-text tokens (the avg-grade column is **colored text only — no badge/background**, matching the design):

```css
/* light */    --grade-descent:#5b6675; --grade-green:#0f9d58; --grade-yellow:#a16207; --grade-orange:#c2410c; --grade-red:#dc2626;
/* dark */     --grade-descent:#8a909a; --grade-green:#34d399; --grade-yellow:#eab308; --grade-orange:#f59e0b; --grade-red:#ef4444;
/* @theme */   --color-grade-descent: var(--grade-descent); --color-grade-green: var(--grade-green);
               --color-grade-yellow: var(--grade-yellow); --color-grade-orange: var(--grade-orange);
               --color-grade-red: var(--grade-red);
```

- [ ] **Step 2: Types** — `activity-detail.ts`:

```ts
export interface ClimbDTO {
  name: string; climb_category: number; distance_m: number; avg_grade: number;
  elev_gain_m: number; time_s: number; vam: number;
}
```

Add `climbs: ClimbDTO[]` to `ActivityDetailDTO`.

- [ ] **Step 3: Failing api test** (append to `activity-detail.test.ts`)

```ts
import { toClimbRows } from "./activity-detail";

describe("toClimbRows", () => {
  it("labels category (Strava: climb_category 2 → Cat 3), length, grade and gain", () => {
    const rows = toClimbRows([{ name: "Marincello", climb_category: 2, distance_m: 4300,
      avg_grade: 7.2, elev_gain_m: 310, time_s: 1089, vam: 1025 }], "metric");
    expect(rows[0]).toMatchObject({
      name: "Marincello", catLabel: "CAT 3", length: "4.3 km",
      grade: "7.2%", gain: "+310 m", vam: "1,025 m/h", time: "18:09",
    });
    expect(rows[0].catColor).toBe("var(--color-cat-3)");
  });
  it("colors the grade text by band, theme-aware via tokens (no background)", () => {
    const grade = (g: number) => toClimbRows([{ name: "X", climb_category: 1, distance_m: 1000,
      avg_grade: g, elev_gain_m: 100, time_s: 600, vam: 600 }], "metric")[0].gradeColor;
    expect(grade(-2)).toBe("var(--color-grade-descent)");
    expect(grade(2)).toBe("var(--color-grade-green)");
    expect(grade(6)).toBe("var(--color-grade-yellow)");
    expect(grade(10)).toBe("var(--color-grade-orange)");
    expect(grade(14)).toBe("var(--color-grade-red)");
  });
  it("labels HC for climb_category 5", () => {
    expect(toClimbRows([{ name: "X", climb_category: 5, distance_m: 1000, avg_grade: 10,
      elev_gain_m: 100, time_s: 600, vam: 600 }], "metric")[0].catLabel).toBe("HC");
  });
});
```

- [ ] **Step 4: Run — expect FAIL.** `cd frontend && npx vitest run src/api/activity-detail.test.ts`

- [ ] **Step 5: Implement** — append to `api/activity-detail.ts`. The grade is **text only**, colored by band via theme-aware `--color-grade-*` tokens (NOT the segments `gradeBadge`, which is a dark-only pill with a background):

```ts
import { fmtClock } from "@/lib/format";
import { fmtDistance, fmtElevation } from "@/lib/units"; // already imported
import type { ClimbDTO } from "@/types/activity-detail";

export interface ClimbRowVM {
  name: string; catLabel: string; catColor: string; length: string;
  grade: string; gradeColor: string; gain: string; vam: string; time: string;
}

// Strava climb_category: 1→Cat 4 (easiest) … 4→Cat 1, 5→HC (hardest).
const CAT_LABEL: Record<number, string> = { 1: "CAT 4", 2: "CAT 3", 3: "CAT 2", 4: "CAT 1", 5: "HC" };
const CAT_TOKEN: Record<number, string> = {
  1: "var(--color-cat-4)", 2: "var(--color-cat-3)", 3: "var(--color-cat-2)",
  4: "var(--color-cat-1)", 5: "var(--color-cat-hc)",
};

/** Grade-text color token by steepness band (matches the design's gradeColor). */
export function gradeColorToken(grade: number): string {
  if (grade < 0) return "var(--color-grade-descent)";
  if (grade < 4) return "var(--color-grade-green)";
  if (grade < 8) return "var(--color-grade-yellow)";
  if (grade < 12) return "var(--color-grade-orange)";
  return "var(--color-grade-red)";
}

export function toClimbRows(climbs: ClimbDTO[], units: Units): ClimbRowVM[] {
  const vamUnit = units === "imperial" ? "ft/h" : "m/h";
  return climbs.map((c) => {
    const len = fmtDistance(c.distance_m, units);
    const gain = fmtElevation(c.elev_gain_m, units);
    const vam = fmtElevation(c.vam, units);
    return {
      name: c.name,
      catLabel: CAT_LABEL[c.climb_category] ?? `CAT ${c.climb_category}`,
      catColor: CAT_TOKEN[c.climb_category] ?? "var(--color-cat-4)",
      length: `${len.value} ${len.unit}`,
      grade: `${c.avg_grade.toFixed(1)}%`,
      gradeColor: gradeColorToken(c.avg_grade),
      gain: `+${gain.value} ${gain.unit}`,
      vam: `${vam.value} ${vamUnit}`,
      time: fmtClock(c.time_s),
    };
  });
}
```

> Notes: (1) the grade is rendered as colored text (the `ClimbsPanel` already does `style={{ color: r.gradeColor }}` with no background — keep it that way). (2) VAM is m/h; `fmtElevation` converts m→ft for imperial (correct for ft/h); the returned `vam.unit` is discarded in favor of the per-hour `vamUnit`.

- [ ] **Step 6: Run — expect PASS.**

- [ ] **Step 7: Component test + impl** — `ClimbsPanel.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ClimbsPanel } from "./ClimbsPanel";

describe("ClimbsPanel", () => {
  it("renders climb rows", () => {
    render(<ClimbsPanel climbs={[{ name: "Marincello", climb_category: 2, distance_m: 4300,
      avg_grade: 7.2, elev_gain_m: 310, time_s: 1089, vam: 1025 }]} units="metric" />);
    expect(screen.getByText("Marincello")).toBeInTheDocument();
    expect(screen.getByText("CAT 3")).toBeInTheDocument();
    expect(screen.getByText("18:09")).toBeInTheDocument();
  });
  it("renders empty state when no climbs", () => {
    render(<ClimbsPanel climbs={[]} units="metric" />);
    expect(screen.getByText(/No categorized climbs/i)).toBeInTheDocument();
  });
});
```

`ClimbsPanel.tsx`:

```tsx
import { toClimbRows } from "@/api/activity-detail";
import type { ClimbDTO } from "@/types/activity-detail";
import type { Units } from "@/lib/units";

const head = "grid grid-cols-[2.2fr_1fr_1fr_1fr_1fr_0.9fr] gap-3";

export function ClimbsPanel({ climbs, units }: { climbs: ClimbDTO[]; units: Units }) {
  const rows = toClimbRows(climbs, units);
  return (
    <div className="bg-surface-card border border-line rounded-[16px] px-[22px] py-5 mb-4 overflow-x-auto">
      <div className="flex items-center justify-between mb-2">
        <span className="font-display font-medium text-[15px] text-ink">Climbs on this ride</span>
        <span className="font-mono text-[11px] text-faint">{rows.length} CATEGORIZED</span>
      </div>
      {rows.length === 0 ? (
        <div className="text-[13px] text-subtle py-6 text-center">No categorized climbs on this ride</div>
      ) : (
        <div className="min-w-[640px]">
          <div className={`${head} px-3 py-[11px] font-mono text-[9.5px] tracking-[0.1em] text-faint border-b border-line-subtle`}>
            <span>CLIMB</span><span>LENGTH</span><span>AVG GRADE</span><span>ELEV GAIN</span><span>VAM</span><span>TIME</span>
          </div>
          {rows.map((r) => (
            <div key={r.name} className={`${head} items-center px-3 py-3.5 rounded-[10px] hover:bg-surface-panel2`}>
              <div className="flex items-center gap-[11px] min-w-0">
                <span className="font-mono text-[9px] font-semibold tracking-[0.04em] px-[7px] py-0.5 rounded-[5px] flex-none border"
                  style={{ color: r.catColor, borderColor: r.catColor, background: `${r.catColor}1c` }}>{r.catLabel}</span>
                <span className="text-[13.5px] font-medium text-ink2 truncate">{r.name}</span>
              </div>
              <span className="font-mono text-[13px] text-ink">{r.length}</span>
              <span className="font-mono text-[13px] font-medium" style={{ color: r.gradeColor }}>{r.grade}</span>
              <span className="font-mono text-[13px] text-ink">{r.gain}</span>
              <span className="font-mono text-[13px] text-body">{r.vam}</span>
              <span className="font-mono text-[13px] text-ink">{r.time}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

> The `${r.catColor}1c` alpha trick only works on hex; since `catColor` is a CSS var here, instead use a wrapper with `background` set via the token at low opacity is not possible inline. Simplify: drop the tinted background (`background: "transparent"`) or apply `style={{ color: r.catColor, borderColor: r.catColor }}` only. Use border + text color for the badge; no fill. Update the test if needed (it doesn't assert background).

- [ ] **Step 8: Wire into page** — render `<ClimbsPanel climbs={detail.climbs} units={units} />` last; add `climbs: []` to the page-test fixture. Import the component.

- [ ] **Step 9: Full suite + lint + build**

Run: `cd frontend && npm test && npm run lint && npm run build` → green.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/index.css frontend/src/types/activity-detail.ts frontend/src/api/activity-detail.ts frontend/src/pages/activity-detail/
git commit -m "feat(web): climbs panel + category tokens"
```

### Task 21: Climb re-backfill (one-time op)

**Files:** none (operational).

- [ ] **Step 1:** Trigger the existing detail backfill so historical segments re-store with `climb_category`/`elev_gain_m`. This reuses `run_detail_backfill` (it calls `store_activity_efforts`). Confirm the entry point (e.g. the `/sync` detail-backfill action used previously) and run it for the athlete. It is paced/resumable by design (see `sync.py` docstring).
- [ ] **Step 2:** Spot-check: open a ride with known categorized climbs → rows appear with correct category, gain, and VAM matching Strava.

**INCREMENT 5 VERIFY:** A ride with categorized climbs shows the table (badge, length, grade colored by steepness, gain, VAM, time), hardest category first; a flat ride shows "No categorized climbs". Correct in light + dark and metric/imperial.

---

## Final verification

- [ ] `cd backend && python -m pytest tests/ -v` — all green, `test_architecture.py` passes.
- [ ] `cd frontend && npm test && npm run lint && npm run build` — all green.
- [ ] Manual: open several rides (power + non-power, with/without GPS, with/without climbs); toggle theme + units; confirm every panel matches the design in both themes.
- [ ] `superpowers:finishing-a-development-branch` to merge `feat/activity-detail-page`.

## Self-review notes (coverage map)

- Streams endpoint + cache → Tasks 1–4. Hero map + polyline seam → Tasks 8, 9 (+ `lib/map-tiles.ts`, `lib/polyline.ts`). Primary stats → Tasks 5, 6, 7, 10. Page + clickable rows → Task 11. Power/elevation charts → Tasks 12, 13. Zones + manual FTP/HR settings → Tasks 14–17. Climbs (migration, capture, compute, panel, backfill) → Tasks 18–21. Theming tokens → Tasks 16 (zones), 20 (category badges + theme-aware grade-text colors); grade is text-only (no badge), distinct from the segments `gradeBadge`; existing tokens cover the rest. Dropped sections (training load/gear/cadence/laps, Export/Edit) → never added. Error/edge states (no watts, no GPS, unset FTP, no climbs, 404) → covered in Tasks 6, 9, 13, 15, 17, 20.
