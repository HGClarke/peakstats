# Peakstats — Segments Feature Design Spec

**Date:** 2026-06-21
**Status:** Approved (design); pending implementation plan
**Source design:** Claude Design project "Ride Analytics Platform" → `Peakstats Segments.dc.html`
**Parent spec:** [`2026-06-20-peakstats-design.md`](2026-06-20-peakstats-design.md) (Phase 6.1–6.3)

## Overview

This spec covers the **Segments** feature: a searchable list of the segments an
athlete has ridden, and a per-segment detail screen that compares the athlete's
personal best against any other attempt and lists all attempts with power/speed/HR.

Segment data is **derived** from the `segment_efforts` array inside Strava's
*detailed* activity payload (`GET /activities/{id}`) — Peakstats never calls the
Strava segment API. The `segments` and `segment_efforts` tables (plus RLS) already
exist from migration `0001_init.sql`, so **no schema migration is required**.

## Goals

- Port the design's two new screens faithfully: Segments list and Segment detail/compare.
- Populate `segment_efforts` reliably without breaching Strava rate limits.
- Keep the layering and conventions in `backend/CLAUDE.md` and `frontend/CLAUDE.md`.

## Non-goals (explicitly out of scope)

- **Overview redesign** (highlights tiles, activity heatmap, ride-types donut,
  Overview "Personal records / SEGMENTS" panel) — captured as a *separate future
  spec*; not built here.
- **Ride detail screen** (Phase 6.4) — not required, because segment data no longer
  depends on lazy ride-detail fetches (see Data population). Attempt rows on the
  segment detail screen set the compare target only; they do **not** navigate to a
  ride.
- Segment starring/favourites, leaderboards, or comparison against other athletes.

## Data model (existing — no migration)

Both tables already exist with athlete-scoped RLS:

- **segments** — `id` (Strava segment id, PK), `name`, `distance_m`, `avg_grade`.
  Shared reference data; readable by any authenticated athlete.
- **segment_efforts** — `id` (Strava effort id, PK), `segment_id` FK, `athlete_id` FK,
  `activity_id` FK, `elapsed_time_s`, `avg_watts` (nullable), `avg_hr` (nullable),
  `avg_speed_ms`, `start_date`, `is_best` (derived per athlete+segment).
  Indexed on `(athlete_id, segment_id)` and `(activity_id)`.

A segment appears in the UI only when the athlete has ≥1 effort on it.

## Data population

The detailed activity payload carries `segment_efforts`. Two paths fill the tables;
both are **idempotent** (PK = Strava effort id) and resumable.

### 1. New rides — webhook extract (≈free)

`services/webhooks.process_event` *already* fetches `strava.get_activity()` (the
detailed payload) for every create/update event and discards everything but the
summary fields. We extend it: after upserting the activity row, extract
`segment_efforts` from the same payload, upsert segments + efforts, and recompute
`is_best` for the affected `(athlete_id, segment_id)` pairs. No extra Strava calls.

### 2. History — background detail-backfill worker (throttled)

Backfill (`run_backfill`) only fetches activity *summaries*, so historical activities
have `detail_fetched_at IS NULL` and no efforts. A new background worker
(`services/sync.run_detail_backfill`, mirroring the existing `run_backfill` pattern)
walks those activities oldest-first and, for each:

1. `strava.get_activity()` → detailed payload.
2. Upsert segments + efforts; recompute `is_best`.
3. Opportunistically store `splits_metric` and set `detail_fetched_at = now()` from
   the same payload (free; means a future ride-detail screen needs no re-fetch).

**Rate limiting.** Strava allows 200 req / 15 min and 2000 / day. The worker paces
itself well under that (target ≤ ~100 / 15 min to leave headroom for interactive
calls and webhooks), sleeping between calls. On HTTP 429 it backs off (honouring
`Retry-After` when present) and resumes. Because the work item is selected purely by
`detail_fetched_at IS NULL`, the worker is **fully resumable** — if the Render
process restarts mid-run, the next invocation picks up the remainder.

**Triggering.** `run_detail_backfill` is chained at the end of a successful
`run_backfill`, and is safe to re-trigger (idempotent). Progress is *derived* from
counts (`activities` with `detail_fetched_at IS NULL` vs. total) — **no new
`sync_state` columns**, so still no migration.

## Derivation logic (`services/segments.py`)

Pure functions, DB client injected as an argument (per `backend/CLAUDE.md`).

**Effort extraction.** Given a detailed activity payload for `athlete_id`, for each
entry in `payload["segment_efforts"]`:

- segment row: `id=effort["segment"]["id"]`, `name`, `distance_m=segment["distance"]`,
  `avg_grade=segment["average_grade"]`.
- effort row: `id=effort["id"]`, `segment_id`, `athlete_id`, `activity_id=payload["id"]`,
  `elapsed_time_s=effort["elapsed_time"]`, `avg_watts=effort.get("average_watts")`,
  `avg_hr=round(effort["average_heartrate"])` if present else `None`,
  `avg_speed_ms = segment["distance"] / elapsed_time_s`,
  `start_date=effort["start_date"]`.

