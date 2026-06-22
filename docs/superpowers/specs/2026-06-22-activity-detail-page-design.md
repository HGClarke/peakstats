# Activity Detail Page — Claude Design Implementation

**Date:** 2026-06-22
**Status:** Design — approved through architecture; pending spec review.

## Context

Peakstats has no `/activities/:id` page yet — routes stop at `/segments/:id`, and rows in the
Activities table are not clickable. This effort builds the **ride detail page** from an imported
Claude Design (`Peakstats Activity.dc.html`), wiring it to **real Strava data**: cached activity
streams (power / heart-rate / elevation), FTP/HR-based training zones, and categorized climbs.

A companion spec — [`2026-06-22-activity-detail-analytics-design.md`](2026-06-22-activity-detail-analytics-design.md)
on the stale `feat/activity-detail-analytics` branch — designed the data foundation but was never
implemented, and that branch predates the merged Settings phase. This spec supersedes it, reuses
its still-valid backend decisions, and is built fresh on `main`.

## Scope

**Sections built** (from the imported design):

1. **Hero** — route over a theme-matched map + identity (name, type badge, date, location) + a
   6-tile primary-stats grid.
2. **Power chart** — watts over distance, with average + Normalized-Power reference lines.
3. **Power zones + HR zones** — two side-by-side time-in-zone panels.
4. **Elevation profile** — altitude over distance.
5. **Climbs on this ride** — categorized climbs table with VAM.

**Dropped from the design** (per the user): the **Training load & intensity** feature panel,
**Gear used**, **Cadence & dynamics**, and **Laps**. The mock's topbar **Export / Edit** buttons
are also dropped (no backing feature).

## Locked decisions

Settled during brainstorming; not re-litigated below.

- **Map:** the hero renders the route **over a real map** using **`react-leaflet`** with
  **theme-matched CARTO basemaps** — Positron (light) / Dark Matter (dark), swapped via the
  existing `SettingsProvider` theme. **No API key required** (attribution required: © OpenStreetMap,
  © CARTO). The route is the decoded `summary_polyline` we already store, drawn as a Leaflet
  `Polyline` in Strava orange with green-start / orange-end markers, auto-fit to bounds; the map is
  non-interactive (drag/scroll disabled) to match the mock's static feel. The gradient caption
  (type badge, date, name, location) layers on top.
- **Swappable map seam (for a later Mapbox switch):** keep three things isolated so the provider
  can change cheaply — (a) polyline decode + bbox normalization in a pure, unit-tested
  `lib/polyline.ts`; (b) tile source in a single `lib/map-tiles.ts` config (`{ url, attribution }`
  per theme); (c) **`RouteHero` as the only map-aware component.** Then: swapping CARTO→Mapbox
  *raster* tiles is a one-constant edit (+ a `VITE_MAPBOX_TOKEN` via `lib/config.ts`); switching to
  Mapbox **GL vector** rendering is a rewrite of `RouteHero` only. No speculative provider
  abstraction beyond these seams (YAGNI).
- **Zone inputs:** the athlete's **FTP** and **max HR** are entered manually in **Settings** and
  stored in the existing `athletes.settings` JSONB; peakstats computes zones locally. Chosen over
  pulling from Strava `/athlete/zones`, which would require adding `profile:read_all` to the OAuth
  scope and forcing every user to re-authorize. (Current scope is `read,activity:read_all`.)
- **Streams:** stored raw, fetched **lazily on first detail view** (`resolution=high`), cached in a
  new `activity_streams` JSONB table, and **computed-on-read** for derived panels. `activity:read_all`
  already covers the streams endpoint — no scope change. (Carried from the analytics spec.)
- **Streams JSONB shape:** object-of-arrays `{"watts":[…],"altitude":[…],…}`, never
  array-of-objects, never one-row-per-sample. Consistent with the existing `splits_metric`/`settings`
  JSONB pattern.
- **Climbs reuse existing data:** Strava's `climb_category` and elevation live on the nested
  `segment` of each `segment_effort`, which the app **already fetches** during its detail backfill.
  Cost is two new `segments` columns + a one-time re-backfill — no new Strava calls.
- **Charts use Recharts** (repo convention — `WeekChart` already does), not the mock's hand-rolled
  SVG.

## Backend architecture

Respects the existing `routers → services → db` layering (services hold business logic and import no
`fastapi`; HTTP exceptions live only in routers), enforced by `test_architecture.py`.

### Streams foundation
- **`strava.py`** gains `get_activity_streams(access_token, activity_id, keys, resolution="high")`,
  calling `/activities/{id}/streams?keys=…&key_by_type=true&resolution=high` and normalizing
  Strava's `{"watts":{"data":[…]}}` into the flat object-of-arrays `{"watts":[…]}`. Reuses the
  existing 429-backoff helper used by detail fetches.
