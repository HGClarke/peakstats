# Phase 5.1 — Activities table — Design Spec

**Date:** 2026-06-21
**Status:** Approved (design); pending implementation plan
**Parent spec:** `docs/superpowers/specs/2026-06-20-peakstats-design.md` (Phase 5, item 1)
**Source design:** `docs/design/Peakstats Dashboard.dc.html` — the `showActivities` view

## Overview

The Overview dashboard (Phase 3a/4) shows aggregates, but there is no way to browse
the actual list of rides. This increment adds the **Activities table**: a server-side
filtered, sorted, and paginated list of the athlete's activities, plus the `/activities`
screen that renders it — a faithful port of the prototype's Activities view.

This is one vertical slice per the project's delivery principle: backend endpoint +
frontend screen + tests, implemented and verified before the next increment. Trends
(Phase 5.3) is a separate increment and is **not** part of this spec.

## Goals

- `GET /activities` endpoint: filter (search + 3 numeric `≥` filters), sort, paginate —
  all server-side via PostgREST.
- **Duplicate-free numbered pagination**: a snapshot (`as_of`) boundary freezes the
  result set for the browsing session so offset paging can't show duplicates/skips when
  new rides arrive via refresh/webhooks.
- **Type-safe enumerated params**: `sort`/`direction` are constrained to a fixed set of
  values via type aliases (Python `Literal`, TS union literals), enforced at the boundary
  and statically by the type checkers.
- `/activities` screen: filter bar, sortable table, numbered pager, empty/loading states.
- Make the sidebar nav actually navigate (for the routes that exist).
- Keep the layering and conventions in `backend/CLAUDE.md` and `frontend/CLAUDE.md`.

## Non-goals (this increment)

- **km/mi unit toggle** — the app is metric-only today (Overview hardcodes km). Full
  unit conversion is Phase 7. This slice displays and filters in **metric** (km, m, min).
- **PR badge on rows** — no segment/PR data exists yet and `is_pr` is not in the
  `activities` schema (Phase 6).
- **Row → ride detail navigation** — the ride detail screen is Phase 6.4. Rows render
  the `›` chevron for visual fidelity but are **non-interactive** (no click handler, no
  pointer cursor). Phase 6.4 wires the click to `/activities/:id` in one change.
- **Trends screen** (`GET /athlete/stats/trends` + UI) — Phase 5.3.
- Wiring the not-yet-built nav items (Segments, Trends, Goals) — they stay inert.

## Approach

**Server-side filter / sort / paginate**, as the parent spec mandates. The prototype
filters client-side over a fully-loaded array; that does not scale and is not a real
backend slice. The backend already has the PostgREST building blocks — `ilike`/`gte`
operators, `order`, and the `count=exact` + `Range` + `Content-Range` pattern used by
`count_activities` in `db/activities.py`.

Page size is **9**, matching the prototype's table-card layout.

### Pagination & snapshot (duplicate-free)

Pagination is **offset/page based** (so the prototype's numbered pager with jump-to-page
and `…` gaps is preserved), but made stable with a per-session **snapshot boundary**:

- A new `activities.created_at` column records when each row was ingested into our DB.
- The first list request of a browsing session omits `as_of`; the server mints
  `as_of = now()` (server clock), returns it in the response, and the client **reuses
  that same `as_of` on every subsequent page/filter/sort request**.
- Every query filters `created_at <= as_of`, so the result set can't grow mid-session.
  New rides synced by refresh/webhooks are simply excluded until the user re-enters the
  screen (which mints a fresh `as_of`). This removes the insert-driven duplicate/skip
  that plain offset paging suffers.
- **Total ordering for stability:** every sort appends `id` as a tiebreaker
  (`order=<col>.<direction>,id.<direction>`). Without a unique tiebreaker, rows with equal sort
  values could swap order between page requests and re-introduce a boundary duplicate
  even within a frozen set.

Remaining edge: deleting a row from *within* the snapshot can cause a one-row skip
(not a duplicate). Activity deletes are rare and out of scope to fully solve here.

## Data-model change — `activities.created_at`

A Supabase migration adds the snapshot column:

```sql
alter table activities
  add column created_at timestamptz not null default now();
```