**`is_best` recompute.** For each affected `(athlete_id, segment_id)`: the effort with
the minimum `elapsed_time_s` gets `is_best=true`, all others `false` (ties → the
earliest `start_date` wins, deterministically).

**Status-note primitives** (computed in the list endpoint, formatted client-side):
for each segment, take the athlete's **latest** effort (max `start_date`) and its rank
among all that athlete's efforts on the segment sorted ascending by `elapsed_time_s`:

- `pr = (rank == 1)` — the latest ride set a new personal best.
- `improvement_s` (only when `pr` and ≥2 efforts) = `second_best_time − best_time`
  (a positive number of seconds shaved).
- `latest_rank` = the ordinal (2, 3, …) used to render "{n}th best".

## API surface (FastAPI)

Registered as `include_router(segments.router, prefix="/segments")`. Both reads are
athlete-scoped via the existing `current_user` dependency. All values metric;
formatting/units happen client-side (consistent with the parent spec).

| Endpoint | Purpose |
|---|---|
| `GET /segments?q=&sort=attempts&dir=desc` | Searchable/sortable segment list |
| `GET /segments/{id}` | Segment meta + all of this athlete's efforts |

**`GET /segments`** → `{ segments: SegmentListItem[] }`, one per segment the athlete
has efforts on:

```
SegmentListItem {
  id, name, distance_m, avg_grade,
  best_time_s,            # min elapsed across athlete's efforts
  attempts,               # count of athlete's efforts
  pr: bool,               # latest effort is the PR
  latest_rank: int,       # rank of latest effort (1 = PR)
  improvement_s: int|null # seconds shaved when pr, else null
}
```

- `q` filters by case-insensitive name substring.
- `sort` ∈ {`attempts`} with `dir` ∈ {`asc`,`desc`}; default `attempts`/`desc`
  (most-attempted first). Secondary stable order by `name`.

**`GET /segments/{id}`** → segment meta + the full effort list (athlete-scoped):

```
SegmentDetail {
  id, name, distance_m, avg_grade,
  pr_time_s,              # best effort time
  attempts,
  efforts: SegmentEffort[]   # ALL of this athlete's efforts, newest-first
}
SegmentEffort {
  id, activity_id, activity_name,   # activity_name via PostgREST embed
  start_date, elapsed_time_s,
  avg_watts|null, avg_hr|null, avg_speed_ms, is_best
}
```

Search / sort / pagination of attempts is done **client-side** — one athlete's
efforts on a single segment is a small set, and the prototype does it all in-memory.
This keeps the endpoint a dumb read. Returns 404 if the segment has no efforts for the
caller. `activity_name` comes from a PostgREST embedded select on `activities(name)`.

**DB layer (`db/segments.py`).** Typed `TypedDict` row shapes + functions:
`upsert_segments`, `upsert_segment_efforts`, `list_athlete_segments`
(aggregate/derive list fields), `get_segment_efforts` (one segment, embedded activity
name), `recompute_is_best`. Uses the shared supabase client singleton; reads filtered
by `athlete_id` (defence-in-depth alongside RLS), mirroring `db/activities.py`.

## Frontend (`frontend/`)

Follows `frontend/CLAUDE.md`: pages compose, components render; data via the `api/`
hook layer; `@/` imports; token utilities (no raw hex); `lucide-react` icons;
`<NavLink>`/`<Link>` for navigation; TDD for new logic.

**Routing & nav.**
- Add to the `routes` array in `app/router.tsx`: `/segments` → `SegmentsPage`,
  `/segments/:id` → `SegmentDetailPage` (before the `*` catch-all).
- Add a **Segments** `<NavLink>` to `components/app-shell/Sidebar.tsx` (the design's
  nav already lists Overview / Activities / Trends / Segments / Settings).

**Data layer.**
- `types/segments.ts` — `SegmentListItem`, `SegmentDetail`, `SegmentEffort`.
- `api/segments.ts` — `fetchSegments(params)` + `useSegments()`,
  `fetchSegment(id)` + `useSegment(id)`, via `apiFetch<T>()`.
- `lib/format.ts` — add `fmtClock(seconds)` → `m:ss` / `h:mm:ss` (segment/effort
  times); reuse existing `fmtDistance`, `fmtDate`, etc. Power/HR absent → em-dash
  (existing convention).

**Pages & components (page-local under `pages/segments/components/`).**
- `SegmentsPage.tsx` — search input + `SegmentTable` + pager. Renders the status note
  from primitives: `pr` → green "New PR · −{improvement_s}s"; else muted
  "{latest_rank}th best".
