# Overview redesign — Phase 3: time in power/HR zones + top avg power

**Date:** 2026-06-23
**Branch:** feature branch off `main` (merge when green).
**Design source:** `Peakstats Overview.dc.html` (Claude Design project `646622a9…`),
rendered reference at `docs/screenshots/overview.png`.
**Predecessors:** `2026-06-22-overview-redesign-phase-1-design.md`,
`2026-06-23-overview-redesign-phase-2-design.md` (both shipped, on `main`).

## Problem

Phases 1–2 shipped the redesigned Overview frame: period selector → hero KPI + trend,
records summary, recent rides, ride-types donut, activity heatmap, and weekly-goal ring.
Three designed elements remain (the final phase):

- **Time in power zones** — a panel of 7 Coggan power zones (Z1…Z7), each a horizontal
  percentage bar showing the share of the selected period's ride time spent in that zone.
- **Time in HR zones** — the same, for 5 heart-rate zones (Z1…Z5).
- **Top avg power** — a stat in the "Weekly Highlights" card (alongside Top avg speed,
  PRs, Longest ride, Most elevation), showing the highest single-ride average power in
  the selected period.

All three are **scoped to the Week/Month/Year selector**, matching the design's "THIS WEEK"
captions, exactly as the hero/summary/trend/donut already are.

## Phasing recap (whole redesign)

- **Phase 1 (shipped):** frame + period selector + hero + summary + recent rides + donut.
- **Phase 2 (shipped):** activity heatmap + weekly-goal ring (`weekly_goal_m` setting).
- **Phase 3 (this spec):** time in power zones + time in HR zones + top-avg-power stat.

The "Bikes & gear / component wear" panel and the separate Trends view remain **out of
scope entirely** (cut for v1).

## Decisions (locked during brainstorming)

1. **Build all of Phase 3 in one go** — top-avg-power stat *and* both zone panels,
   including the streams-backfill pipeline and compact per-activity distribution store.
2. **Top avg power = `max(average_watts)` over the period's rides** — parallels the
   existing `top_speed_ms = max(avg_speed_ms)`. Sourced from Strava's summary
   `average_watts`, which the sync already receives but does not store. **No streams
   needed for this stat.**
3. **Zone panels need per-ride streams**, which are currently cached only for rides whose
   detail page has been opened (`activity_streams` is lazily populated). To make the
   panels accurate, we **precompute a compact per-activity distribution once** and
   aggregate that — we do **not** read full streams per request, and we do **not** store
   full stream blobs for un-viewed rides (free-tier storage protection).
4. **Distributions are FTP/HR-max-independent histograms** (absolute wattage / bpm bins),
   not pre-bucketed zone seconds. Zone boundaries are applied at *query* time from the
   athlete's current `ftp_w` / `hr_max`. Consequence: changing FTP/Max-HR in Settings
   re-buckets the panels instantly with **no re-backfill**.
5. **Reuse the existing zone definitions and labels** from `analysis.py`
   (`power_zones`, `hr_zones`) and the existing `ZoneBucket` / `ZonesBlock` models —
   one source of truth shared with the activity-detail page. The Overview mock's slightly
   different wording ("Recovery"/"Sprint"/"VO₂ Max") is treated as non-binding.
6. **Empty/unset states mirror the activity-detail page.** FTP/Max-HR unset → an inline
   "Set your FTP in Settings" prompt (`ZonesBlock.unset = True`). Configured but the period
   has no power/HR data → a "No power data for this period" message
   (`unset = False`, zeroed buckets).
7. **Bonus: detail-page perf.** Precomputing `avg_power_w` / `np_w` / `work_kj` per
   activity lets `get_detail` read them instead of recomputing from the full stream array
   on every view (the deferred `peakstats-activity-detail-perf` item). The detail map/power
   charts still lazily fetch the full stream on first view, as today.

## Data model

### New table `activity_metrics` (migration `0008`)

One row per activity, keyed by `activity_id`. Holds the compact, FTP-independent
distribution plus precomputed scalars.

```sql
create table activity_metrics (
  activity_id  bigint primary key references activities(id) on delete cascade,
  athlete_id   bigint not null,
  avg_power_w  double precision,      -- Δt-weighted mean power, null if no power
  np_w         double precision,      -- normalized power, null if no power
  work_kj      double precision,      -- total work, null if no power
  power_hist   jsonb,                 -- seconds per absolute wattage bin (see below)
  hr_hist      jsonb,                 -- seconds per absolute bpm bin
  has_power    boolean not null default false,
  has_hr       boolean not null default false,
  computed_at  timestamptz not null default now()
);
create index activity_metrics_athlete_idx on activity_metrics(athlete_id);
```

RLS to match the existing tables (service-role writes; athlete-scoped reads), following
whatever `0006_activity_streams.sql` established.

