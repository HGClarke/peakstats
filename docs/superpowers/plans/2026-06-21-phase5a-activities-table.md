# Activities Table (Phase 5.1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a server-side filtered/sorted/paginated `GET /activities` endpoint and the `/activities` screen (filter bar, sortable table, numbered pager) that browses an athlete's synced rides.

**Architecture:** Pagination is offset/page-based but made duplicate-free by a per-session `as_of` snapshot over a new `activities.created_at` column, with `id` as a sort tiebreaker. `sort`/`direction` are constrained by type aliases (Python `Literal`, TS union) and validated at the boundary. Backend follows the existing routers→services→db layering; frontend follows the `types → api → page/components` pattern with TanStack Query.

**Tech Stack:** FastAPI + httpx/PostgREST + Supabase (backend); React 19 + Vite + TanStack Query + Tailwind v4 (frontend); pytest (backend tests), Vitest + Testing Library (frontend tests).

## Global Constraints

- **Backend layering:** routers → services → db, no skipping. Services contain no `fastapi` imports. db modules are typed `httpx`/PostgREST wrappers returning `TypedDict`s. (`backend/CLAUDE.md`)
- **Backend types:** annotate every public function (params + return). Use plain `def` unless the body `await`s. Pydantic for all I/O boundaries.
- **Backend gates:** `cd backend && ruff check . && mypy && pytest` must be clean before each commit (a pre-commit hook runs ruff+mypy).
- **Frontend imports:** use the `@/` alias, never deep relative paths (relative is fine within a page folder).
- **Frontend types:** `enum`/namespaces/param-properties are banned (`erasableSyntaxOnly`). Use union literal types and `as const`.
- **Frontend styling:** use token utilities (`text-ink`, `bg-surface-card`, `border-line`, `text-strava`, …) — never raw hex or `dark:` pairs. Icons via `lucide-react`.
- **Frontend gates:** `cd frontend && npm test && npm run lint && npm run build` must pass before a change is done.
- **Data is metric.** This slice displays/filters in metric (km, m, min); the client converts UI inputs to the metric base before sending.
- **Page size is 9.**
- **Spec:** `docs/superpowers/specs/2026-06-21-phase5-activities-table-design.md`.

---

### Task 1: Migration — `activities.created_at` + `ActivityRow` field

**Files:**
- Create: `supabase/migrations/0002_activities_created_at.sql`
- Modify: `backend/app/db/activities.py` (`ActivityRow` TypedDict)

**Interfaces:**
- Produces: an `activities.created_at timestamptz` column (the snapshot boundary) and `ActivityRow["created_at"]` as an optional read field. Tasks 2–3 filter/echo on it.

