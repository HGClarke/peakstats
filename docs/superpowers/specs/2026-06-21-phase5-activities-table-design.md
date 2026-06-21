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

**Server-side filter / sort / paginate**, as the parent spec mandates
(`GET /activities?q=&min_dist=&min_time=&min_elev=&sort=&page=`). The prototype filters
client-side over a fully-loaded array; that does not scale and is not a real backend
slice. The backend already has the PostgREST building blocks — `ilike`/`gte` operators,
`order`, and the `count=exact` + `Range` + `Content-Range` pattern used by
`count_activities` in `db/activities.py`.

Page size is **9**, matching the prototype's table-card layout.

## Backend — `GET /activities`

New list endpoint on the existing activities router (mounted at `/activities`; the
relative path `""` keeps it distinct from `/activities/overview`).

### Query parameters

All metric. All optional; defaults applied server-side.

| Param | Type | Default | Maps to (PostgREST) |
|---|---|---|---|
| `q` | str | — | `name=ilike.*<q>*` (case-insensitive substring) |
| `min_dist` | float (meters) | — | `distance_m=gte.<v>` |
| `min_time` | int (seconds) | — | `moving_time_s=gte.<v>` |
| `min_elev` | float (meters) | — | `elev_gain_m=gte.<v>` |
| `sort` | enum: `date \| distance \| time \| elevation \| speed` | `date` | allowlist → column |
| `dir` | enum: `asc \| desc` | `desc` | order direction |
| `page` | int ≥ 1 | `1` | `Range` offset; page size 9 |

- **Sort allowlist (injection-safe):** `{date→start_date, distance→distance_m,
  time→moving_time_s, elevation→elev_gain_m, speed→avg_speed_ms}`. The raw `sort` value
  is never interpolated into the `order` param — only the mapped column name is used.
  `speed` orders as `avg_speed_ms.<dir>.nullslast` (the column is nullable).
- **Validation:** unknown `sort` or `dir` → service raises `ValueError` → router returns
  HTTP **400**. Negative/zero filter values are passed through (harmless `gte`).

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
    order: str,          # already-mapped, e.g. "distance_m.desc" / "avg_speed_ms.desc.nullslast"
    offset: int,
    limit: int,
) -> tuple[list[ActivityRow], int]:
    ...
```

One PostgREST GET against `/activities` with `athlete_id=eq.<id>`, the active filters,
`order=<order>`, `select=*`, header `Prefer: count=exact`, and `Range: <offset>-<offset+limit-1>`.
Returns the rows plus the total parsed from the `Content-Range` header (same parsing
approach as the existing `count_activities`). Only non-`None` filters are added to the
params dict.

**service** (`app/services/activities.py`) — add:

```python
PAGE_SIZE = 9

_SORT_COLUMNS = {
    "date": "start_date",
    "distance": "distance_m",
    "time": "moving_time_s",
    "elevation": "elev_gain_m",
    "speed": "avg_speed_ms",
}

def list_activities(
    supabase, athlete_id, *,
    q, min_dist, min_time, min_elev, sort, dir, page,
) -> ActivityListResponse: ...
```

Validates `sort`/`dir` against the allowlists (raise `ValueError` otherwise), builds the
`order` string (`<column>.<dir>`, appending `.nullslast` for `speed`), computes
`offset = (page - 1) * PAGE_SIZE`, calls the db function, maps `ActivityRow` →
`ActivityListItem`, and computes `total_pages = max(1, ceil(total / PAGE_SIZE))`. Pages
beyond range simply yield an empty `activities` list while still reporting the true
`total`/`total_pages` so the client can correct.

**models** (`app/models/activities.py`) — add:

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
```

**router** (`app/routers/activities.py`) — add:

```python
@router.get("", response_model=ActivityListResponse)
def list_activities(
    q: str | None = None,
    min_dist: float | None = None,
    min_time: int | None = None,
    min_elev: float | None = None,
    sort: str = "date",
    dir: str = "desc",
    page: int = 1,
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: httpx.Client = Depends(get_supabase),
) -> ActivityListResponse:
    try:
        return activities_service.list_activities(
            supabase, athlete_id,
            q=q, min_dist=min_dist, min_time=min_time, min_elev=min_elev,
            sort=sort, dir=dir, page=page,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

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
  - `ActivityListItemDTO` (matches the backend item).
  - `ActivityListDTO` `{ activities, page, page_size, total, total_pages }`.
  - `ActivityRowVM` — formatted for render: `{ id, name, meta, distLabel, durLabel,
    elevLabel, speedLabel, dotColor }` (`meta` e.g. `"Tue · Jun 3 · Ride"`;
    `speedLabel` is `"—"` when `avg_speed_ms` is null).
- **api** (`api/activities.ts`):
  - `ActivitiesQuery { q; minDist; minTime; minElev; sort; dir; page }` — `minDist`,
    `minTime`, `minElev` carry the **raw UI-input values** in the units shown in the
    filter bar (km, minutes, meters).
  - `fetchActivities(query): Promise<ActivityListDTO>` — builds the querystring (omitting
    empty filters) and calls `apiFetch`. **It converts the UI-unit inputs to the
    endpoint's metric base** when serializing: `min_dist = km × 1000` (meters),
    `min_time = min × 60` (seconds), `min_elev = meters` (unchanged). This is the only
    unit handling in this slice; the km↔mi toggle (Phase 7) will later feed converted
    metric values in here the same way.
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
  keeps the slice focused. Holds filter/sort/page state in `useState`; **debounces the
  search + numeric inputs by 300ms**; sort and page changes fire immediately. Page resets
  to 1 whenever a filter or sort changes.
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
  params/headers (only active filters present; `Range` offsets; `count=exact`) and parses
  the total from `Content-Range`.
- `tests/services/test_activities.py`: filter passthrough; sort allowlist maps correctly
  and raises `ValueError` on bad `sort`/`dir`; `speed` gets `.nullslast`; pagination math
  (`offset`, `total_pages`); row → `ActivityListItem` mapping.
- `tests/routers/test_activities.py`: `GET /activities` happy path (service mocked),
  query-param parsing/defaults, and **400** on invalid `sort`.

**Frontend** (Vitest + Testing Library):
- `lib/format.test.ts`: `fmtDuration`, `fmtDate`.
- `lib/pager.test.ts`: `makePager` token generation (≤7 pages, gaps at both ends, active
  marking, edges).
- `api/activities.test.ts`: querystring building (omits empty filters; converts
  km→m, min→s, m→m) + DTO → VM mapping (incl. null speed → "—").
- `pages/activities/ActivitiesPage.test.tsx`: renders rows from a mocked hook; loading
  skeleton; both empty states; filter/sort/page interactions update the query; page resets
  on filter change.

Run gates before done: backend `ruff check . && mypy && pytest`; frontend
`npm test && npm run lint && npm run build`.

## Delivery checkpoint

A single increment, verified end to end: connect → backfill → open `/activities` →
search/filter/sort/page over real synced rides, with the sidebar navigating between
Overview and Activities. Independently demoable and mergeable.