**Histogram encoding** (both `*_hist`): a fixed-width seconds array with documented bin
geometry. Constants in `analysis.py`:

- Power: `POWER_BIN_W = 10`, `POWER_BINS = 150` → covers `[0, 1500) W`; samples ≥ 1500
  fold into the last (overflow) bin. `power_hist = [secs_bin0, …, secs_bin149]`.
- HR: `HR_BIN_BPM = 5`, `HR_BINS = 44` → covers `[0, 220) bpm`; overflow into the last bin.

Seconds are Δt-weighted (reusing `analysis.deltas`), so they match `time_in_zones`. A bin's
zone membership at query time is decided by its **midpoint** wattage/bpm
(`bin_index * bin_w + bin_w/2`); with 10 W / 5 bpm bins the boundary quantization error is
negligible. Storage per row ≈ a few hundred ints (~1 KB jsonb); ~877 rows ≈ <1 MB total.

### New column `avg_watts` on `activities` (same migration `0008`)

```sql
alter table activities add column avg_watts double precision;
```

Nullable (rides without a power meter have none). The `ActivityRow` TypedDict gains
`avg_watts: float | None`.

## Backend

### Analysis (`app/services/analysis.py`) — pure math, unit-tested

Add (no I/O):

- `POWER_BIN_W`, `POWER_BINS`, `HR_BIN_BPM`, `HR_BINS` constants.
- `histogram(time, series, bin_w, n_bins) -> list[float]` — Δt-weighted seconds per
  absolute bin, overflow into the last bin, skipping `None` samples. Empty/None series → a
  zero array (length `n_bins`).
- `compute_metrics(data: dict) -> dict` — from a flat stream dict (`{time, watts, heartrate, …}`)
  produce `{avg_power_w, np_w, work_kj, power_hist, hr_hist, has_power, has_hr}` using the
  existing `weighted_mean` / `normalized_power` / `total_work_kj` / `histogram`. `has_power`/
  `has_hr` are true when the respective series exists and has ≥1 non-None sample.
- `zone_seconds_from_histogram(hist, bin_w, zones) -> list[float]` — sum each bin's seconds
  into the zone whose `[lo, hi)` contains the bin midpoint. Returns per-zone seconds aligned
  to `zones`.
- `buckets_from_zone_seconds(secs, zones) -> list[dict]` — produce the same
  `{z, name, range, seconds, pct}` dicts `time_in_zones` already emits, so it feeds the
  existing `ZoneBucket` model unchanged. (Refactor: `time_in_zones` can be expressed as
  `buckets_from_zone_seconds` over its own per-zone sums to avoid duplication.)

### DB (`app/db/metrics.py` — new module)

`MetricsRow` TypedDict mirroring the table. Functions:

- `get_metrics(client, activity_id) -> MetricsRow | None`
- `upsert_metrics(client, row: MetricsRow) -> None` (`on_conflict="activity_id"`)
- `list_metrics_for_activities(client, athlete_id, activity_ids: list[int]) -> list[MetricsRow]`
  — `.in_("activity_id", ids)`; returns `[]` for an empty id list without a query.
- `list_activity_ids_needing_metrics(client, athlete_id) -> list[int]` — activity ids with
  no `activity_metrics` row, computed by an **id-diff in the db layer**: fetch the athlete's
  activity ids and their existing metrics ids, return the difference (ascending). ~877 ids is
  trivial; no RPC and no new column on `activities`. Resumable: the metrics row's existence is
  the marker, so re-running the backfill picks up only what's left. (Migration `0008` stays
  table + column + RLS only.)

### Sync / backfill (`app/services/sync.py`, `app/services/activities.py`)

- **`_to_activity_row`** maps `"avg_watts": summary.get("average_watts")`. New activities from
  backfill/refresh/webhook get it automatically.
- **`avg_watts` history backfill** — a one-off: re-list all activities
  (`list_activities` paged, `after=None`) and `upsert_activities`. ~5 API calls for 877 rides;
  no detail/streams. Expose as a small runnable path (a `run_avg_watts_backfill(supabase,
  settings, athlete_id)` service fn invoked once post-deploy, the same way the Phase-related
  one-off backfills have been run). Idempotent (upsert).
- **`ensure_streams`** — after it has the stream `data` (cached or freshly fetched), upsert
  `activity_metrics` via `analysis.compute_metrics(data)`. Keeps viewed/new rides' metrics
  current and self-heals.