This is schema scaffolding (no red/green unit test — Postgres schema isn't exercised by the httpx-mocked tests). Its deliverable is verified by the column existing and the existing suite staying green.

- [ ] **Step 1: Create the migration file**

`supabase/migrations/0002_activities_created_at.sql`:

```sql
-- Snapshot boundary for duplicate-free pagination of the activities list.
-- Records when each activity row was first ingested into our DB. Set once on
-- insert and preserved across PostgREST merge-duplicates upserts, because the
-- sync upsert payload omits this column.
alter table activities
  add column created_at timestamptz not null default now();
```

- [ ] **Step 2: Add `created_at` to the `ActivityRow` TypedDict**

In `backend/app/db/activities.py`, update the import and the TypedDict:

```python
from typing import NotRequired, TypedDict, cast
```

```python
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
    created_at: NotRequired[str]
```

- [ ] **Step 3: Apply the migration to Supabase**

Apply via the Supabase MCP `apply_migration` (name `activities_created_at`, the SQL above) or `supabase db push`.

- [ ] **Step 4: Verify the column exists and the suite is green**

Run (Supabase MCP `execute_sql` or psql):
```sql
select column_name from information_schema.columns
where table_name = 'activities' and column_name = 'created_at';
```
Expected: one row, `created_at`.

Then:
```bash
cd backend && ruff check . && mypy && pytest
```
Expected: all green (the `NotRequired` field is backward-compatible with existing upsert payloads).

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/0002_activities_created_at.sql backend/app/db/activities.py
git commit -m "feat(db): add activities.created_at snapshot column"
```

---

### Task 2: db — `list_activities_filtered`

**Files:**
- Modify: `backend/app/db/activities.py`
- Test: `backend/tests/db/test_activities.py`

**Interfaces:**
- Produces: `list_activities_filtered(client, athlete_id, *, q, min_dist, min_time, min_elev, order: str, as_of: str, offset: int, limit: int) -> tuple[list[ActivityRow], int]` and a private `_parse_total(response) -> int`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/db/test_activities.py`:

```python
def test_list_activities_filtered_builds_params_and_parses_total():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        seen["prefer"] = request.headers.get("prefer")
        seen["range"] = request.headers.get("range")
        return httpx.Response(
            200,
            json=[{"id": 9, "athlete_id": 7, "name": "Ride"}],
            headers={"Content-Range": "0-8/42"},
        )

    rows, total = activities.list_activities_filtered(
        _client(handler), 7,
        q="loop", min_dist=1000.0, min_time=600, min_elev=50.0,
        order="distance_m.desc,id.desc",
        as_of="2026-06-21T12:00:00+00:00",
        offset=0, limit=9,
    )
    p = seen["params"]
    assert p["athlete_id"] == "eq.7"
    assert p["created_at"] == "lte.2026-06-21T12:00:00+00:00"
    assert p["name"] == "ilike.*loop*"
    assert p["distance_m"] == "gte.1000.0"
    assert p["moving_time_s"] == "gte.600"
    assert p["elev_gain_m"] == "gte.50.0"
    assert p["order"] == "distance_m.desc,id.desc"
    assert p["select"] == "*"
    assert seen["prefer"] == "count=exact"
    assert seen["range"] == "0-8"
    assert total == 42
    assert rows == [{"id": 9, "athlete_id": 7, "name": "Ride"}]


def test_list_activities_filtered_omits_empty_filters():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=[], headers={"Content-Range": "*/0"})

    rows, total = activities.list_activities_filtered(
        _client(handler), 7,
        q=None, min_dist=None, min_time=None, min_elev=None,
        order="start_date.desc,id.desc",
        as_of="2026-06-21T12:00:00+00:00",
        offset=0, limit=9,
    )
    p = seen["params"]
    assert "name" not in p
    assert "distance_m" not in p
    assert "moving_time_s" not in p
    assert "elev_gain_m" not in p
    assert total == 0
    assert rows == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/db/test_activities.py -k list_activities_filtered -v`
Expected: FAIL with `AttributeError: module 'app.db.activities' has no attribute 'list_activities_filtered'`.

- [ ] **Step 3: Implement the function (and DRY the count parser)**

In `backend/app/db/activities.py`, add `_parse_total`, refactor `count_activities` to use it, and add `list_activities_filtered`:

```python
def _parse_total(response: httpx.Response) -> int:
    total = response.headers.get("Content-Range", "").split("/")[-1]
    return int(total) if total.isdigit() else 0


def list_activities_filtered(
    client: httpx.Client,
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
    params: dict[str, str] = {
        "athlete_id": f"eq.{athlete_id}",
        "created_at": f"lte.{as_of}",
        "order": order,
        "select": "*",
    }
    if q:
        params["name"] = f"ilike.*{q}*"
    if min_dist is not None:
        params["distance_m"] = f"gte.{min_dist}"
    if min_time is not None:
        params["moving_time_s"] = f"gte.{min_time}"
    if min_elev is not None:
        params["elev_gain_m"] = f"gte.{min_elev}"
    response = client.get(
        "/activities",
        params=params,
        headers={"Prefer": "count=exact", "Range": f"{offset}-{offset + limit - 1}"},
    )
    response.raise_for_status()
    return cast(list[ActivityRow], response.json()), _parse_total(response)
```

Replace the body of `count_activities`'s Content-Range parsing with `return _parse_total(response)`:

```python
def count_activities(client: httpx.Client, athlete_id: int) -> int:
    response = client.get(
        "/activities",
        params={"athlete_id": f"eq.{athlete_id}", "select": "id"},
        headers={"Prefer": "count=exact", "Range": "0-0"},
    )
    response.raise_for_status()
    return _parse_total(response)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/db/test_activities.py -v`
Expected: PASS (including the unchanged `count_activities` tests).

- [ ] **Step 5: Lint, type-check, commit**

```bash
cd backend && ruff check . && mypy
git add backend/app/db/activities.py backend/tests/db/test_activities.py
git commit -m "feat(db): list_activities_filtered with snapshot + count"
```

---

### Task 3: models + service — `list_activities`

**Files:**
- Modify: `backend/app/models/activities.py`
- Modify: `backend/app/services/activities.py`
- Test: `backend/tests/services/test_activities.py`

**Interfaces:**
- Consumes: `activities_db.list_activities_filtered(...)` (Task 2).
- Produces: types `SortField`, `SortDir`, `ActivityListItem`, `ActivityListResponse`; and `list_activities(supabase, athlete_id, *, q, min_dist, min_time, min_elev, sort: SortField, direction: SortDir, page: int, as_of: datetime | None = None) -> ActivityListResponse`.

- [ ] **Step 1: Add the models**

In `backend/app/models/activities.py`, update the header imports and append the new schemas:

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SortField = Literal["date", "distance", "time", "elevation", "speed"]
SortDir = Literal["asc", "desc"]
```

```python
class ActivityListItem(BaseModel):
    id: int
    name: str
    type: str
    start_date: str
    distance_m: float
    moving_time_s: int
    elev_gain_m: float
    avg_speed_ms: float | None


class ActivityListResponse(BaseModel):
    activities: list[ActivityListItem]
    page: int
    page_size: int
    total: int
    total_pages: int
    as_of: datetime
```

- [ ] **Step 2: Write the failing service tests**

Append to `backend/tests/services/test_activities.py`:

```python
LIST_ROWS = [
    {"id": 2, "athlete_id": 7, "name": "Wed ride", "type": "Ride",
     "start_date": "2026-06-17T09:00:00Z", "distance_m": 20000.0,
     "moving_time_s": 2000, "elapsed_time_s": 2000, "elev_gain_m": 50.0,
     "avg_speed_ms": 10.0, "avg_hr": None, "summary_polyline": None},
]


def _patch_list(monkeypatch, rows, total):
    captured = {}

    def fake(supabase, athlete_id, **kwargs):
        captured.update(kwargs)
        captured["athlete_id"] = athlete_id
        return rows, total

    monkeypatch.setattr(activities_service.activities_db,
                        "list_activities_filtered", fake)
    return captured


def test_list_builds_order_and_offset(monkeypatch):
    cap = _patch_list(monkeypatch, LIST_ROWS, 42)
    resp = activities_service.list_activities(
        object(), 7, q="loop", min_dist=1000.0, min_time=600, min_elev=50.0,
        sort="distance", direction="asc", page=3, as_of=NOW,
    )
    assert cap["order"] == "distance_m.asc,id.asc"
    assert cap["offset"] == 18  # (3 - 1) * 9
    assert cap["limit"] == 9
    assert cap["q"] == "loop"
    assert cap["as_of"] == NOW.isoformat()
    assert resp.page == 3
    assert resp.page_size == 9
    assert resp.total == 42
    assert resp.total_pages == 5  # ceil(42 / 9)
    assert resp.as_of == NOW
    assert resp.activities[0].id == 2
    assert resp.activities[0].avg_speed_ms == 10.0


def test_list_speed_sort_is_nullslast(monkeypatch):
    cap = _patch_list(monkeypatch, [], 0)
    activities_service.list_activities(
        object(), 7, q=None, min_dist=None, min_time=None, min_elev=None,
        sort="speed", direction="desc", page=1, as_of=NOW,
    )
    assert cap["order"] == "avg_speed_ms.desc.nullslast,id.desc"


def test_list_defaults_as_of_to_now(monkeypatch):
    cap = _patch_list(monkeypatch, [], 0)
    resp = activities_service.list_activities(
        object(), 7, q=None, min_dist=None, min_time=None, min_elev=None,
        sort="date", direction="desc", page=1,
    )
    assert cap["as_of"]  # an ISO timestamp was passed through
    assert resp.total_pages == 1  # max(1, ceil(0 / 9))
    assert resp.as_of is not None
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && pytest tests/services/test_activities.py -k list -v`
Expected: FAIL with `AttributeError: ... has no attribute 'list_activities'`.

- [ ] **Step 4: Implement the service**

In `backend/app/services/activities.py`, update the imports and add the function:

```python
from datetime import UTC, datetime, timedelta
from math import ceil

import httpx

from app.db import activities as activities_db
from app.db.activities import ActivityRow
from app.models.activities import (
    ActivityListItem,
    ActivityListResponse,
    OverviewResponse,
    RecentRideItem,
    SortDir,
    SortField,
    WeekDay,
    WeekTotals,
)

PAGE_SIZE = 9

_SORT_COLUMNS: dict[SortField, str] = {
    "date": "start_date",
    "distance": "distance_m",
    "time": "moving_time_s",
    "elevation": "elev_gain_m",
    "speed": "avg_speed_ms",
}
```

```python
def list_activities(
    supabase: httpx.Client,
    athlete_id: int,
    *,
    q: str | None,
    min_dist: float | None,
    min_time: int | None,
    min_elev: float | None,
    sort: SortField,
    direction: SortDir,
    page: int,
    as_of: datetime | None = None,
) -> ActivityListResponse:
    snapshot = as_of or datetime.now(UTC)
    column = _SORT_COLUMNS[sort]
    primary = (
        f"{column}.{direction}.nullslast" if sort == "speed"
        else f"{column}.{direction}"
    )
    order = f"{primary},id.{direction}"
    offset = (page - 1) * PAGE_SIZE

    rows, total = activities_db.list_activities_filtered(
        supabase, athlete_id,
        q=q, min_dist=min_dist, min_time=min_time, min_elev=min_elev,
        order=order, as_of=snapshot.isoformat(), offset=offset, limit=PAGE_SIZE,
    )
    items = [
        ActivityListItem(
            id=r["id"], name=r["name"], type=r["type"], start_date=r["start_date"],
            distance_m=r["distance_m"], moving_time_s=r["moving_time_s"],
            elev_gain_m=r["elev_gain_m"], avg_speed_ms=r["avg_speed_ms"],
        )
        for r in rows
    ]
    return ActivityListResponse(
        activities=items,
        page=page,
        page_size=PAGE_SIZE,
        total=total,
        total_pages=max(1, ceil(total / PAGE_SIZE)),
        as_of=snapshot,
    )
```

(The `from app.db.activities import ActivityRow` import already exists; keep it. Add only the new names.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && pytest tests/services/test_activities.py -v`
Expected: PASS (existing overview tests stay green).

- [ ] **Step 6: Lint, type-check, commit**

```bash
cd backend && ruff check . && mypy
git add backend/app/models/activities.py backend/app/services/activities.py backend/tests/services/test_activities.py
git commit -m "feat(service): list_activities with snapshot + sort allowlist"
```

---

### Task 4: router — `GET /activities`

**Files:**
- Modify: `backend/app/routers/activities.py`
- Test: `backend/tests/routers/test_activities.py`

**Interfaces:**
- Consumes: `activities_service.list_activities(...)` (Task 3), `SortField`, `SortDir`.

- [ ] **Step 1: Write the failing router tests**

Append to `backend/tests/routers/test_activities.py`:

```python
from app.models.activities import ActivityListItem, ActivityListResponse  # noqa: E402
from datetime import UTC, datetime  # noqa: E402


def _list_response() -> ActivityListResponse:
    return ActivityListResponse(
        activities=[ActivityListItem(
            id=2, name="Wed ride", type="Ride", start_date="2026-06-17T09:00:00Z",
            distance_m=20000.0, moving_time_s=2000, elev_gain_m=50.0, avg_speed_ms=10.0,
        )],
        page=1, page_size=9, total=1, total_pages=1,
        as_of=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
    )


def test_list_requires_session(client):
    assert client.get("/activities").status_code == 401


def test_list_returns_body(client, monkeypatch):
    captured = {}

    def fake(supabase, athlete_id, **kwargs):
        captured.update(kwargs)
        return _list_response()

    monkeypatch.setattr(activities_service, "list_activities", fake)
    _auth(client)
    response = client.get("/activities?sort=distance&direction=asc&page=1&min_dist=1000")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["activities"][0]["name"] == "Wed ride"
    assert captured["sort"] == "distance"
    assert captured["direction"] == "asc"
    assert captured["min_dist"] == 1000.0


def test_list_rejects_bad_sort(client):
    _auth(client)
    assert client.get("/activities?sort=bogus").status_code == 422


def test_list_rejects_bad_as_of(client):
    _auth(client)
    assert client.get("/activities?as_of=not-a-date").status_code == 422
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/routers/test_activities.py -k "list" -v`
Expected: FAIL — `GET /activities` is unrouted, so authed requests 404 (and the 422 assertions fail).

- [ ] **Step 3: Implement the route**

Replace `backend/app/routers/activities.py` with:

```python
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, Query

from app.deps import get_current_athlete_id, get_supabase
from app.models.activities import (
    ActivityListResponse,
    OverviewResponse,
    SortDir,
    SortField,
)
from app.services import activities as activities_service

router = APIRouter()


@router.get("", response_model=ActivityListResponse)
def list_activities(
    q: str | None = None,
    min_dist: float | None = None,
    min_time: int | None = None,
    min_elev: float | None = None,
    sort: SortField = "date",
    direction: SortDir = "desc",
    page: int = Query(1, ge=1),
    as_of: datetime | None = None,
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: httpx.Client = Depends(get_supabase),
) -> ActivityListResponse:
    return activities_service.list_activities(
        supabase, athlete_id,
        q=q, min_dist=min_dist, min_time=min_time, min_elev=min_elev,
        sort=sort, direction=direction, page=page, as_of=as_of,
    )


@router.get("/overview", response_model=OverviewResponse)
def overview(
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: httpx.Client = Depends(get_supabase),
) -> OverviewResponse:
    return activities_service.get_overview(supabase, athlete_id)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/routers/test_activities.py -v`
Expected: PASS (the existing `/activities/overview` tests stay green).

- [ ] **Step 5: Full backend gate + commit**

```bash
cd backend && ruff check . && mypy && pytest
git add backend/app/routers/activities.py backend/tests/routers/test_activities.py
git commit -m "feat(api): GET /activities list endpoint"
```

---

### Task 5: frontend — shared formatters in `lib/format.ts`

**Files:**
- Create: `frontend/src/lib/format.ts`
- Create: `frontend/src/lib/format.test.ts`
- Modify: `frontend/src/api/overview.ts`

**Interfaces:**
- Produces: `fmtDuration(seconds: number): string` ("1h 34m" / "10m") and `fmtDate(iso: string): string` ("Tue · Jun 16"). Task 7 uses both.

- [ ] **Step 1: Write the failing tests**

`frontend/src/lib/format.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { fmtDate, fmtDuration } from "./format";

describe("fmtDuration", () => {
  it("formats hours with zero-padded minutes", () => {
    expect(fmtDuration(5662)).toBe("1h 34m");
    expect(fmtDuration(22320)).toBe("6h 12m");
  });
  it("pads single-digit minutes after an hour", () => {
    expect(fmtDuration(3660)).toBe("1h 01m");
  });
  it("omits the hour under an hour", () => {
    expect(fmtDuration(600)).toBe("10m");
  });
});

describe("fmtDate", () => {
  it("formats weekday, month and day in UTC", () => {
    expect(fmtDate("2026-06-16T07:42:00Z")).toBe("Tue · Jun 16");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/format.test.ts`
Expected: FAIL — cannot resolve `./format`.

- [ ] **Step 3: Create `lib/format.ts`**

`frontend/src/lib/format.ts`:

```ts
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/** "1h 34m" / "10m" from a duration in seconds. */
export function fmtDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m < 10 ? "0" : ""}${m}m` : `${m}m`;
}