- `SegmentDetailPage.tsx` — `SegmentMetaCards` (PR time, length, avg grade, attempts),
  `SegmentCompare`, `SegmentAttemptsTable`.
  - `SegmentCompare` — Personal Best card vs. Selected attempt card (time, delta pill
    "+M:SS slower" / "Personal best", avg power/speed/HR) + two proportional bars
    (`width = time / max(bestTime, selTime)`). The selected attempt is **local
    component state**; clicking an attempt row sets it. Defaults to the most recent
    non-best effort (falls back to the best if only one effort).
  - `SegmentAttemptsTable` — columns DATE (+ PR/SELECTED tag), ACTIVITY, TIME, POWER,
    SPEED, HR; client-side search (activity name or date), sortable headers, pager.

**Reuse (the "use the React components" instruction).** `SegmentsPage` and
`SegmentDetailPage` are the **second consumer** of the activities-table building
blocks, so per `frontend/CLAUDE.md` ("promote to `src/components/` when a second
consumer appears") promote and reuse rather than duplicate:
- the pager UI (`pages/activities/components/ActivityPager.tsx`) → generalize into
  `src/components/Pager.tsx` driven by the existing `lib/pager.ts`;
- the search-input control from `ActivityFilterBar` → a small shared `SearchInput`.
Keep the existing Activities pages working against the promoted components (their
tests must stay green).

**Styling.** Map the design's CSS vars to existing tokens (`text-strava`/`bg-strava`
for accent, `text-ride-green`, `bg-surface-card`, `border-line`, etc.). Delta pills
need a "good/green" and "bad/red" pair — if no red token exists, add a `--color-…`
var to **both** `:root` and `.dark` in `index.css` and map it under `@theme inline`
(one-file change), never raw hex in components.

## Testing

**Backend (pytest, patch at the service boundary; respx for Strava).**
- Effort extraction from a sample detailed payload (fields, nullable power/HR,
  computed `avg_speed_ms`).
- `is_best` recompute (new faster effort flips the flag; tie-break by earliest date).
- Webhook path extracts + upserts efforts from the already-fetched detail.
- `run_detail_backfill`: selects only `detail_fetched_at IS NULL`, paces calls,
  backs off on a stubbed 429, resumes; sets `detail_fetched_at`.
- `GET /segments`: `q` filter, sort/dir, derived `best_time_s`/`attempts`/`pr`/
  `latest_rank`/`improvement_s`.
- `GET /segments/{id}`: meta, efforts with embedded `activity_name`, 404 when none.
- `test_architecture.py` continues to pass (routers→services→db layering).

**Frontend (Vitest + RTL).**
- `fmtClock` unit tests (m:ss and h:mm:ss boundaries).
- `SegmentsPage`: list render, search filter, status-note rendering (PR vs nth-best),
  pager.
- `SegmentDetailPage`: meta cards; compare math (delta text, bar widths); selecting an
  attempt updates the compare; attempts search/sort/paginate; em-dash for missing
  power/HR.
- `api/segments` fetch/hook tests (mock-resolved first, then `apiFetch`).
- Promoted `Pager`/`SearchInput`: existing Activities page tests stay green.

## Updates to the parent spec (`2026-06-20-peakstats-design.md`)

To make changes here, also update the parent so it stays the source of truth:

1. **Segments derivation** — change "detailed fetches … are **lazy** (performed on
   ride-detail open)" and "Segments are derived … from those" to reflect the actual
   model: efforts are extracted from the webhook's already-fetched detail for new
   rides, and from a **background detail-backfill worker** (resumable, rate-limited)
   for history; the worker also fills `splits_metric`/`detail_fetched_at`.
2. **`/segments/{id}`** — clarify it returns the athlete's full effort list and that
   attempt search/sort/pagination is client-side.
3. **Overview** — note the Overview redesign (heatmap, donut, highlights, segment-PR
   panel) is a separate, not-yet-scheduled spec; the current Overview does not return
   top segments.

## Build increments (vertical slices, each verified before the next)

Per the parent spec's delivery principle — one increment at a time, end to end:

1. **Effort derivation + webhook extract** (backend) — `services/segments.py`
   extraction + `is_best` recompute, `db/segments.py` upserts; wire into
   `webhooks.process_event`. Verified by tests (new rides populate efforts).
2. **Detail-backfill worker** (backend) — `run_detail_backfill`, throttled/resumable,
   chained after `run_backfill`. Verified by tests + a live backfill populating
   historical efforts.
3. **Segments list** — `GET /segments` + `SegmentsPage` (search, sort, pager, status
   notes). Full vertical slice, demoable.
4. **Segment detail** — `GET /segments/{id}` + `SegmentDetailPage` (meta, compare,
   attempts table). Full vertical slice, demoable.

## Open questions / risks

- **Long-running worker on Render.** A multi-minute background thread can be killed by
  a deploy/restart. Mitigated by the resumable design (re-trigger picks up remaining);
  if it proves unreliable, revisit with a durable queue or a Render cron job.
- **Effort payload completeness.** Power/HR are frequently absent on efforts; the model
  and UI already treat them as nullable (em-dash), matching the prototype.
- **`average_grade` sign.** Strava reports segment grade; we store it as-is and render
  "{grade}% avg" exactly as the design does.