- **`run_streams_backfill(supabase, settings, athlete_id)`** — new resumable, paced pass:
  - Load `list_activity_ids_needing_metrics` once (one cheap query), then iterate.
  - For each: fetch streams from Strava (`STREAM_KEYS`), `compute_metrics`, `upsert_metrics`.
    **Do not** store the full blob (storage protection) — metrics only.
  - Pace `DETAIL_PAUSE_S` (~12/min) with the existing 429 backoff (`_fetch_*_with_backoff`
    pattern); resumable (only un-metriced activities selected); one transient error skips the
    activity, never aborts the batch (mirror `run_detail_backfill`).
  - Chained after `run_detail_backfill` on `POST /sync/start` for new athletes; run once
    historically for the existing 877-activity dataset.

### Models (`app/models/activities.py`)

- `OverviewSummary` gains `top_avg_power_w: float | None`.
- `OverviewResponse` gains `power_zones: ZonesBlock` and `hr_zones: ZonesBlock` (reuse the
  existing `ZonesBlock` / `ZoneBucket` — already imported by the service).

### Overview service (`app/services/activities.py` → `get_overview`)

- `top_avg_power_w` in `_summary`: `max((r["avg_watts"] for r in rows if r.get("avg_watts")),
  default=None)`.
- New `_period_zones(supabase, athlete_id, this_rows, settings)`:
  - Read `ftp = settings.get("ftp_w")`, `hr_max = settings.get("hr_max")`.
  - Power: `ftp` unset → `ZonesBlock(unset=True)`. Else fetch
    `list_metrics_for_activities` for `[r["id"] for r in this_rows]`, element-wise sum
    `power_hist` (skip null/short arrays), `zone_seconds_from_histogram(...,
    analysis.power_zones(ftp))`, `buckets_from_zone_seconds(...)`, return
    `ZonesBlock(unset=False, avg=None, buckets=...)`. All-zero buckets are a valid "no data"
    result (frontend renders the message).
  - HR: same with `hr_max` / `analysis.hr_zones(hr_max)`.
  - `get_overview` already loads the athlete settings path for nothing else — fetch
    `athletes_db.get_athlete(...)` once here (the detail service already does this) and pass
    `settings` in.
- Wire both blocks + `top_avg_power_w` into the `OverviewResponse`.

### Detail service perf (`get_detail`) — bonus, low-risk

When an `activity_metrics` row exists, read `avg_power_w` / `np_w` / `work_kj` and derive the
power/HR `ZonesBlock`s from the stored histograms (via the new analysis helpers) instead of
recomputing from the full stream array. Fall back to the current stream-based computation when
no metrics row exists yet (e.g. an activity not yet processed). Keep the response shape
identical. This is additive; if it risks scope creep during implementation it may be deferred
to a follow-up, but the metrics store makes it a small change.

### Router (`app/routers/activities.py`)

No change — `GET /activities/overview` already returns `OverviewResponse`; the new fields flow
through. (`run_streams_backfill` is chained in the existing `POST /sync/start` handler.)

## Frontend

### Types (`frontend/src/types/overview.ts`)

DTO additions:

```typescript
export interface ZoneBucketDTO {
  z: string;        // "Z1"
  name: string;     // "Endurance"
  range: string;    // "137–187 W"
  seconds: number;
  pct: number;      // 0..100
}

export interface ZonesBlockDTO {
  unset: boolean;
  avg: number | null;
  buckets: ZoneBucketDTO[];
}
```

Extend `OverviewDTO` with `power_zones: ZonesBlockDTO`, `hr_zones: ZonesBlockDTO`, and add
`top_avg_power_w: number | null` to `OverviewSummaryDTO`.

Display additions:

```typescript
export interface ZoneRow {
  z: string;
  name: string;
  range: string;
  pct: string;      // "33%"
  fraction: number; // 0..1 (bar width)
  color: string;    // zone color literal
}

export interface ZonesView {
  unset: boolean;    // FTP/Max-HR not configured
  hasData: boolean;  // configured AND some seconds > 0
  rows: ZoneRow[];
}
```

Extend `SummaryView` with `topAvgPower: string` (`"287 W"` | `"—"`) and `DashboardOverview`
with `powerZones: ZonesView` and `hrZones: ZonesView`.

### Mapper (`frontend/src/api/overview.ts`)

- `buildSummaryView` adds `topAvgPower = dto.top_avg_power_w != null ?
  \`${Math.round(dto.top_avg_power_w)} W\` : "—"`. (Power is not unit-converted — watts are
  watts in both unit systems.)
- `buildZonesView(block: ZonesBlockDTO, palette): ZonesView`:
  - `unset = block.unset`.
  - `total = sum(buckets.seconds)`, `hasData = !unset && total > 0`.
  - `rows`: per bucket, `pct = \`${Math.round(b.pct)}%\``, `fraction = b.pct / 100`,
    `color = palette[index]`.
- Two palettes (7 power colors, 5 HR colors) as JS literal arrays — the documented
  chart-color exception (Recharts/SVG need literals). Orange-forward ramp mirroring the mock.