/** "Tue · Jun 16" from an ISO date, in UTC. */
export function fmtDate(iso: string): string {
  const d = new Date(iso);
  return `${WEEKDAYS[d.getUTCDay()]} · ${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/format.test.ts`
Expected: PASS.

- [ ] **Step 5: Refactor `overview.ts` to import the shared helpers**

In `frontend/src/api/overview.ts`: delete the local `WEEKDAYS`, `MONTHS`, `fmtDuration`, and `fmtDate` definitions, and add the import near the top:

```ts
import { fmtDate, fmtDuration } from "@/lib/format";
```

Leave the local `delta` helper and everything else unchanged.

- [ ] **Step 6: Verify nothing regressed**

Run: `cd frontend && npx vitest run src/api/overview.test.ts src/lib/format.test.ts`
Expected: PASS (the overview mapping output is unchanged).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/format.ts frontend/src/lib/format.test.ts frontend/src/api/overview.ts
git commit -m "refactor(frontend): extract shared fmtDuration/fmtDate into lib/format"
```

---

### Task 6: frontend — pager util `lib/pager.ts`

**Files:**
- Create: `frontend/src/lib/pager.ts`
- Create: `frontend/src/lib/pager.test.ts`

**Interfaces:**
- Produces: `type PagerToken` and `makePager(current: number, totalPages: number): PagerToken[]` (1-based pages). Task 9's pager uses it.

- [ ] **Step 1: Write the failing tests**

`frontend/src/lib/pager.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { makePager, type PagerToken } from "./pager";

const labels = (t: PagerToken[]) =>
  t.map((x) => (x.kind === "gap" ? "…" : x.label));

describe("makePager", () => {
  it("lists every page when there are 7 or fewer", () => {
    expect(labels(makePager(1, 5))).toEqual(["1", "2", "3", "4", "5"]);
  });
  it("marks the current page active", () => {
    const active = makePager(3, 5).find((t) => t.kind === "page" && t.active);
    expect(active).toMatchObject({ kind: "page", page: 3 });
  });
  it("gaps on the right near the start", () => {
    expect(labels(makePager(2, 12))).toEqual(["1", "2", "3", "4", "…", "12"]);
  });
  it("gaps on the left near the end", () => {
    expect(labels(makePager(11, 12))).toEqual(["1", "…", "9", "10", "11", "12"]);
  });
  it("gaps on both sides in the middle", () => {
    expect(labels(makePager(6, 12))).toEqual(["1", "…", "5", "6", "7", "…", "12"]);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/pager.test.ts`
Expected: FAIL — cannot resolve `./pager`.

- [ ] **Step 3: Implement `lib/pager.ts`**

`frontend/src/lib/pager.ts` (port of the prototype's `makePager`, converted to 1-based pages):

```ts
export type PagerToken =
  | { kind: "page"; page: number; label: string; active: boolean }
  | { kind: "gap" };

/** Build pager tokens for a 1-based `current` page over `totalPages`. */
export function makePager(current: number, totalPages: number): PagerToken[] {
  const out: PagerToken[] = [];
  const add = (p: number) =>
    out.push({ kind: "page", page: p, label: String(p), active: p === current });
  const gap = () => out.push({ kind: "gap" });

  if (totalPages <= 7) {
    for (let p = 1; p <= totalPages; p++) add(p);
    return out;
  }
  add(1);
  let start = Math.max(2, current - 1);
  let end = Math.min(totalPages - 1, current + 1);
  if (current <= 3) { start = 2; end = 4; }
  if (current >= totalPages - 2) { start = totalPages - 3; end = totalPages - 1; }
  if (start > 2) gap();
  for (let p = start; p <= end; p++) add(p);
  if (end < totalPages - 1) gap();
  add(totalPages);
  return out;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/pager.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/pager.ts frontend/src/lib/pager.test.ts
git commit -m "feat(frontend): makePager pager-token util"
```

---

### Task 7: frontend — types + api (`types/activities.ts`, `api/activities.ts`)

**Files:**
- Create: `frontend/src/types/activities.ts`
- Create: `frontend/src/api/activities.ts`
- Create: `frontend/src/api/activities.test.ts`

**Interfaces:**
- Consumes: `fmtDate`, `fmtDuration` (Task 5); `apiFetch` (`api/client.ts`).
- Produces: `SortField`, `SortDir`, `ActivityListItemDTO`, `ActivityListDTO`, `ActivityRowVM`, `ActivitiesQuery`, `buildActivitiesQuery(query): string`, `toActivityRow(dto): ActivityRowVM`, `fetchActivities(query)`, `useActivities(query)`. Task 9 uses these.

- [ ] **Step 1: Create the types**

`frontend/src/types/activities.ts`:

```ts
export type SortField = "date" | "distance" | "time" | "elevation" | "speed";
export type SortDir = "asc" | "desc";

/** Raw activity item from `GET /activities`. */
export interface ActivityListItemDTO {
  id: number;
  name: string;
  type: string;
  start_date: string;
  distance_m: number;
  moving_time_s: number;
  elev_gain_m: number;
  avg_speed_ms: number | null;
}

export interface ActivityListDTO {
  activities: ActivityListItemDTO[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  as_of: string;
}

/** Formatted row the table renders. */
export interface ActivityRowVM {
  id: number;
  name: string;
  meta: string;       // "Tue · Jun 16 · Ride"
  distLabel: string;  // "38.7 km"
  durLabel: string;   // "1h 34m"
  elevLabel: string;  // "1,240 m"
  speedLabel: string; // "24.8 km/h" or "—"
}
```

- [ ] **Step 2: Write the failing api tests**

`frontend/src/api/activities.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { ActivitiesQuery } from "./activities";
import { buildActivitiesQuery, toActivityRow } from "./activities";

const base: ActivitiesQuery = {
  q: "", minDist: "", minTime: "", minElev: "",
  sort: "date", direction: "desc", page: 1, asOf: null,
};

describe("buildActivitiesQuery", () => {
  it("omits empty filters and a null asOf", () => {
    const qs = new URLSearchParams(buildActivitiesQuery(base));
    expect(qs.get("q")).toBeNull();
    expect(qs.get("min_dist")).toBeNull();
    expect(qs.get("as_of")).toBeNull();
    expect(qs.get("sort")).toBe("date");
    expect(qs.get("direction")).toBe("desc");
    expect(qs.get("page")).toBe("1");
  });
  it("trims search and converts km->m, min->s, m->m", () => {
    const qs = new URLSearchParams(buildActivitiesQuery({
      ...base, q: "  loop ", minDist: "10", minTime: "30", minElev: "500",
    }));
    expect(qs.get("q")).toBe("loop");
    expect(qs.get("min_dist")).toBe("10000");
    expect(qs.get("min_time")).toBe("1800");
    expect(qs.get("min_elev")).toBe("500");
  });
  it("includes asOf when set", () => {
    const qs = new URLSearchParams(
      buildActivitiesQuery({ ...base, asOf: "2026-06-21T12:00:00Z" }),
    );
    expect(qs.get("as_of")).toBe("2026-06-21T12:00:00Z");
  });
});

describe("toActivityRow", () => {
  it("formats a ride row", () => {
    expect(toActivityRow({
      id: 1, name: "River loop", type: "Ride",
      start_date: "2026-06-16T07:42:00Z",
      distance_m: 38700, moving_time_s: 5662, elev_gain_m: 1240, avg_speed_ms: 6.889,
    })).toEqual({
      id: 1, name: "River loop", meta: "Tue · Jun 16 · Ride",
      distLabel: "38.7 km", durLabel: "1h 34m", elevLabel: "1,240 m",
      speedLabel: "24.8 km/h",
    });
  });
  it("shows an em dash for missing speed", () => {
    expect(toActivityRow({
      id: 2, name: "No GPS", type: "Ride", start_date: "2026-06-16T07:42:00Z",
      distance_m: 1000, moving_time_s: 600, elev_gain_m: 0, avg_speed_ms: null,
    }).speedLabel).toBe("—");
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/api/activities.test.ts`
Expected: FAIL — cannot resolve `./activities`.

- [ ] **Step 4: Implement `api/activities.ts`**

`frontend/src/api/activities.ts`:

```ts
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { fmtDate, fmtDuration } from "@/lib/format";
import type {
  ActivityListDTO,
  ActivityListItemDTO,
  ActivityRowVM,
  SortDir,
  SortField,
} from "@/types/activities";
import { apiFetch } from "./client";

export interface ActivitiesQuery {
  q: string;
  minDist: string; // raw UI input, km
  minTime: string; // raw UI input, minutes
  minElev: string; // raw UI input, meters
  sort: SortField;
  direction: SortDir;
  page: number;
  asOf: string | null;
}

/** Build the `GET /activities` querystring, converting UI units to metric. */
export function buildActivitiesQuery(query: ActivitiesQuery): string {
  const p = new URLSearchParams();
  const q = query.q.trim();
  if (q) p.set("q", q);
  if (query.minDist !== "") p.set("min_dist", String(Number(query.minDist) * 1000));
  if (query.minTime !== "") p.set("min_time", String(Number(query.minTime) * 60));
  if (query.minElev !== "") p.set("min_elev", String(Number(query.minElev)));
  p.set("sort", query.sort);
  p.set("direction", query.direction);
  p.set("page", String(query.page));
  if (query.asOf) p.set("as_of", query.asOf);
  return p.toString();
}

export function toActivityRow(dto: ActivityListItemDTO): ActivityRowVM {
  return {
    id: dto.id,
    name: dto.name,
    meta: `${fmtDate(dto.start_date)} · ${dto.type}`,
    distLabel: `${(dto.distance_m / 1000).toFixed(1)} km`,
    durLabel: fmtDuration(dto.moving_time_s),
    elevLabel: `${Math.round(dto.elev_gain_m).toLocaleString("en-US")} m`,
    speedLabel:
      dto.avg_speed_ms === null ? "—" : `${(dto.avg_speed_ms * 3.6).toFixed(1)} km/h`,
  };
}

export function fetchActivities(query: ActivitiesQuery): Promise<ActivityListDTO> {
  return apiFetch<ActivityListDTO>(`/activities?${buildActivitiesQuery(query)}`);
}

export function useActivities(query: ActivitiesQuery) {
  return useQuery({
    queryKey: ["activities", "list", query],
    queryFn: () => fetchActivities(query),
    placeholderData: keepPreviousData,
  });
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/api/activities.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/activities.ts frontend/src/api/activities.ts frontend/src/api/activities.test.ts
git commit -m "feat(frontend): activities types + api (query builder, mapper, hook)"
```

---

### Task 8: frontend — sidebar nav wiring

**Files:**
- Modify: `frontend/src/components/app-shell/Sidebar.tsx`
- Create: `frontend/src/components/app-shell/Sidebar.test.tsx`
- Modify: `frontend/src/components/app-shell/AppShell.test.tsx` (wrap in a router)

**Interfaces:**
- Produces: Sidebar items for built routes render as `<Link>` (Overview→`/home`, Activities→`/activities`); unbuilt items stay inert.

- [ ] **Step 1: Write the failing Sidebar test**

`frontend/src/components/app-shell/Sidebar.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { Sidebar } from "./Sidebar";

const athlete = {
  id: 1, name: "Ada Lovelace", avatar_url: null,
  settings: { units: "metric", theme: "dark", default_period: "week" },
};

function renderSidebar() {
  render(
    <MemoryRouter>
      <Sidebar navActive="Activities" athlete={athlete} syncLabel="Up to date"
        onLogout={() => {}} />
    </MemoryRouter>,
  );
}

describe("Sidebar", () => {
  it("links built routes and leaves unbuilt ones inert", () => {
    renderSidebar();
    expect(screen.getByRole("link", { name: /activities/i }))
      .toHaveAttribute("href", "/activities");
    expect(screen.getByRole("link", { name: /overview/i }))
      .toHaveAttribute("href", "/home");
    expect(screen.queryByRole("link", { name: /segments/i })).toBeNull();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/app-shell/Sidebar.test.tsx`
Expected: FAIL — Activities renders as a `<div>`, so `getByRole("link")` finds nothing.

- [ ] **Step 3: Wire the nav in `Sidebar.tsx`**

Replace the `NAV_ITEMS` constant and the `<nav>` block in `frontend/src/components/app-shell/Sidebar.tsx`. Add `import { Link } from "react-router";` at the top.

```tsx
const NAV_ITEMS: { label: string; to?: string }[] = [
  { label: "Overview", to: "/home" },
  { label: "Activities", to: "/activities" },
  { label: "Segments" },
  { label: "Trends" },
  { label: "Goals" },
];
```

```tsx
      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ label, to }) => {
          const active = label === navActive;
          const className = `flex items-center gap-[11px] px-[11px] py-[9px] rounded-[9px] ${
            active ? "bg-strava-soft" : ""
          }`;
          const inner = (
            <>
              <span
                className={`w-[6px] h-[6px] rounded-full ${active ? "bg-strava" : "bg-muted5"}`}
              />
              <span
                className={`text-[14px] font-medium ${active ? "text-ink2" : "text-subtle"}`}
              >
                {label}
              </span>
            </>
          );
          return to ? (
            <Link key={label} to={to} className={className}>
              {inner}
            </Link>
          ) : (
            <div key={label} className={className}>
              {inner}
            </div>
          );
        })}
      </nav>
```

- [ ] **Step 4: Wrap the AppShell test in a router**

In `frontend/src/components/app-shell/AppShell.test.tsx`, add `import { MemoryRouter } from "react-router";` and wrap each `<AppShell>…</AppShell>` passed to `renderWithProviders` in `<MemoryRouter>…</MemoryRouter>`. Example for the first test:

```tsx
    renderWithProviders(
      <MemoryRouter>
        <AppShell navActive="Overview" athlete={athlete} syncLabel="Up to date"
          onLogout={() => {}} title="Home">
          <div>body</div>
        </AppShell>
      </MemoryRouter>,
    );
```

Apply the same wrapping to the second test (the logout one).

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/app-shell`
Expected: PASS (both Sidebar and AppShell suites).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/app-shell/Sidebar.tsx frontend/src/components/app-shell/Sidebar.test.tsx frontend/src/components/app-shell/AppShell.test.tsx
git commit -m "feat(frontend): sidebar navigates to built routes"
```

---

### Task 9: frontend — Activities screen (debounce hook, components, page, route)

**Files:**
- Create: `frontend/src/lib/useDebouncedValue.ts`
- Create: `frontend/src/lib/useDebouncedValue.test.ts`
- Create: `frontend/src/pages/activities/components/ActivityFilterBar.tsx`
- Create: `frontend/src/pages/activities/components/ActivityTable.tsx`
- Create: `frontend/src/pages/activities/components/ActivityPager.tsx`
- Create: `frontend/src/pages/activities/ActivitiesPage.tsx`
- Create: `frontend/src/pages/activities/ActivitiesPage.test.tsx`
- Modify: `frontend/src/app/router.tsx`

**Interfaces:**
- Consumes: `useActivities`, `toActivityRow`, `ActivitiesQuery` (Task 7); `makePager` (Task 6); `AppShell`; `useAthlete`/`logout`/`disconnect` (`@/api/auth`); `useSyncStatus` (`@/api/sync`).

- [ ] **Step 1: Write the failing debounce-hook test**

`frontend/src/lib/useDebouncedValue.test.ts`:

```ts
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useDebouncedValue } from "./useDebouncedValue";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("useDebouncedValue", () => {
  it("returns the initial value immediately", () => {
    const { result } = renderHook(() => useDebouncedValue("a", 300));
    expect(result.current).toBe("a");
  });
  it("updates only after the delay elapses", () => {
    const { result, rerender } = renderHook(
      ({ v }) => useDebouncedValue(v, 300),
      { initialProps: { v: "a" } },
    );
    rerender({ v: "b" });
    expect(result.current).toBe("a");
    act(() => vi.advanceTimersByTime(300));
    expect(result.current).toBe("b");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/useDebouncedValue.test.ts`
Expected: FAIL — cannot resolve `./useDebouncedValue`.

- [ ] **Step 3: Implement the debounce hook**

`frontend/src/lib/useDebouncedValue.ts`:

```ts
import { useEffect, useState } from "react";

/** Returns `value` delayed by `delayMs`, resetting the timer on each change. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/useDebouncedValue.test.ts`
Expected: PASS.

- [ ] **Step 5: Create the filter bar component**

`frontend/src/pages/activities/components/ActivityFilterBar.tsx`:

```tsx
import { Search } from "lucide-react";

interface Props {
  q: string;
  minDist: string;
  minTime: string;
  minElev: string;
  onQ: (v: string) => void;
  onMinDist: (v: string) => void;
  onMinTime: (v: string) => void;
  onMinElev: (v: string) => void;
  onClear: () => void;
}

const numberBox =
  "flex items-center gap-2 h-10 bg-surface-card border border-line rounded-[10px] px-3";
const numberInput =
  "w-12 bg-transparent border-none outline-none text-ink font-mono text-[13px]";
const label = "font-mono text-[10px] tracking-[0.08em] text-faint";

export function ActivityFilterBar({
  q, minDist, minTime, minElev,
  onQ, onMinDist, onMinTime, onMinElev, onClear,
}: Props) {
  return (
    <div className="flex items-center gap-[10px] mb-4 flex-wrap">
      <div className="flex items-center gap-[9px] flex-1 min-w-[220px] h-10 bg-surface-card border border-line rounded-[10px] px-[14px]">
        <Search size={15} className="text-faint" aria-hidden />
        <input
          value={q}
          onChange={(e) => onQ(e.target.value)}
          placeholder="Search activities…"
          aria-label="Search activities"
          className="flex-1 bg-transparent border-none outline-none text-ink text-[13.5px]"
        />
      </div>
      <div className={numberBox}>
        <span className={label}>DIST ≥</span>
        <input type="number" min="0" value={minDist} onChange={(e) => onMinDist(e.target.value)}
          placeholder="0" aria-label="Minimum distance (km)" className={numberInput} />
        <span className="text-[11px] text-subtle">km</span>
      </div>
      <div className={numberBox}>
        <span className={label}>TIME ≥</span>
        <input type="number" min="0" value={minTime} onChange={(e) => onMinTime(e.target.value)}
          placeholder="0" aria-label="Minimum time (min)" className={numberInput} />
        <span className="text-[11px] text-subtle">min</span>
      </div>
      <div className={numberBox}>
        <span className={label}>ELEV ≥</span>
        <input type="number" min="0" value={minElev} onChange={(e) => onMinElev(e.target.value)}
          placeholder="0" aria-label="Minimum elevation (m)" className={numberInput} />
        <span className="text-[11px] text-subtle">m</span>
      </div>
      <button
        onClick={onClear}
        className="h-10 px-[14px] rounded-[10px] bg-transparent border border-line text-subtle text-[13px] cursor-pointer hover:text-ink"
      >
        Clear
      </button>
    </div>
  );
}
```

- [ ] **Step 6: Create the table component**

`frontend/src/pages/activities/components/ActivityTable.tsx`:

```tsx
import { ArrowDown, ArrowUp, ChevronRight } from "lucide-react";
import type { ActivityRowVM, SortDir, SortField } from "@/types/activities";

interface Props {
  rows: ActivityRowVM[];
  sort: SortField;
  direction: SortDir;
  onSort: (field: SortField) => void;
  emptyMessage: string | null;
}

const COLUMNS: { label: string; field: SortField | null }[] = [
  { label: "ACTIVITY", field: null },
  { label: "DISTANCE", field: "distance" },
  { label: "TIME", field: "time" },
  { label: "ELEVATION", field: "elevation" },
  { label: "AVG SPEED", field: "speed" },
];

const grid = "grid grid-cols-[1.7fr_1fr_1fr_1fr_1fr_36px] gap-3 items-center";

export function ActivityTable({ rows, sort, direction, onSort, emptyMessage }: Props) {
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-2">
      <div className={`${grid} px-[18px] py-[14px] font-mono text-[10px] tracking-[0.1em] text-faint border-b border-line-subtle`}>
        {COLUMNS.map(({ label, field }) =>
          field ? (
            <button
              key={label}
              onClick={() => onSort(field)}
              className={`flex items-center gap-1 select-none bg-transparent border-none cursor-pointer text-left font-mono ${
                sort === field ? "text-ink" : "text-faint"
              }`}
            >
              {label}
              {sort === field &&
                (direction === "asc"
                  ? <ArrowUp size={11} aria-hidden />
                  : <ArrowDown size={11} aria-hidden />)}
            </button>
          ) : (
            <span key={label} className="select-none">{label}</span>
          ),
        )}
        <span />
      </div>

      {rows.map((r) => (
        <div key={r.id} className={`${grid} px-[18px] py-[15px] rounded-[11px]`}>
          <div className="flex items-center gap-[13px] min-w-0">
            <span className="w-[9px] h-[9px] rounded-full bg-strava flex-none" />
            <div className="min-w-0">
              <div className="text-[14px] font-medium text-ink truncate">{r.name}</div>
              <div className="font-mono text-[10.5px] text-faint mt-[2px]">{r.meta}</div>
            </div>
          </div>
          <span className="font-display font-semibold text-[15px] text-ink">{r.distLabel}</span>
          <span className="font-mono text-[13px] text-body">{r.durLabel}</span>
          <span className="font-mono text-[13px] text-body">{r.elevLabel}</span>
          <span className="font-mono text-[13px] text-body">{r.speedLabel}</span>
          <ChevronRight size={16} className="text-faint justify-self-end" aria-hidden />
        </div>
      ))}

      {emptyMessage && (
        <div className="px-[18px] py-12 text-center text-subtle text-[14px]">
          {emptyMessage}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 7: Create the pager component**

`frontend/src/pages/activities/components/ActivityPager.tsx`:

```tsx
import { makePager } from "@/lib/pager";

interface Props {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPage: (page: number) => void;
}

const edgeBtn =
  "h-[34px] px-3 rounded-[8px] border border-line bg-transparent text-subtle text-[13px] font-medium disabled:opacity-40 disabled:cursor-default enabled:cursor-pointer";

export function ActivityPager({ page, totalPages, total, pageSize, onPage }: Props) {
  if (totalPages <= 1) return null;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(total, page * pageSize);

  return (
    <div className="flex items-center justify-between mt-[18px]">
      <span className="font-mono text-[11px] text-faint">
        Showing {start}–{end} of {total} activities
      </span>
      <div className="flex items-center gap-[6px]">
        <button className={edgeBtn} disabled={page === 1} onClick={() => onPage(page - 1)}>
          ‹ Prev
        </button>
        {makePager(page, totalPages).map((t, i) =>
          t.kind === "gap" ? (
            <span key={`gap-${i}`} className="w-[34px] text-center text-faint font-mono text-[13px]">
              …
            </span>
          ) : (
            <button
              key={t.page}
              onClick={() => onPage(t.page)}
              className={`min-w-[34px] h-[34px] px-[10px] rounded-[8px] font-mono text-[13px] cursor-pointer border ${
                t.active
                  ? "bg-strava text-white border-strava"
                  : "bg-transparent text-subtle border-line"
              }`}
            >
              {t.label}
            </button>
          ),
        )}
        <button className={edgeBtn} disabled={page >= totalPages} onClick={() => onPage(page + 1)}>
          Next ›
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 8: Create the page**

`frontend/src/pages/activities/ActivitiesPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { disconnect, logout, useAthlete } from "@/api/auth";
import { type ActivitiesQuery, toActivityRow, useActivities } from "@/api/activities";
import { useSyncStatus } from "@/api/sync";
import { AppShell } from "@/components/app-shell/AppShell";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import type { SortField } from "@/types/activities";
import { ActivityFilterBar } from "./components/ActivityFilterBar";
import { ActivityPager } from "./components/ActivityPager";
import { ActivityTable } from "./components/ActivityTable";

function SkeletonRows() {
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-2" role="status"
      aria-label="Loading activities">
      {[0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
        <div key={i} className="px-[18px] py-[15px]">
          <div className="h-4 w-full rounded bg-skel animate-pkskel" />
        </div>
      ))}
    </div>
  );
}

export default function ActivitiesPage() {
  const { data: athlete, error } = useAthlete();
  const { data: status } = useSyncStatus();
  const navigate = useNavigate();

  const [q, setQ] = useState("");
  const [minDist, setMinDist] = useState("");
  const [minTime, setMinTime] = useState("");
  const [minElev, setMinElev] = useState("");
  const [sort, setSort] = useState<SortField>("date");
  const [direction, setDirection] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [asOf, setAsOf] = useState<string | null>(null);

  const dq = useDebouncedValue(q, 300);
  const dDist = useDebouncedValue(minDist, 300);
  const dTime = useDebouncedValue(minTime, 300);
  const dElev = useDebouncedValue(minElev, 300);

  const query: ActivitiesQuery = {
    q: dq, minDist: dDist, minTime: dTime, minElev: dElev,
    sort, direction, page, asOf,
  };
  const { data, isLoading } = useActivities(query);

  useEffect(() => {
    if (error) navigate("/", { replace: true });
  }, [error, navigate]);

  useEffect(() => {
    if (status?.status === "never_synced") navigate("/sync", { replace: true });
  }, [status, navigate]);

  useEffect(() => {
    if (data?.as_of && asOf === null) setAsOf(data.as_of);
  }, [data, asOf]);

  // Reset to page 1 whenever a filter or sort changes (keep the snapshot).
  useEffect(() => {
    setPage(1);
  }, [dq, dDist, dTime, dElev, sort, direction]);

  const synced = status?.status === "idle";

  const handleSort = (field: SortField) => {
    if (field === sort) {
      setDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSort(field);
      setDirection("desc");
    }
  };

  const handleClear = () => {
    setQ(""); setMinDist(""); setMinTime(""); setMinElev("");
  };

  const handleLogout = async () => { await logout(); navigate("/", { replace: true }); };
  const handleDisconnect = async () => { await disconnect(); navigate("/", { replace: true }); };

  const rows = (data?.activities ?? []).map(toActivityRow);
  const total = data?.total ?? 0;
  const filtersActive = Boolean(q || minDist || minTime || minElev);
  const emptyMessage =
    rows.length > 0 ? null
      : filtersActive ? "No activities match your filters."
        : "No activities yet.";

  return (
    <AppShell
      navActive="Activities"
      athlete={athlete}
      syncLabel={synced ? "Up to date" : "Syncing…"}
      onLogout={handleLogout}
      title="Activities"
      subtitle={synced ? `${total} RIDES` : "SYNCING"}
    >
      <div className="h-full overflow-y-auto p-7">
        <ActivityFilterBar
          q={q} minDist={minDist} minTime={minTime} minElev={minElev}
          onQ={setQ} onMinDist={setMinDist} onMinTime={setMinTime} onMinElev={setMinElev}
          onClear={handleClear}
        />
        {isLoading && !data ? (
          <SkeletonRows />
        ) : (
          <>
            <ActivityTable
              rows={rows} sort={sort} direction={direction}
              onSort={handleSort} emptyMessage={emptyMessage}
            />
            <ActivityPager
              page={data?.page ?? 1}
              totalPages={data?.total_pages ?? 1}
              total={total}
              pageSize={data?.page_size ?? 9}
              onPage={setPage}
            />
          </>
        )}
        <div className="pt-7">
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

- [ ] **Step 9: Register the route**

In `frontend/src/app/router.tsx`, import the page and add the route before the `*` catch-all:

```tsx
import ActivitiesPage from "@/pages/activities/ActivitiesPage";
```

```tsx
  { path: "/home", element: <AppHome /> },
  { path: "/activities", element: <ActivitiesPage /> },
  { path: "/sync", element: <SyncPage /> },
```

- [ ] **Step 10: Write the page test**

`frontend/src/pages/activities/ActivitiesPage.test.tsx`:

```tsx
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/providers";
import type { ActivitiesQuery } from "@/api/activities";
import type { ActivityListDTO } from "@/types/activities";

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
vi.mock("@/api/sync", () => ({ useSyncStatus: () => useSyncStatus() }));

const useActivities = vi.fn();
vi.mock("@/api/activities", async () => {
  const actual = await vi.importActual<typeof import("@/api/activities")>("@/api/activities");
  return { ...actual, useActivities: (query: ActivitiesQuery) => useActivities(query) };
});

import ActivitiesPage from "./ActivitiesPage";

const athlete = {
  id: 99, name: "Ada Lovelace", avatar_url: null,
  settings: { units: "metric", theme: "dark", default_period: "week" },
};
const synced = { status: "idle", progress: 100, synced: 200,
  last_backfill_at: "T", last_sync_at: "T" };

function dto(over: Partial<ActivityListDTO> = {}): ActivityListDTO {
  return {
    activities: [{
      id: 1, name: "River loop", type: "Ride", start_date: "2026-06-16T07:42:00Z",
      distance_m: 38700, moving_time_s: 5662, elev_gain_m: 1240, avg_speed_ms: 6.889,
    }],
    page: 1, page_size: 9, total: 1, total_pages: 1, as_of: "2026-06-21T12:00:00Z",
    ...over,
  };
}

function lastQuery(): ActivitiesQuery {
  return useActivities.mock.calls.at(-1)![0] as ActivitiesQuery;
}

function renderPage() {
  renderWithProviders(<MemoryRouter><ActivitiesPage /></MemoryRouter>);
}

beforeEach(() => {
  useAthlete.mockReturnValue({ data: athlete, isLoading: false, error: null });
  useSyncStatus.mockReturnValue({ data: synced });
  useActivities.mockReturnValue({ data: dto(), isLoading: false });
});
afterEach(() => vi.clearAllMocks());

describe("ActivitiesPage", () => {
  it("renders rows from the hook", () => {
    renderPage();
    expect(screen.getByText("River loop")).toBeInTheDocument();
    expect(screen.getByText("38.7 km")).toBeInTheDocument();
  });

  it("shows the skeleton while loading the first page", () => {
    useActivities.mockReturnValue({ data: undefined, isLoading: true });
    renderPage();
    expect(screen.getByLabelText(/loading activities/i)).toBeInTheDocument();
    expect(screen.queryByText("River loop")).not.toBeInTheDocument();
  });

  it("shows the no-rides empty state", () => {
    useActivities.mockReturnValue({ data: dto({ activities: [], total: 0 }), isLoading: false });
    renderPage();
    expect(screen.getByText("No activities yet.")).toBeInTheDocument();
  });

  it("shows the no-match empty state when a filter is set", () => {
    useActivities.mockReturnValue({ data: dto({ activities: [], total: 0 }), isLoading: false });
    renderPage();
    fireEvent.change(screen.getByLabelText(/search activities/i), { target: { value: "zzz" } });
    expect(screen.getByText("No activities match your filters.")).toBeInTheDocument();
  });

  it("toggles sort field and direction via headers", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /distance/i }));
    expect(lastQuery()).toMatchObject({ sort: "distance", direction: "desc" });
    fireEvent.click(screen.getByRole("button", { name: /distance/i }));
    expect(lastQuery()).toMatchObject({ sort: "distance", direction: "asc" });
  });

  it("requests the next page from the pager", () => {
    useActivities.mockReturnValue({ data: dto({ total: 20, total_pages: 3 }), isLoading: false });
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(lastQuery()).toMatchObject({ page: 2 });
  });

  it("captures the snapshot from the first response and reuses it", async () => {
    renderPage();
    await waitFor(() =>
      expect(lastQuery()).toMatchObject({ asOf: "2026-06-21T12:00:00Z" }));
  });

  it("redirects to /sync when never synced", async () => {
    useSyncStatus.mockReturnValue({ data: { status: "never_synced", progress: 0, synced: 0,
      last_backfill_at: null, last_sync_at: null } });
    renderPage();
    await waitFor(() =>
      expect(mockNavigate).toHaveBeenCalledWith("/sync", { replace: true }));
  });
});
```

- [ ] **Step 11: Run the page suite to verify it passes**

Run: `cd frontend && npx vitest run src/pages/activities src/lib/useDebouncedValue.test.ts`
Expected: PASS.

- [ ] **Step 12: Full frontend gate + commit**

```bash
cd frontend && npm test && npm run lint && npm run build
git add frontend/src/lib/useDebouncedValue.ts frontend/src/lib/useDebouncedValue.test.ts frontend/src/pages/activities frontend/src/app/router.tsx
git commit -m "feat(frontend): /activities screen (filter, sortable table, pager)"
```

---

### Task 10: End-to-end verification

**Files:** none (verification only).

- [ ] **Step 1: Run both full test gates**

```bash
cd backend && ruff check . && mypy && pytest
cd ../frontend && npm test && npm run lint && npm run build
```
Expected: all green.

- [ ] **Step 2: Manual smoke test against the running app**

Start backend (`cd backend && uvicorn app.main:app --reload`) and frontend (`cd frontend && npm run dev`). With a synced athlete:
- Navigate Overview → Activities via the sidebar; the URL becomes `/activities` and the nav highlights Activities.
- The table lists rides; the subtitle shows the ride count.
- Search narrows by name; DIST/TIME/ELEV `≥` filters reduce the list; Clear resets them.
- Clicking DISTANCE/TIME/ELEVATION/AVG SPEED headers sorts and toggles the arrow.
- The pager moves between pages; page 1→2→1 shows no duplicate rows (snapshot holds).
- Rows show the `›` chevron but are not clickable (ride detail is Phase 6.4).

- [ ] **Step 3: Confirm and report**

Report the gate output and smoke-test observations. Do not claim done unless every gate passed and the smoke test behaved as described.

---

## Self-Review

**Spec coverage:**
- `GET /activities` filter/sort/paginate → Tasks 2–4. ✓
- Snapshot/`created_at`/`as_of`/`id` tiebreaker → Tasks 1–4. ✓
- Type aliases (`Literal`/union), 422 validation, `direction` rename → Tasks 3, 4, 7. ✓
- `/activities` screen: filter bar, sortable table, numbered pager, states → Task 9. ✓
- Sidebar nav wiring → Task 8. ✓
- Shared formatters `lib/format.ts` → Task 5. ✓
- `makePager` util → Task 6. ✓
- Unit conversion (km→m, min→s) → Task 7. ✓
- Non-goals (PR badge, ride-detail nav, units toggle, Trends) → not implemented, by design. ✓

**Type consistency:** `list_activities_filtered` signature matches between Task 2 (produces) and Task 3 (consumes); `list_activities` matches between Task 3 (produces) and Task 4 (consumes); `ActivitiesQuery`/`toActivityRow`/`useActivities` match between Task 7 (produces) and Task 9 (consumes); `makePager` matches Task 6 → Task 9; `SortField`/`SortDir` are defined once per side (backend `models`, frontend `types`). ✓

**Placeholder scan:** every code step contains complete code and exact commands. ✓