- **Migration `0006`** — `activity_streams` table (see Data model).
- **`db/streams.py`** *(new)* — `get_streams(client, activity_id)`, `upsert_streams(client, row)`.
- **`services/activities.py`** — `ensure_streams(supabase, athlete_id, activity_id)`: DB hit; on miss,
  fetch via a valid token (`get_valid_access_token`), persist, return. Stores a **sentinel empty row**
  (`data={}`, `point_count=0`) for activities with no streams so we never refetch.

### Analysis (pure, no I/O — the heavily unit-tested core)
New **`services/analysis.py`**:
- `normalized_power(time, watts) -> float | None` — 30 s rolling avg → 4th power → mean → 4th root;
  `None` if `watts` absent.
- `power_zones(ftp) -> list[ZoneDef]` — Coggan 7 (table below).
- `hr_zones(hr_max) -> list[ZoneDef]` — 5-zone %max (table below).
- `time_in_zones(time, series, zones) -> list[ZoneBucket]` — **Δt-weighted** by the `time` stream so
  smart-recording (non-1 Hz) rides are correct; null samples skipped, power zeros (coasting) → Z1.
- `compute_climbs(rows) -> list[Climb]` — VAM + sort hardest category first.

### Endpoints
| Method | Path | Returns |
|---|---|---|
| GET | `/activities/{id}` | `ActivityDetailResponse` — header + primary stats + `zones` + `climbs` |
| GET | `/activities/{id}/streams` | `ActivityStreamsResponse` — `{distance, altitude, watts, heartrate, velocity_smooth, time}` arrays |
| PATCH | `/athlete/settings` | extended to accept `ftp_w` + `hr_max` |

`services/activities.get_detail(...)` orchestrates: load the activity row → `ensure_streams` →
compute header power stats (avg W, NP, work kJ) + zones from streams + athlete settings → compute
climbs from joined efforts → assemble. `ensure_streams` is the only place that performs the lazy
Strava fetch. Both GETs trigger it (cached after the first). A not-found / not-owned activity raises
a domain error → router returns **404**.

**Header / primary stats** (6 tiles): DISTANCE, MOVING TIME, ELEV GAIN, AVG POWER, AVG SPEED, WORK
(kJ). Sourced from the `activities` row (`distance_m`, `moving_time_s`, `elev_gain_m`,
`avg_speed_ms`) plus stream-derived power figures. `location` is best-effort from Strava's
`location_*` fields (frequently null → omitted). When `watts` is absent, AVG POWER / WORK / NP are
returned `null` and the power-zones block is flagged `unset`.

### Settings (FTP / max HR)
- **`models/athlete.py`** — `SettingsUpdate` gains `ftp_w: int | None` and `hr_max: int | None`
  (the model already uses `extra="forbid"` + an "at least one field" validator; extend both).
- The existing `services/athletes.update_settings` already merges via
  `model_dump(exclude_none=True)` into the settings JSONB — no service/db change needed beyond the
  model.

### Climbs
- **Migration `0007`** — `segments` gains `climb_category smallint not null default 0` and
  `elev_gain_m double precision not null default 0`.
- **`services/segments.extract_efforts`** captures `seg.get("climb_category", 0)` and elevation gain
  (`elevation_high - elevation_low`, falling back to `total_elevation_gain` when present) into the
  `SegmentRow`; `SegmentRow` TypedDict + `upsert_segments` updated.
- **`db/activities.py`** — `list_activity_climbs(client, athlete_id, activity_id)`: efforts joined to
  segments where `climb_category > 0`.
- **Backfill:** historical segments keep the defaults until a detail re-backfill re-stores their
  efforts via the existing `list_activities_needing_detail` mechanism. A one-time paced re-run
  populates the new fields (a follow-up op — memory notes the detail-backfill pacing caveat).

## Data model

**Migration `0006` (streams):**
```sql
create table activity_streams (
  activity_id bigint primary key references activities(id) on delete cascade,
  athlete_id  bigint not null references athletes(id) on delete cascade,
  data        jsonb  not null,   -- object-of-arrays: {"time":[…],"distance":[…],
                                 --  "altitude":[…],"heartrate":[…],"watts":[…],
                                 --  "velocity_smooth":[…]}
  resolution  text   not null,
  point_count integer not null,
  fetched_at  timestamptz not null default now()
);
alter table activity_streams enable row level security;
create policy activity_streams_self_read on activity_streams
  for select using (athlete_id = (auth.jwt() ->> 'athlete_id')::bigint);
```
Writes use the service-role key (RLS bypassed), matching every other table; the read policy is
defense-in-depth (the SPA reads streams through FastAPI, not Supabase directly).

**Migration `0007` (climbs):**
```sql
alter table segments add column climb_category smallint        not null default 0;
alter table segments add column elev_gain_m    double precision not null default 0;
```

