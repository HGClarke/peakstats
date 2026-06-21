# Local-time ride day Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bucket rides into weekdays by each ride's Strava local time (`start_date_local`) instead of UTC, decide the this-week/last-week boundary from the viewer's browser timezone, and label recent rides by their local day.

**Architecture:** Store Strava's per-ride `start_date_local` (a wall-clock label, stored verbatim) on each activity. The Overview service reads a `tz` query param to compute the week window in the viewer's zone, and buckets every ride by its own local wall-clock day, falling back to UTC `start_date` for legacy rows that predate the column. The frontend sends its browser zone and renders the recent-ride label from `start_date_local`.

**Tech Stack:** FastAPI + httpx/PostgREST (backend), Supabase Postgres, React 19 + Vite + TypeScript + Vitest (frontend), Python `zoneinfo` for tz math.

## Global Constraints

- **Backend layering:** routers → services → db. No layer skips another. No `fastapi` imports in `services/`. (`backend/CLAUDE.md`)
- **Type annotations on every public function** — params and return. (`backend/CLAUDE.md`)
- **Async only when you `await`** — these functions are sync `def`. (`backend/CLAUDE.md`)
- **Backend done = clean:** `pytest`, `ruff check .`, `mypy` all pass from `backend/`.
- **Frontend done = clean:** `npm test && npm run lint && npm run build` all pass from `frontend/`.
- **Frontend imports** use the `@/` alias; **data stays out of JSX** (api layer only). (`frontend/CLAUDE.md`)
- **Wall-clock invariant:** `start_date_local` is a wall-clock label — NEVER timezone-convert it (no `.astimezone()` / local conversion). Stored in a `timestamptz` column with its trailing `Z`; the numerals round-trip intact.
- **Commits:** end each message body with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

## File Structure

- `supabase/migrations/0003_activities_start_date_local.sql` — **create** — adds the nullable column.
- `backend/app/services/sync.py` — **modify** — `_to_activity_row` stores `start_date_local` (shared by backfill + webhook).
- `backend/app/db/activities.py` — **modify** — `ActivityRow` TypedDict gains `start_date_local`.
- `backend/app/services/activities.py` — **modify** — local-time bucketing + tz window in `get_overview`.
- `backend/app/models/activities.py` — **modify** — `RecentRideItem` gains `start_date_local`.
- `backend/app/routers/activities.py` — **modify** — `overview` reads the `tz` query param.
- `backend/tests/services/test_sync.py`, `test_activities.py`, `backend/tests/routers/test_activities.py` — **modify** — new tests.
- `frontend/src/types/overview.ts` — **modify** — `RecentRideDTO` gains `start_date_local`.
- `frontend/src/api/overview.ts` — **modify** — send `tz`, render label from `start_date_local`.
- `frontend/src/api/overview.test.ts` — **modify** — new tests.

---

### Task 1: Add `start_date_local` column

**Files:**
- Create: `supabase/migrations/0003_activities_start_date_local.sql`

**Interfaces:**
- Produces: an `activities.start_date_local timestamptz` column (nullable).

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/0003_activities_start_date_local.sql`:

```sql
-- Strava's per-ride local wall-clock start time. Stored verbatim (carries a
-- trailing Z from Strava); treat as a wall-clock label, never tz-convert it.
-- Nullable: rows synced before this column fall back to UTC start_date until a
-- re-backfill repopulates them.
alter table activities add column start_date_local timestamptz;
```

- [ ] **Step 2: Apply the migration**

Apply via the Supabase MCP `apply_migration` tool (name: `activities_start_date_local`, the SQL above), or `psql "$DATABASE_URL" -f supabase/migrations/0003_activities_start_date_local.sql`.

- [ ] **Step 3: Verify the column exists**

Run (Supabase MCP `execute_sql` or psql):

```sql
select column_name, data_type, is_nullable
from information_schema.columns
where table_name = 'activities' and column_name = 'start_date_local';
```

Expected: one row — `start_date_local | timestamp with time zone | YES`.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/0003_activities_start_date_local.sql
git commit -m "feat(db): add activities.start_date_local column

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Ingest `start_date_local` on sync + webhook

**Files:**
- Modify: `backend/app/services/sync.py` (`_to_activity_row`, ~line 22-38)
- Modify: `backend/app/db/activities.py` (`ActivityRow`, ~line 8-22)
- Test: `backend/tests/services/test_sync.py`

**Interfaces:**
- Produces: each ingested activity row carries `start_date_local: str | None` from `summary["start_date_local"]`. Used by Task 3's bucketing and shared by the webhook path (`webhooks.process_event` calls `_to_activity_row`).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/services/test_sync.py`:

