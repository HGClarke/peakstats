# Segments list — fix 1000-row cap + paginated, snapshotted list

**Date:** 2026-06-22
**Branch:** `feat/activity-detail-analytics` (continuing) — or a fresh branch off `main`.

## Problem

The `/segments` list page shows far fewer segments than are stored. Root cause:
`list_athlete_efforts` (`backend/app/db/segments.py`) selects `segment_efforts` with no
`.range()`/`.limit()`, so it inherits PostgREST's default `max-rows = 1000` cap. The
service (`list_segments`) builds the **entire** segment list by aggregating those efforts
in Python, so the list is only as complete as that truncated 1000-row slice. For one
athlete with ~3,928 efforts across 577 segments, only ~148–228 segments appear (the exact
count varies with Postgres's unspecified row order).

Separately, the list has no pagination — it renders every segment at once, unlike the
Activities list which has a numbered pager.

## Goal

1. **Fix the cap** so every segment with an effort appears.
2. **Add numbered pagination** to the segments list, matching the Activities list UX
   (reuse the existing `<Pager>`), including **snapshot + offset** for stable, drift-free
   paging.

## Approach

The segments list is a **Python aggregation** across all of an athlete's efforts — each
segment needs its full effort history to compute best-time, attempts, PR, latest-rank,
improvement, and the recent-trend sparkline. That is unlike the Activities list (one DB
row per item, paginated at the DB with `.range()`).

Chosen approach: **fetch all efforts, aggregate in Python (unchanged), then
filter/sort/slice the aggregated list and return the same pagination envelope the
Activities list uses.** A SQL/RPC aggregation was considered and rejected as
over-engineering at single-athlete scale (~4k rows) — it would force re-implementing the
trend/rank/improvement logic in SQL.

Stable paging uses **snapshot + offset** (the user's established preference for new list
endpoints). `segment_efforts` has no insert-timestamp today (`start_date` is the effort's
ride time, not its ingest time), so this requires a small migration to add `created_at`.

## Changes

### 1. Migration — `supabase/migrations/0004_segment_efforts_created_at.sql`

Mirror `0002_activities_created_at.sql`:

```sql
alter table segment_efforts
  add column created_at timestamptz not null default now();
```

`ADD COLUMN … DEFAULT now()` stamps all existing rows at migration time. The sync upsert
payload omits the column, so it's preserved across PostgREST merge-duplicate upserts. This
is the snapshot boundary.

### 2. `backend/app/db/segments.py`

- `SegmentEffortRow`: add `created_at: NotRequired[str]` (mirrors `ActivityRow`; the upsert
  path still omits it and lets the DB default it).
- Rewrite `list_athlete_efforts(client, athlete_id, as_of)`:
  - New `as_of: str` parameter; filter `.lte("created_at", as_of)`.
  - Loop `.range(start, start + PAGE - 1)` (PAGE = 1000), accumulating rows until a page
    shorter than PAGE returns. This both un-truncates the read and applies the snapshot
    filter. Looping is required because PostgREST caps each response at `max-rows` no
    matter how wide the requested range is.
  - Keep the existing `segments(name, distance_m, avg_grade)` join select.

### 3. `backend/app/models/segments.py`

`SegmentListResponse` gains pagination fields (identical shape to `ActivityListResponse`):

```python
class SegmentListResponse(BaseModel):
    segments: list[SegmentListItem]
    page: int
    page_size: int
    total: int
    total_pages: int
    as_of: datetime
```

### 4. `backend/app/services/segments.py`

- New constant `SEGMENT_PAGE_SIZE = 10`.
- `list_segments` gains `page: int` and `as_of: datetime | None = None`.
- Flow: `snapshot = as_of or datetime.now(UTC)` → `list_athlete_efforts(.., snapshot.isoformat())`
  → aggregate per segment (unchanged) → `q` filter (unchanged) → sort (unchanged) →
  `total = len(items)`; `offset = (page - 1) * SEGMENT_PAGE_SIZE`; slice
  `items[offset : offset + SEGMENT_PAGE_SIZE]` → return with `page`, `page_size`,
  `total`, `total_pages = max(1, ceil(total / SEGMENT_PAGE_SIZE))`, `as_of = snapshot`.

### 5. `backend/app/routers/segments.py`

Add query params, mirroring the activities router:

```python
page: int = Query(1, ge=1),
as_of: datetime | None = None,
```

Pass both through to the service.

### 6. Frontend

- `types/segments.ts` — `SegmentListDTO` gains `page`, `page_size`, `total`,
  `total_pages`, `as_of: string`.
- `api/segments.ts` — `SegmentsQuery` gains `page: number` and `asOf: string | null`;
  `buildSegmentsQuery` sets `page` and (when present) `as_of`.
- `pages/segments/SegmentsPage.tsx`:
  - Add `page` and `asOf` state. Capture `as_of` from the first response using the
    render-time state pattern already used in `ActivitiesPage.tsx`.
  - Reset `page → 1` on search change and on the attempts sort toggle.
  - Subtitle shows `total` (`${total} SEGMENTS`) instead of `data?.segments.length`.
  - Render the existing `<Pager … noun="segments" />` below `<SegmentTable>`.

## Testing

- **Backend**
  - `tests/db/test_segments.py`: `list_athlete_efforts` loops past 1000 rows (regression
    for the bug) and filters by `created_at <= as_of`.
  - `tests/services/test_segments.py`: pagination math (slice, `total`, `total_pages`);
    aggregates computed from the full effort set (not just the returned page);
    `as_of`/snapshot passthrough.
  - `tests/routers/test_segments.py`: `page` and `as_of` are parsed and forwarded.
- **Frontend**
  - `api/segments.test.ts`: `buildSegmentsQuery` includes `page` and `as_of`.
  - `SegmentsPage.test.tsx`: `<Pager>` renders for multi-page results; page resets on
    search/sort; subtitle uses `total`.

## Verification

- `cd backend && ruff check . && mypy && pytest`
- `cd frontend && npm test && npm run lint && npm run build`
- Apply the migration to Supabase; confirm the live list now shows all ~577 segments and
  the pager navigates correctly.

## Out of scope

- The one orphan `segments` row with no efforts (578 rows vs 577 with efforts) — cosmetic,
  unchanged here.
- Additional segment sort fields (only `attempts` asc/desc today) — unchanged.
- SQL/RPC aggregation — deferred; revisit only if effort volume grows by an order of
  magnitude.