**Athlete settings:** `ftp_w` (int watts) and `hr_max` (int bpm) added as keys in the existing
`athletes.settings` JSONB — no DDL.

## Metric definitions

**Power zones — Coggan 7, % of FTP:**

| Zone | Name | Range |
|---|---|---|
| Z1 | Active Rec. | < 55% |
| Z2 | Endurance | 55–75% |
| Z3 | Tempo | 75–90% |
| Z4 | Threshold | 90–105% |
| Z5 | VO₂ Max | 105–120% |
| Z6 | Anaerobic | 120–150% |
| Z7 | Neuromuscular | > 150% |

**HR zones — 5-zone, % of max HR.** Names: Recovery / Endurance / Tempo / Threshold / Maximum.
Boundaries are a single tunable constant, default **[68, 78, 88, 95]%** (Z1 <68, Z2 68–78, Z3 78–88,
Z4 88–95, Z5 >95).

**Time-in-zone** — weighted by the `time` stream's per-sample Δt, not sample count. The "AVG BPM"
figure is the Δt-weighted mean of `heartrate`.

**Normalized Power** — 30 s rolling average of `watts` → 4th power → mean → 4th root.

**Work (kJ)** — Δt-weighted sum of `watts` over the ride, ÷ 1000.

**Climbs** — efforts whose segment has `climb_category > 0`. Per row: category badge
(1→Cat 4 … 5→HC), name, length (`segment.distance_m`), avg grade (`segment.avg_grade`), elev gain
(`segment.elev_gain_m`), time (`effort.elapsed_time_s`), and **VAM = elev_gain_m / (elapsed_s / 3600)**
m/h. Sorted hardest category first.

## Frontend architecture

Follows `frontend/CLAUDE.md`: pages compose, components render; data lives in the `api/` layer and is
fed to presentational components via hooks; `@/` imports; **token utilities only — no raw hex**.

### Data layer
- **`types/activity-detail.ts`** — `ActivityDetailDTO`, `PrimaryStatDTO`, `ZoneBucketDTO`,
  `PowerZonesDTO` / `HrZonesDTO` (each with an `unset` flag), `ClimbDTO`, `ActivityStreamsDTO`.
- **`api/activity-detail.ts`** — `fetchActivityDetail(id)`, `fetchActivityStreams(id)` via
  `apiFetch<T>`, exposed as `useActivityDetail(id)` / `useActivityStreams(id)` TanStack Query hooks.
  **All formatting/derivation (unit conversion, labels, downsampling, chart point shaping) lives
  here**, so swapping internals never touches components.

### Page + components
- **`pages/activity-detail/ActivityDetailPage.tsx`** — composition only; reads `useParams` id,
  calls both hooks, lays out panels, renders loading skeletons + a not-found state.
- **`pages/activity-detail/components/`**:
  - `RouteHero` — Leaflet map (theme basemap + route overlay + caption). The **only** map-aware
    component.
  - `PrimaryStats` — the 6-tile grid.
  - `PowerChart` — Recharts area + gradient + avg/NP `ReferenceLine`s (follows `WeekChart`'s pattern:
    color literals passed as props, mono custom ticks, `isDark` for theme-variant strokes).
  - `ZonesPanel` — reused for both power and HR (stacked bar + per-zone rows); renders an
    "set your FTP / max HR" prompt linking to `/settings` when `unset`.
  - `ElevationChart` — Recharts area over distance.
  - `ClimbsPanel` — climbs table (category badge, length, grade, gain, VAM, time).
- **`lib/polyline.ts`** — pure `decodePolyline(encoded) -> [lat,lng][]` + bbox normalization;
  unit-tested; renderer-agnostic.
- **`lib/map-tiles.ts`** — `{ light, dark }` → `{ url, attribution }`.

### Routing + entry
- **`app/router.tsx`** — add `{ path: "/activities/:id", element: <ActivityDetailPage /> }` before the
  `*` catch-all.
- **`ActivityTable`** rows become `<Link to={`/activities/${r.id}`}>` (react-router `Link`, never raw
  `<a>`; the existing `ChevronRight` already signals navigability). Keep the page test green by
  asserting the link target.

### Theming (the key requirement: identical colors in light + dark)
The repo's existing tokens in `index.css` already cover the design's palette (`--panel2`, `--good`/
`--bad` + soft, `--track`, `--chartgrid`, `--overlay`, `--border-strong`, `--text-hi`, `--muted2/5`,
`--strava` + soft) with matching hex values per theme. The **only new tokens** are the **zone / grade
/ climb-category colors**, which need explicit light + dark variants (the mock already defines both
palettes in its `gradeColor`/`catColor`/zone arrays):
- Power zones Z1–Z7, HR zones Z1–Z5, grade bands (descent/green/yellow/orange/red), climb-category
  badges (Cat4–HC). Add each to **both `:root` and `.dark`** and map under `@theme inline`
  (`--color-zone-*`, `--color-grade-*`, `--color-cat-*`). Components reference the utility; one class
  is correct in both themes. Chart stroke/fill literals (Recharts needs them) are passed from the
  api/component layer keyed on `isDark`, mirroring `WeekChart`.