### Components (`pages/app-home/components/`)

- **`ZonePanel.tsx`** — `<ZonePanel title={string} caption={string} zones={ZonesView} />`.
  Card chrome + header (`title` + period `caption`, e.g. "THIS WEEK"). Body:
  - `zones.unset` → inline prompt: "Set your FTP in Settings" / "Set your Max HR in Settings"
    (pass the prompt text in, or branch on title). A `<Link to="/settings">` for the
    Settings reference.
  - `!unset && !hasData` → "No power data for this period" / "No heart-rate data…".
  - else → one row per `ZoneRow`: `Z# · name`, a track+fill bar (`fraction`), `pct` right-aligned.
  Presentational; colors from the view. Used for both panels.
- **`SummaryCard.tsx`** — add the "TOP AVG POWER" row showing `summary.topAvgPower`, placed
  per the mock (after Top avg speed).

### Page (`frontend/src/pages/app-home/AppHome.tsx`)

Per `overview.png`, the existing `SummaryCard` ("Weekly Highlights") becomes the **first cell
of a three-up row**, with the two zone panels beside it, sitting above the heatmap/goal row.
This **replaces** the current full-width `SummaryCard` placement with a row
`grid-cols-[1.1fr_1fr_1fr] gap-4 mb-4 max-[1024px]:grid-cols-1`:

```
HeroPanel
<grid 1.1fr | 1fr | 1fr: SummaryCard | ZonePanel(power) | ZonePanel(HR)>   ← Phase 3 row
<grid 2.7fr | 1fr:  ActivityHeatmap | WeeklyGoalRing>
<grid 1.55fr | 1fr: RecentRidesPanel | RideTypesDonut>
```

Pass `overview.powerZones` / `overview.hrZones` and the period caption to the panels. Extend
`SkeletonPanels` with a matching block.

The period caption ("THIS WEEK" / "THIS MONTH" / "THIS YEAR") already exists for the hero;
reuse the same derivation for the zone panel captions.

### Tokens

**No `index.css` change.** Zone bar colors live as JS literal arrays inside `ZonePanel.tsx`
(or the mapper) under the documented chart-color exception, exactly as `TrendChart`/
`WeekChart`/`ActivityHeatmap` already do. Text/surfaces use existing token utilities.

## Testing

TDD per `backend/CLAUDE.md` and `frontend/CLAUDE.md`. Gates: backend
`pytest && ruff check . && mypy`; frontend `npm test && npm run lint && npm run build`.

- **Backend (`tests/services/test_analysis.py`):**
  - `histogram` — Δt-weighted seconds land in the right bins; overflow folds into the last
    bin; `None` samples skipped; empty/None series → zero array of correct length.
  - `zone_seconds_from_histogram` — bin midpoints map to the correct zone; boundary bins;
    empty histogram → all zeros.
  - `compute_metrics` — scalars match the existing helpers; `has_power`/`has_hr` flags;
    no-power / no-hr inputs.
- **Backend (`tests/services/test_activities.py`):**
  - `get_overview` zones — sums histograms across the period's rows; selector-scoped
    (week/month/year cover different rows); `unset=True` when FTP/Max-HR missing; zeroed
    buckets when configured-but-no-data; correct pct.
  - `top_avg_power_w` — max over the period's `avg_watts`; `None` when no ride has power.
  - `_to_activity_row` maps `avg_watts` from `average_watts`.
  - `run_streams_backfill` — processes only un-metriced activities, paced, resumable, one
    failure skips not aborts (mocked Strava + db).
  - Existing Phase 1–2 tests stay green.
- **Frontend:**
  - Mapper (`api/overview.test.ts`) — `topAvgPower` formatting (`"287 W"`, `"—"` when null);
    `buildZonesView` (unset, hasData false on all-zero, pct/fraction/color, row count).
  - `ZonePanel` render — rows for data; unset prompt; no-data message.
  - `SummaryCard` — Top avg power row renders.
  - `AppHome.test.tsx` — the new zone row renders within the loaded dashboard.

## Migration & rollout

1. Apply migration `0008` (table + `avg_watts` column + RLS + optional RPC) to Supabase.
2. Deploy backend + frontend.
3. Run the one-off `avg_watts` re-list backfill (top-avg-power lights up immediately).
4. Run the one-off `run_streams_backfill` for the existing dataset (paced; zone panels fill
   in as it progresses — partial data renders correctly, it just undercounts until complete).

## Out of scope (Phase 3)

- Trends view; bikes & gear / component wear (cut for v1).
- Storing full stream blobs for un-viewed rides.
- Persisting the period selector or any Settings control beyond what already exists.
- A manual "rebuild metrics" UI control (the backfill is run operationally).