```python
def test_to_activity_row_stores_start_date_local():
    row = sync_service._to_activity_row(7, {
        "id": 9, "name": "Evening spin", "type": "Ride",
        "start_date": "2026-06-21T05:00:00Z",
        "start_date_local": "2026-06-20T22:00:00Z",
        "distance": 1000.0, "moving_time": 100, "elapsed_time": 100,
        "total_elevation_gain": 0.0,
    })
    assert row["start_date_local"] == "2026-06-20T22:00:00Z"


def test_to_activity_row_start_date_local_missing_is_none():
    row = sync_service._to_activity_row(7, {
        "id": 1, "name": "Spin", "type": "Workout",
        "start_date": "2026-06-15T08:00:00Z", "distance": 0.0,
        "moving_time": 10, "elapsed_time": 10, "total_elevation_gain": 0.0,
    })
    assert row["start_date_local"] is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/services/test_sync.py::test_to_activity_row_stores_start_date_local tests/services/test_sync.py::test_to_activity_row_start_date_local_missing_is_none -v`
Expected: FAIL with `KeyError: 'start_date_local'`.

- [ ] **Step 3: Store the field in `_to_activity_row`**

In `backend/app/services/sync.py`, inside the dict returned by `_to_activity_row`, add the key right after `"start_date"`:

```python
        "start_date": summary["start_date"],
        "start_date_local": summary.get("start_date_local"),
```

- [ ] **Step 4: Add the field to the row type**

In `backend/app/db/activities.py`, add to the `ActivityRow` TypedDict (after `start_date: str`):

```python
    start_date: str
    start_date_local: str | None
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && pytest tests/services/test_sync.py -v`
Expected: PASS (new tests + existing sync tests still green).

- [ ] **Step 6: Lint, type-check, commit**

Run: `cd backend && ruff check . && mypy`
Expected: clean.

```bash
git add backend/app/services/sync.py backend/app/db/activities.py backend/tests/services/test_sync.py
git commit -m "feat(sync): store Strava start_date_local on ingest

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Bucket the Overview by local time + tz window

**Files:**
- Modify: `backend/app/services/activities.py` (`_parse` → `_local_naive`, `_resolve_tz`, `get_overview`, ~line 32-93)
- Modify: `backend/app/models/activities.py` (`RecentRideItem`, ~line 22-28)
- Test: `backend/tests/services/test_activities.py`

**Interfaces:**
- Consumes: `start_date_local` from activity rows (Task 2); the widened query still calls `activities_db.list_activities_since(supabase, athlete_id, since_iso)` (unchanged signature).
- Produces: `get_overview(supabase, athlete_id, tz: str = "UTC", now: datetime | None = None) -> OverviewResponse`. `RecentRideItem` now has `start_date_local: str | None`.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/services/test_activities.py` (the existing `THIS_WEEK`/`LAST_WEEK` rows have no `start_date_local`, so they exercise the UTC fallback and keep the existing tests green):