- Existing rows get the migration timestamp (all `<= ` any future `as_of`, so they
  always appear). New rows get their real ingestion time via the `default now()`.
- The sync upsert **does not** write `created_at` — it's omitted from the upsert payload
  so the column is set once on insert and preserved by PostgREST `merge-duplicates`
  on refresh. In `db/activities.py`, `created_at` is added to the `ActivityRow`
  `TypedDict` as `NotRequired[str]` (present on reads, absent on writes).
- Migration lives under `supabase/` alongside the existing schema migrations.

## Backend — `GET /activities`

New list endpoint on the existing activities router (mounted at `/activities`; the
relative path `""` keeps it distinct from `/activities/overview`).

### Query parameters

Filters are metric. All optional; defaults applied server-side.

| Param | Type | Default | Maps to (PostgREST) |
|---|---|---|---|
| `q` | str | — | `name=ilike.*<q>*` (case-insensitive substring) |
| `min_dist` | float (meters) | — | `distance_m=gte.<v>` |
| `min_time` | int (seconds) | — | `moving_time_s=gte.<v>` |
| `min_elev` | float (meters) | — | `elev_gain_m=gte.<v>` |
| `sort` | `SortField` (Literal) | `date` | allowlist → column |
| `direction` | `SortDir` (Literal) | `desc` | order direction |
| `page` | int ≥ 1 | `1` | `Range` offset; page size 9 |
| `as_of` | `datetime` (ISO 8601) | server `now()` | `created_at=lte.<as_of>` |

- **Type-safe enums:** `sort` and `direction` are typed with `Literal` aliases (below).
  FastAPI/Pydantic validate query params against the `Literal`, so an out-of-set value
  is rejected with **HTTP 422** automatically — no hand-written validation, and mypy
  guarantees only valid values reach the service. (`direction`, not `dir`, to avoid
  shadowing the Python builtin / a ruff `A002` warning.)
- **`as_of`** is typed `datetime | None`, so FastAPI parses and validates the ISO value
  (422 on a malformed timestamp) and the service mints `datetime.now(UTC)` when absent.
- **Sort allowlist (injection-safe):** `{date→start_date, distance→distance_m,
  time→moving_time_s, elevation→elev_gain_m, speed→avg_speed_ms}`. The raw value is
  never interpolated into `order` — only the mapped column name is. `speed` orders as
  `avg_speed_ms.<direction>.nullslast` (the column is nullable). Every order string appends the
  `id` tiebreaker.

### Shared type aliases

```python
# app/models/activities.py
from typing import Literal

SortField = Literal["date", "distance", "time", "elevation", "speed"]
SortDir = Literal["asc", "desc"]
```

Used by both the router signature and the service signature so the constraint is one
definition enforced end to end.

### Layers (routers → services → db)

**db** (`app/db/activities.py`) — add:

```python
def list_activities_filtered(
    client: httpx.Client,
    athlete_id: int,
    *,
    q: str | None,
    min_dist: float | None,
    min_time: int | None,
    min_elev: float | None,
    order: str,          # already-mapped + tiebreaker, e.g. "distance_m.desc,id.desc"
    as_of: str,          # ISO datetime; filters created_at<=as_of
    offset: int,
    limit: int,
) -> tuple[list[ActivityRow], int]:
    ...
```

One PostgREST GET against `/activities` with `athlete_id=eq.<id>`, `created_at=lte.<as_of>`,
the active filters, `order=<order>`, `select=*`, header `Prefer: count=exact`, and
`Range: <offset>-<offset+limit-1>`. Returns the rows plus the total parsed from the
`Content-Range` header (same parsing approach as the existing `count_activities`). Only
non-`None` filters are added to the params dict. `ActivityRow` gains
`created_at: NotRequired[str]`.

**service** (`app/services/activities.py`) — add:

```python
PAGE_SIZE = 9

_SORT_COLUMNS: dict[SortField, str] = {
    "date": "start_date",
    "distance": "distance_m",
    "time": "moving_time_s",
    "elevation": "elev_gain_m",
    "speed": "avg_speed_ms",
}

def list_activities(
    supabase, athlete_id, *,
    q, min_dist, min_time, min_elev,
    sort: SortField, direction: SortDir, page: int,
    as_of: datetime | None = None,
) -> ActivityListResponse: ...
```