### Units
Distance / elevation / speed / VAM formatted via the existing `lib/units.ts` + `lib/format.ts`
(`fmtDistance`, `fmtElevation`, `fmtSpeed`, `fmtClock`, `fmtDuration`), reading `units` from
`useSettings()`. Conversion happens in the api layer; components receive display strings.

## Increments (each independently mergeable + browser-verifiable)

Per the project's one-feature-at-a-time delivery principle.

1. **Streams foundation** — migration `0006`; `strava.get_activity_streams`; `db/streams.py`;
   `ensure_streams`; `GET /activities/{id}/streams`.
   *Verify:* first load fetches + persists; second served from DB; payload has requested channels.
2. **Hero + page shell** — `GET /activities/{id}` (header + primary stats, power figures from
   streams); `types`/`api`/hooks; route; clickable rows; `lib/polyline.ts` + `lib/map-tiles.ts`;
   `RouteHero` + `PrimaryStats`.
   *Verify:* click a ride → map + route + stat tiles render in both themes.
3. **Charts** — `PowerChart` + `ElevationChart` consuming `useActivityStreams` (downsampled).
   *Verify:* charts render from real streams; avg/NP lines correct; theme-correct.
4. **Zones + Settings** — `analysis.power_zones/hr_zones/time_in_zones`; `SettingsUpdate` gains
   `ftp_w`/`hr_max`; Settings form inputs; detail response includes `zones`; both `ZonesPanel`s +
   unset state.
   *Verify:* set FTP/HR → zone times sum to ride time; unset → prompt to Settings.
5. **Climbs** — migration `0007`; `extract_efforts` captures climb fields; `list_activity_climbs`;
   `analysis.compute_climbs`; detail response includes `climbs`; `ClimbsPanel`; one-time re-backfill.
   *Verify:* climbs match Strava; VAM correct; hardest-first ordering.

## Error handling & edge cases

- **Lazy fetch cost:** one Strava streams call per activity, only on first view; reuse the existing
  429-backoff; token from `get_valid_access_token`.
- **Activity not found / not owned:** service raises a domain error → 404; page shows a not-found
  state.
- **Missing channels:** no `watts` → AVG POWER/WORK/NP `null`, power-zones block `unset`, power chart
  shows an empty/“no power data” state; no `heartrate` → HR-zones block `unset`.
- **FTP / max HR unset:** the corresponding zones block returns `unset`; the panel shows a setup
  prompt linking to Settings rather than erroring.
- **No streams available** (manual / very old activities): sentinel `activity_streams` row prevents
  refetch; detail returns header + climbs with empty zones/charts.
- **No GPS** (`summary_polyline` null/empty): `RouteHero` shows the caption over a plain themed panel
  (no map), no Leaflet errors.
- **Map tiles fail to load:** route overlay + caption still render over the panel background.

## Testing

- **Backend (pytest):** `services/analysis.py` thorough pure-fn unit tests — NP against a known-value
  series, zone-% boundaries, Δt-weighted time-in-zone (incl. non-1 Hz), work, VAM. Service tests use
  a Strava stub + supabase mock **at the service boundary**; router tests via `TestClient` mock the
  service layer. `test_architecture.py` continues to enforce layering.
- **Frontend (Vitest + RTL):** api fetch fns + hooks with mocked `apiFetch`; `lib/polyline.ts`
  unit-tested (decode + normalize); panel render tests against sample DTOs incl. **missing-watts** and
  **unset-FTP** states; `ActivityTable` link target asserted. Leaflet is mocked in panel tests
  (jsdom has no canvas/map).
- **Per-increment verification:** a browser/API smoke check at each checkpoint before merge.
- `npm test && npm run lint && npm run build` green before any frontend change is considered done;
  backend `pytest` green before any backend change.

## Out of scope (this effort)

- Dropped design sections: training load, gear, cadence, laps; topbar Export/Edit.
- Mapbox / keyed tile providers (the swappable seam is built; the switch is not).
- Pulling zones/FTP from Strava (`profile:read_all`).
- Editing activity metadata.

## Open questions / risks

- **Streams availability** on manual/virtual/older rides — handled by the sentinel row; confirm on
  real data in Increment 1.
- **HR zone percentages** are an illustrative default; revisit against real rides.
- **Historical climb backfill** — existing segments need a paced detail re-backfill (one-time).
- **Leaflet bundle + tiles in jsdom** — mock the map in tests; confirm SSR-free dynamic behavior is
  fine for the Vite SPA (it is; no SSR here).