```python
from zoneinfo import ZoneInfo  # add to imports at top of file


def test_overview_buckets_by_local_day_not_utc(monkeypatch):
    # 11pm Sat 2026-06-20 in LA == 2026-06-21T06:00:00Z (Sun UTC).
    # Local time must place it on Saturday, not Sunday.
    ride = {
        "id": 50, "athlete_id": 7, "name": "Late ride", "type": "Ride",
        "start_date": "2026-06-21T06:00:00Z",
        "start_date_local": "2026-06-20T23:00:00Z",
        "distance_m": 12000.0, "moving_time_s": 1200, "elapsed_time_s": 1200,
        "elev_gain_m": 0.0, "avg_speed_ms": 10.0, "avg_hr": None,
        "summary_polyline": None,
    }
    _patch(monkeypatch, [ride], [])
    ov = activities_service.get_overview(
        object(), 7, tz="America/Los_Angeles", now=NOW
    )
    km = {w.day: w.km for w in ov.week}
    assert km["SAT"] == 12.0
    assert km["SUN"] == 0.0


def test_overview_window_uses_tz(monkeypatch):
    # A ride at 2026-06-15T02:00:00Z is Mon 02:00 UTC, but Sun 19:00 in LA —
    # i.e. last week in LA, this week in UTC.
    ride = {
        "id": 60, "athlete_id": 7, "name": "Boundary", "type": "Ride",
        "start_date": "2026-06-15T02:00:00Z",
        "start_date_local": "2026-06-14T19:00:00Z",
        "distance_m": 5000.0, "moving_time_s": 500, "elapsed_time_s": 500,
        "elev_gain_m": 0.0, "avg_speed_ms": 10.0, "avg_hr": None,
        "summary_polyline": None,
    }
    _patch(monkeypatch, [ride], [])
    ov = activities_service.get_overview(
        object(), 7, tz="America/Los_Angeles", now=NOW
    )
    assert ov.this_week.distance_m == 0.0
    assert ov.last_week.distance_m == 5000.0


def test_overview_invalid_tz_falls_back_to_utc(monkeypatch):
    _patch(monkeypatch, THIS_WEEK + LAST_WEEK, [])
    ov = activities_service.get_overview(object(), 7, tz="Not/AZone", now=NOW)
    # Same result as the existing UTC-default aggregation test.
    assert ov.this_week.distance_m == 30000.0
    assert ov.last_week.distance_m == 5000.0


def test_overview_recent_ride_exposes_start_date_local(monkeypatch):
    ride = {
        "id": 70, "athlete_id": 7, "name": "Has local", "type": "Ride",
        "start_date": "2026-06-21T06:00:00Z",
        "start_date_local": "2026-06-20T23:00:00Z",
        "distance_m": 1000.0, "moving_time_s": 100, "elapsed_time_s": 100,
        "elev_gain_m": 0.0, "avg_speed_ms": 10.0, "avg_hr": None,
        "summary_polyline": None,
    }
    _patch(monkeypatch, [], [ride])
    ov = activities_service.get_overview(object(), 7, now=NOW)
    assert ov.recent_rides[0].start_date_local == "2026-06-20T23:00:00Z"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/services/test_activities.py -v`
Expected: the four new tests FAIL (`get_overview` has no `tz` param / `RecentRideItem` has no `start_date_local`).

- [ ] **Step 3: Add `start_date_local` to the model**

In `backend/app/models/activities.py`, `RecentRideItem`:

```python
class RecentRideItem(BaseModel):
    id: int
    name: str
    type: str
    start_date: str
    start_date_local: str | None = None
    distance_m: float
    moving_time_s: int
```

- [ ] **Step 4: Rewrite the time helpers and `get_overview`**

In `backend/app/services/activities.py`, update the imports at the top:

```python
from datetime import UTC, datetime, timedelta
from math import ceil
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
```

Replace the `_parse` helper (lines ~32-33) with these two helpers:

```python
def _resolve_tz(tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _local_naive(row: ActivityRow) -> datetime:
    """Wall-clock datetime used for day bucketing and week membership.

    Uses Strava's per-ride start_date_local; falls back to UTC start_date for
    legacy rows. The value is a wall-clock label — it is intentionally NOT
    timezone-converted (we drop the tzinfo and compare numerals directly).
    """
    raw = row.get("start_date_local") or row["start_date"]
    return datetime.fromisoformat(raw).replace(tzinfo=None)
```