Mints `as_of = datetime.now(UTC)` when the caller passes none (tests pass an explicit
`as_of` for determinism); passes `as_of.isoformat()` to the db `created_at` filter;
builds the `order` string (`<column>.<direction>`, `.nullslast` for `speed`, then
`,id.<direction>`); computes `offset = (page - 1) * PAGE_SIZE`; calls the db function;
maps `ActivityRow` → `ActivityListItem`; computes `total_pages = max(1, ceil(total /
PAGE_SIZE))`; echoes `as_of` in the response. Because `sort`/`direction` are `Literal`-typed,
the `_SORT_COLUMNS` lookup is total — no runtime enum validation needed. Pages beyond
range yield an empty `activities` list while still reporting the true `total`/`total_pages`.

**models** (`app/models/activities.py`) — add the aliases above plus:

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

**router** (`app/routers/activities.py`) — add:

```python
@router.get("", response_model=ActivityListResponse)
def list_activities(
    q: str | None = None,
    min_dist: float | None = None,
    min_time: int | None = None,
    min_elev: float | None = None,
    sort: SortField = "date",
    direction: SortDir = "desc",
    page: int = 1,
    as_of: datetime | None = None,
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: httpx.Client = Depends(get_supabase),
) -> ActivityListResponse:
    return activities_service.list_activities(
        supabase, athlete_id,
        q=q, min_dist=min_dist, min_time=min_time, min_elev=min_elev,
        sort=sort, direction=direction, page=page, as_of=as_of,
    )
```

No try/except: invalid `sort`/`direction` are rejected by FastAPI as 422 before the
handler runs; everything reaching the service is already valid.

## Frontend — `/activities` screen

### Routing & navigation

- Add `/activities` → `pages/activities/ActivitiesPage.tsx` to the `routes` array in
  `app/router.tsx` (before the `*` catch-all).
- **Sidebar** (`components/app-shell/Sidebar.tsx`): give each nav entry an optional
  `to` route. Items with a route render as react-router `<Link>` and navigate; items
  without one (Segments, Trends, Goals) render exactly as today (inert — no dead links).
  Wire **Overview → `/home`**, **Activities → `/activities`**. The existing `navActive`
  prop continues to drive active styling (minimal change; no active-from-URL refactor).

### Data layer

- **types** (`types/activities.ts`):
  - `SortField = "date" | "distance" | "time" | "elevation" | "speed"` and
    `SortDir = "asc" | "desc"` (union literals — `frontend/CLAUDE.md` bans `enum`).
  - `ActivityListItemDTO` (matches the backend item).
  - `ActivityListDTO` `{ activities, page, page_size, total, total_pages, as_of }`.
  - `ActivityRowVM` — formatted for render: `{ id, name, meta, distLabel, durLabel,
    elevLabel, speedLabel, dotColor }` (`meta` e.g. `"Tue · Jun 3 · Ride"`;
    `speedLabel` is `"—"` when `avg_speed_ms` is null).
- **api** (`api/activities.ts`):
  - `ActivitiesQuery { q; minDist; minTime; minElev; sort: SortField; direction: SortDir;
    page; asOf: string | null }` — `minDist`/`minTime`/`minElev` carry the **raw UI-input
    values** in the units shown in the filter bar (km, minutes, meters); `asOf` is the
    session snapshot (null on the first request).
  - `fetchActivities(query): Promise<ActivityListDTO>` — builds the querystring (omitting
    empty filters and a null `asOf`) and calls `apiFetch`. **Converts UI-unit inputs to
    the endpoint's metric base**: `min_dist = km × 1000`, `min_time = min × 60`,
    `min_elev = meters` (unchanged). Emits `sort`/`direction`/`as_of` as-is.
  - mapping `ActivityListItemDTO → ActivityRowVM`.
  - `useActivities(query)` — `useQuery({ queryKey: ["activities", "list", query],
    queryFn, placeholderData: keepPreviousData })` so paging/filtering does not flash an
    empty table.
- **shared formatters** (`lib/format.ts`): extract `fmtDuration` and `fmtDate` out of
  `api/overview.ts` into `lib/format.ts` (unit-tested) and have `overview.ts` import
  them. Small dedupe — both surfaces format the same ride fields.