Replace the body of `get_overview` (the window + partition + bucket block, lines ~47-73) with:

```python
def get_overview(
    supabase: httpx.Client,
    athlete_id: int,
    tz: str = "UTC",
    now: datetime | None = None,
) -> OverviewResponse:
    zone = _resolve_tz(tz)
    now_local = (now or datetime.now(UTC)).astimezone(zone)
    this_monday = (
        now_local - timedelta(days=now_local.weekday())
    ).replace(hour=0, minute=0, second=0, microsecond=0)
    last_monday = this_monday - timedelta(days=7)

    # Rows are fetched by UTC start_date, which can sit up to ~14h off the local
    # date, so widen the query a day and filter precisely by local time below.
    rows = activities_db.list_activities_since(
        supabase, athlete_id, (last_monday - timedelta(days=1)).isoformat()
    )

    this_monday_naive = this_monday.replace(tzinfo=None)
    last_monday_naive = last_monday.replace(tzinfo=None)

    this_week = [r for r in rows if _local_naive(r) >= this_monday_naive]
    last_week = [
        r for r in rows
        if last_monday_naive <= _local_naive(r) < this_monday_naive
    ]

    km_by_day = [0.0] * 7
    for r in this_week:
        km_by_day[_local_naive(r).weekday()] += r["distance_m"] / 1000
    week = [
        WeekDay(day=label, km=round(km_by_day[i], 1))
        for i, label in enumerate(_WEEKDAY_LABELS)
    ]
```

Update the `RecentRideItem(...)` construction in the same function to pass the new field:

```python
        RecentRideItem(
            id=r["id"],
            name=r["name"],
            type=r["type"],
            start_date=r["start_date"],
            start_date_local=r.get("start_date_local"),
            distance_m=r["distance_m"],
            moving_time_s=r["moving_time_s"],
        )
```

- [ ] **Step 5: Run the full backend test file to verify pass**

Run: `cd backend && pytest tests/services/test_activities.py -v`
Expected: PASS — the four new tests plus all pre-existing overview tests (they default `tz="UTC"` and hit the `start_date` fallback, so their buckets are unchanged).

- [ ] **Step 6: Lint, type-check, commit**

Run: `cd backend && ruff check . && mypy`
Expected: clean. (`_local_naive` takes `ActivityRow`; `r.get(...)` is valid on a TypedDict.)

```bash
git add backend/app/services/activities.py backend/app/models/activities.py backend/tests/services/test_activities.py
git commit -m "feat(overview): bucket rides by local day, window by viewer tz

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Router forwards the `tz` query param

**Files:**
- Modify: `backend/app/routers/activities.py` (`overview`, ~line 38-43)
- Test: `backend/tests/routers/test_activities.py`

**Interfaces:**
- Consumes: `get_overview(supabase, athlete_id, tz=...)` (Task 3).
- Produces: `GET /activities/overview?tz=<IANA>` (defaults to `UTC`).

- [ ] **Step 1: Update the existing patched lambda and add tests**

In `backend/tests/routers/test_activities.py`, the existing `test_overview_returns_body` patches `get_overview` with a 2-arg lambda; the router now passes `tz`, so widen the lambda signature. Change:

```python
    monkeypatch.setattr(activities_service, "get_overview",
                        lambda supabase, athlete_id: _overview())
```

to:

```python
    monkeypatch.setattr(activities_service, "get_overview",
                        lambda supabase, athlete_id, tz="UTC": _overview())
```

Then add a test that the param is forwarded:

```python
def test_overview_forwards_tz(client, monkeypatch):
    seen = {}

    def fake(supabase, athlete_id, tz="UTC"):
        seen["tz"] = tz
        return _overview()

    monkeypatch.setattr(activities_service, "get_overview", fake)
    _auth(client)
    response = client.get("/activities/overview?tz=America/Los_Angeles")
    assert response.status_code == 200
    assert seen["tz"] == "America/Los_Angeles"
```

- [ ] **Step 2: Run the tests to verify the new one fails**

Run: `cd backend && pytest tests/routers/test_activities.py::test_overview_forwards_tz -v`
Expected: FAIL — `tz` stays `"UTC"` because the router doesn't read or pass it yet.

- [ ] **Step 3: Read and forward `tz` in the router**

In `backend/app/routers/activities.py`, update the `overview` handler:

```python
@router.get("/overview", response_model=OverviewResponse)
def overview(
    tz: str = Query("UTC"),
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: httpx.Client = Depends(get_supabase),
) -> OverviewResponse:
    return activities_service.get_overview(supabase, athlete_id, tz=tz)
```

(`Query` is already imported in this file.)

- [ ] **Step 4: Run the router tests to verify pass**

Run: `cd backend && pytest tests/routers/test_activities.py -v`
Expected: PASS (new test + updated `test_overview_returns_body`).

- [ ] **Step 5: Full backend suite + lint + types, then commit**

Run: `cd backend && pytest && ruff check . && mypy`
Expected: all clean.

```bash
git add backend/app/routers/activities.py backend/tests/routers/test_activities.py
git commit -m "feat(overview): accept tz query param on the overview route

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Frontend — send browser tz + render local recent-ride day

**Files:**
- Modify: `frontend/src/types/overview.ts` (`RecentRideDTO`, ~line 11-18)
- Modify: `frontend/src/api/overview.ts` (`toRide` ~line 18-26, `fetchOverview` ~line 69-71)
- Test: `frontend/src/api/overview.test.ts`

**Interfaces:**
- Consumes: backend `recent_rides[].start_date_local` (Task 3) and `?tz=` route (Task 4).
- Produces: requests `/activities/overview?tz=<browser IANA>`; recent-ride `meta` formatted from `start_date_local` (falls back to `start_date`).

- [ ] **Step 1: Add the field to the DTO and fix the existing fixture**

In `frontend/src/types/overview.ts`, `RecentRideDTO`:

```typescript
export interface RecentRideDTO {
  id: number;
  name: string;
  type: string;
  start_date: string;
  start_date_local: string | null;
  distance_m: number;
  moving_time_s: number;
}
```

In `frontend/src/api/overview.test.ts`, add `start_date_local` to the existing `recent_rides` fixture entry so it type-checks (give it the same instant as `start_date` so the existing label assertion stays `"Tue · Jun 16 · Ride"`):

```typescript
  recent_rides: [
    {
      id: 1,
      name: "River loop",
      type: "Ride",
      start_date: "2026-06-16T07:42:00Z",
      start_date_local: "2026-06-16T07:42:00Z",
      distance_m: 38700,
      moving_time_s: 5662,
    },
  ],
```

- [ ] **Step 2: Write the failing tests**

In `frontend/src/api/overview.test.ts`, update the imports line to include `fetchOverview` and `vi`:

```typescript
import { describe, expect, it, vi } from "vitest";
import { toOverview, fetchOverview, overviewQueryOptions, OVERVIEW_REFETCH_INTERVAL_MS } from "./overview";
```

Add a test that `toRide` prefers local time (new `describe` or inside the existing `toOverview` block):

```typescript
  it("labels a recent ride by its local day, not UTC", () => {
    const dto = {
      ...DTO,
      recent_rides: [
        {
          id: 2,
          name: "Late ride",
          type: "Ride",
          start_date: "2026-06-21T06:00:00Z", // Sun UTC
          start_date_local: "2026-06-20T23:00:00Z", // Sat local
          distance_m: 12000,
          moving_time_s: 1200,
        },
      ],
    };
    expect(toOverview(dto).recentRides[0].meta).toBe("Sat · Jun 20 · Ride");
  });

  it("falls back to start_date when start_date_local is null", () => {
    const dto = {
      ...DTO,
      recent_rides: [
        {
          id: 3,
          name: "Legacy",
          type: "Ride",
          start_date: "2026-06-16T07:42:00Z",
          start_date_local: null,
          distance_m: 1000,
          moving_time_s: 100,
        },
      ],
    };
    expect(toOverview(dto).recentRides[0].meta).toBe("Tue · Jun 16 · Ride");
  });
```