### Page & components

- **`ActivitiesPage.tsx`** (composition only): reuses `AppShell` with
  `navActive="Activities"` and the same athlete/sync/logout wiring and `/` + `/sync`
  guards as `AppHome`. Header: `title="Activities"`, `subtitle` = total count
  (e.g. `"142 RIDES"`). **No Refresh/Disconnect button** — those stay on Overview; this
  keeps the slice focused. Holds filter/sort/page/`asOf` state in `useState`;
  **debounces the search + numeric inputs by 300ms**; sort and page changes fire
  immediately. **Snapshot lifecycle:** `asOf` starts `null`; on the first successful
  response it is set to `data.as_of` and reused thereafter. Page resets to 1 whenever a
  filter or sort changes (but `asOf` is kept). Re-mounting the screen starts a fresh
  snapshot.
- **`components/ActivityFilterBar.tsx`**: search input + three numeric `≥` filters
  (DIST/TIME/ELEV) + Clear button. Presentational — values + change handlers via props.
- **`components/ActivityTable.tsx`**: sortable header row (DISTANCE / TIME / ELEVATION /
  AVG SPEED, with ↑/↓ on the active column; ACTIVITY column not sortable), data rows
  (dot + name + `meta`, then distance/time/elevation/speed, then the `›` chevron),
  **non-interactive rows**, and the `"No activities match your filters."` empty state.
- **`components/ActivityPager.tsx`**: page-range text (`"Showing 1–9 of 142 activities"`),
  Prev/Next, and the numbered pager with `…` gaps. Hidden when `total_pages <= 1`.
- **`lib/pager.ts`**: port the prototype's `makePager(cur, total)` to a pure function
  returning tokens `{ kind: "page" | "gap"; label; page?; active? }`, unit-tested. (Note
  the prototype is 0-based internally; the API page is 1-based — the util adapts.)

### States

- **Loading** (initial): skeleton table rows.
- **never_synced:** redirect to `/sync` (mirrors `AppHome`).
- **synced, zero activities total:** empty message ("No activities yet.").
- **filters match nothing:** "No activities match your filters."
- Subsequent loads (paging/filtering) keep the previous page visible via
  `keepPreviousData`.

## Testing

**Backend** (pytest; patch at the service boundary per conventions):
- `tests/db/test_activities.py`: `list_activities_filtered` builds the correct PostgREST
  params/headers — only active filters present, `created_at=lte.<as_of>`, the `order`
  string incl. the `id` tiebreaker, `Range` offsets, `count=exact` — and parses the total
  from `Content-Range`.
- `tests/services/test_activities.py`: filter passthrough; sort map → column + `direction`;
  `speed` gets `.nullslast`; order always appends `id`; an explicit `as_of` is passed
  through to the db filter and echoed in the response (and defaults to `now()` when
  absent); pagination math (`offset`, `total_pages`); row → `ActivityListItem` mapping.
- `tests/routers/test_activities.py`: `GET /activities` happy path (service mocked) and
  query-param parsing/defaults; **422** on an out-of-set `sort`/`direction` or a malformed
  `as_of` (FastAPI validation); a valid `as_of` passed through.

**Frontend** (Vitest + Testing Library):
- `lib/format.test.ts`: `fmtDuration`, `fmtDate`.
- `lib/pager.test.ts`: `makePager` token generation (≤7 pages, gaps at both ends, active
  marking, edges).
- `api/activities.test.ts`: querystring building (omits empty filters and null `asOf`;
  converts km→m, min→s, m→m; passes `sort`/`direction`/`as_of`) + DTO → VM mapping
  (incl. null speed → "—").
- `pages/activities/ActivitiesPage.test.tsx`: renders rows from a mocked hook; loading
  skeleton; both empty states; filter/sort/page interactions update the query; page resets
  on filter change; `asOf` is captured from the first response and reused.

Run gates before done: backend `ruff check . && mypy && pytest`; frontend
`npm test && npm run lint && npm run build`.

## Delivery checkpoint

A single increment, verified end to end: connect → backfill → open `/activities` →
search/filter/sort/page over real synced rides (no duplicates across pages), with the
sidebar navigating between Overview and Activities. Independently demoable and mergeable.