And a test that `fetchOverview` sends the tz param (add as a new `describe`):

```typescript
describe("fetchOverview", () => {
  it("requests the overview with the browser timezone", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DTO), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await fetchOverview();
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("/activities/overview?tz=");
    vi.unstubAllGlobals();
  });
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd frontend && npm test -- overview`
Expected: the local-day test FAILS (meta still UTC `"Sun · Jun 21 · Ride"`) and the `fetchOverview` test FAILS (URL has no `tz=`).

- [ ] **Step 4: Implement `toRide` + `fetchOverview`**

In `frontend/src/api/overview.ts`, update `toRide` to format from local time with a fallback:

```typescript
function toRide(r: RecentRideDTO): DashRide {
  return {
    id: r.id,
    name: r.name,
    meta: `${fmtDate(r.start_date_local ?? r.start_date)} · ${r.type}`,
    distLabel: `${(r.distance_m / 1000).toFixed(1)} km`,
    durLabel: fmtDuration(r.moving_time_s),
  };
}
```

Update `fetchOverview` to send the browser zone:

```typescript
export function fetchOverview(): Promise<DashboardOverview> {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  return apiFetch<OverviewDTO>(
    `/activities/overview?tz=${encodeURIComponent(tz)}`,
  ).then(toOverview);
}
```

- [ ] **Step 5: Run the tests to verify pass**

Run: `cd frontend && npm test -- overview`
Expected: PASS (new + existing overview tests; `fmtDate` unchanged, fed local time).

- [ ] **Step 6: Full frontend gate, then commit**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: all pass.

```bash
git add frontend/src/types/overview.ts frontend/src/api/overview.ts frontend/src/api/overview.test.ts
git commit -m "feat(overview): send browser tz and label recent rides by local day

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Re-backfill existing rides + verify end-to-end

**Files:** none (operational).

**Interfaces:**
- Consumes: the deployed backend with Tasks 1-5 merged.

- [ ] **Step 1: Deploy backend + frontend** per the project's normal deploy (Render backend, Vercel frontend).

- [ ] **Step 2: Trigger one re-backfill per athlete** so existing rows get `start_date_local`. Use the existing refresh/backfill entrypoint (e.g. `POST /sync/...` or the backfill trigger the app already exposes). The upsert merges the new column onto existing rows.

- [ ] **Step 3: Verify the column is populated**

```sql
select count(*) as total,
       count(start_date_local) as with_local
from activities;
```

Expected: `with_local` equals `total` (or grows toward it as backfill completes).

- [ ] **Step 4: Browser smoke test** — open Overview, confirm a late-evening ride now sits on its local weekday in the chart and the recent-rides label matches.

---

## Self-Review

**Spec coverage:**
- Data column → Task 1. ✅
- Ingest `start_date_local` (sync + webhook via shared `_to_activity_row`) → Task 2. ✅
- Per-ride local bucketing + tz week window + widened query + null fallback → Task 3. ✅
- `tz` route param → Task 4. ✅
- Recent-ride label local + send browser tz → Task 5. ✅
- Rollout / re-backfill → Task 6. ✅
- Wall-clock invariant (never tz-convert) → enforced in `_local_naive` (drops tzinfo) and stated in Global Constraints. ✅
- `/activities` table untouched (non-goal) → no task modifies `list_activities`. ✅

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every command shows expected output.

**Type consistency:** `get_overview(supabase, athlete_id, tz="UTC", now=None)` is defined in Task 3 and called with `tz=` in Task 4 and patched with matching arity in the Task 4 test. `_local_naive(row: ActivityRow)` matches the `ActivityRow` type extended in Task 2. `RecentRideItem.start_date_local` (Task 3) ↔ `RecentRideDTO.start_date_local` (Task 5) ↔ `r.get("start_date_local")` (Task 3 service). `start_date_local: str | None` (backend) and `string | null` (frontend) align.
