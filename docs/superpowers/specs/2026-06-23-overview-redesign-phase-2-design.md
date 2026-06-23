# Overview redesign — Phase 2: activity heatmap + weekly-goal ring

**Date:** 2026-06-23
**Branch:** feature branch off `main` (multi-phase work; merge when green).
**Design source:** `Peakstats Overview.dc.html` (Claude Design project `646622a9…`).
**Predecessor:** `2026-06-22-overview-redesign-phase-1-design.md` (Phase 1 — shipped, on `main`).

## Problem

Phase 1 shipped the redesigned Overview frame: a Week/Month/Year period selector
driving a hero KPI + trend chart, a records summary, recent rides, and a ride-types
donut. Two designed panels were deferred to Phase 2:

- An **activity heatmap** — a GitHub-style calendar of the year, each day shaded by
  distance ridden, with a `{year} · {N} ACTIVE DAYS` caption and a Less→More legend.
- A **weekly-goal ring** — a radial progress ring showing the current week's distance
  against a target the athlete sets, with `{pct}% OF GOAL` and `{done} / {target}` labels.

Phase 2 adds both, plus the athlete-settings field that backs the goal target.

## Phasing recap (whole redesign)

- **Phase 1 (shipped):** frame + period selector + hero + summary + recent rides + donut.
- **Phase 2 (this spec):** activity heatmap (`react-activity-calendar`) + weekly-goal ring
  (adds `weekly_goal_m` to athlete settings).
- **Phase 3:** time in power zones + time in HR zones (aggregated from stored
  `activity_streams`), plus the "Top avg power" summary stat.

The "Bikes & gear / component wear" panel remains **out of scope entirely**.

## Decisions (locked during brainstorming)

1. **Goal metric = weekly distance.** Stored in meters (metric storage convention),
   displayed km/mi. Natural pairing with the Distance headline KPI.
2. **Unset goal → sensible default.** When the athlete has not set a goal, the ring
   renders against `DEFAULT_WEEKLY_GOAL_M = 100_000` (100 km ≈ 62 mi), applied as a
   **frontend fallback constant** — no DB backfill of existing athletes' settings. The
   Settings input seeds from `weekly_goal_m ?? DEFAULT`.
3. **Heatmap span = current calendar year** (Jan 1 → Dec 31), independent of the
   Week/Month/Year selector — matching the design (`2026 · N ACTIVE DAYS`).
4. **One endpoint, one round-trip.** Both new blocks extend the existing
   `GET /activities/overview` response rather than adding a second endpoint. They are
   selector-independent, so they re-fetch on every period toggle; the payload is small
   (~150–250 sparse day entries, ~6 KB) and the aggregation runs over rows already
   fetched, so the cost is negligible and the page stays a single hook.
5. **Goal target is applied frontend-side.** The backend reports only the raw current-week
   distance (`week_distance_m`); the target comes from `useSettings()` and is combined in
   the display mapper. This makes the ring react instantly to a Settings change with no
   query invalidation — the same mechanism Phase 1 already uses for unit changes.
6. **Heatmap intensity = distance/day**, 5 levels with the design's thresholds
   (`0 / <10 / <25 / <50 / ≥50 km`), computed on meters so they are unit-independent.
7. **Streak counter is not included.** Phase 2 is heatmap + weekly goal only.

## Layout

A new full-width row, `grid-cols-[2.7fr_1fr]`, inserted **between** `SummaryCard` and the
recent-rides/donut row (the design's vertical order), inside the existing `p-7` scroll body:

```
HeroPanel
SummaryCard
<grid 2.7fr | 1fr:  ActivityHeatmap | WeeklyGoalRing>   ← Phase 2
<grid 1.55fr | 1fr: RecentRidesPanel | RideTypesDonut>
```

Collapses to a single column at the existing `max-[1024px]` breakpoint. Both panels reuse
the standard `bg-surface-card border border-line rounded-2xl` surface and the
`transition-colors duration-300` treatment used by the other panels.

## Backend — extend `GET /activities/overview`

No new route. Two fields are added to `OverviewResponse`:

```jsonc
{
  // …existing Phase 1 fields (period, this_period, last_period, trend, summary,
  //   ride_types, recent_rides)…
  "heatmap": {
    "year": 2026,
    "days": [ { "date": "2026-06-16", "distance_m": 38700.0 } ]   // active days only (distance>0)
  },
  "week_distance_m": 64000.0   // current Mon–Sun distance, independent of the selector
}
```

### Models (`backend/app/models/activities.py`)

Add:

```python
class HeatmapDay(BaseModel):
    date: str          # local ride day, "YYYY-MM-DD"
    distance_m: float


class HeatmapData(BaseModel):
    year: int
    days: list[HeatmapDay]
```

Extend `OverviewResponse` with `heatmap: HeatmapData` and `week_distance_m: float`.

### Service (`backend/app/services/activities.py`)

`get_overview` already resolves `now_local`, the period bounds, and queries rows once.
Changes:

- **Widen the query lower bound** from `last_start - 1 day` to
  `min(year_start, last_start) - 1 day` (where `year_start = base.replace(month=1, day=1)`),
  so one query covers the period totals, the current week, **and** the full-year heatmap.
  For `period="year"`, `last_start` (last Jan 1) is already ≤ `year_start`, so the bound is
  unchanged; for week/month it extends back to Jan 1.
- **`week_distance_m`** — sum `distance_m` over rows whose local day falls in the current
  Mon–Sun week (`week_start = base - timedelta(days=base.weekday())`, half-open
  `[week_start, week_start + 7d)`), regardless of the selected period.
- **`heatmap`** — a new `_heatmap(rows, year)` helper: bucket `distance_m` by local ride day
  (`_local_naive(r).date()`) for rows whose local year == the current year, emit
  `HeatmapDay` entries for active days only (distance > 0), sorted ascending by date.
  `year` is the current local year.

All three derive from the single widened query using the existing `_local_naive` helper and
local-time filtering established in Phase 1.

### Router (`backend/app/routers/activities.py`)

No change — the route already returns `OverviewResponse`; the two new fields flow through.

## Settings — new `weekly_goal_m` field

Athlete settings are stored as a loose `dict` on the athlete row, so no migration is needed —
only the typed views that gate writes and reads.

- **Backend (`backend/app/models/athlete.py`):** add `weekly_goal_m: int | None = None` to
  `SettingsUpdate` (extend the `extra="forbid"` allow-list and the `require_at_least_one`
  validator's field tuple).
- **Frontend type (`frontend/src/types/athlete.ts`):** add `weekly_goal_m?: number` to
  `AthleteSettings`.
- **Frontend API (`frontend/src/api/settings.ts`):** add `weekly_goal_m?: number` to
  `SettingsPatch`.
- **Settings page (`frontend/src/pages/settings/SettingsPage.tsx`):** add a **"Weekly distance
  goal"** numeric input. It reads the stored goal (or the default), is labelled in the user's
  distance unit (km/mi), and on `onBlur` converts via `distanceToMeters(value, units)` then
  PATCHes `weekly_goal_m`, reusing the existing
  `patchSettings(...).then(updated => queryClient.setQueryData(["athlete"], updated))` pattern
  used by FTP / Max-HR. Placed in a new "Goals" section card on the page.

## Frontend

### Dependency

Add `react-activity-calendar` (`npm install react-activity-calendar`). It renders the
GitHub-style grid, month/weekday labels, and color legend from a `{date, count, level}[]`
array; we supply explicit `level`s and an orange `theme`.

### Types (`frontend/src/types/overview.ts`)

DTO additions:

```typescript
export interface HeatmapDayDTO {
  date: string;        // "YYYY-MM-DD"
  distance_m: number;
}

export interface HeatmapDTO {
  year: number;
  days: HeatmapDayDTO[];
}
```

Extend `OverviewDTO` with `heatmap: HeatmapDTO` and `week_distance_m: number`.

Display additions:

```typescript
export interface HeatmapView {
  year: number;
  activeDays: number;
  /** Full-year entries for react-activity-calendar (zero-filled, range-forced). */
  data: { date: string; count: number; level: number }[];
}

export interface GoalView {
  pct: number;          // 0..100, capped
  pctLabel: string;     // "64%"
  doneLabel: string;    // "64.0"   (value only; unit shown separately)
  targetLabel: string;  // "100.0"
  unit: string;         // "km" | "mi"
  remainingLabel: string; // "36.0"
}
```

Extend `DashboardOverview` with `heatmap: HeatmapView` and `goal: GoalView`.

### Mapper + hook (`frontend/src/api/overview.ts`)

- `DEFAULT_WEEKLY_GOAL_M = 100_000` exported constant.
- Heatmap level thresholds (meters): `level(d) = d <= 0 ? 0 : d < 10_000 ? 1 : d < 25_000 ? 2
  : d < 50_000 ? 3 : 4`.
- `buildHeatmapView(dto.heatmap, units)`:
  - `activeDays = dto.heatmap.days.length`.
  - Build a date→distance map; produce one entry per active day with `count = distance_m`,
    `level` from the thresholds.
  - **Force the full-year range**: ensure entries exist for `${year}-01-01` and `${year}-12-31`
    (level 0, count 0) so the calendar spans the year even with sparse data. (`count` stays in
    meters; the heatmap component formats the tooltip via `units`.)
- `buildGoalView(weekDistanceM, weeklyGoalM, units)`:
  - `target = weeklyGoalM ?? DEFAULT_WEEKLY_GOAL_M`.
  - `pct = target > 0 ? Math.min(100, Math.round((done / target) * 100)) : 0`.
  - `remaining = Math.max(0, target - done)`.
  - Labels via `distanceValue` / `distanceUnit` (numeric value + shared unit), so the ring shows
    `done / target unit` and `remaining unit to go`.
- `toOverview(dto, units, weeklyGoalM)` gains the third arg and returns the extended shape.
- `useOverview(period)` reads `units` **and** `weekly_goal_m` from `useSettings()` and passes
  both into the `select` mapper. Because `select` already closes over settings (the Phase 1
  units-reactivity mechanism), changing the goal in Settings updates the ring with no query
  invalidation.

### Components (`pages/app-home/components/`)

- **`ActivityHeatmap.tsx`** — `<ActivityHeatmap view={HeatmapView} isDark={boolean} units={Units} />`.
  Wraps `react-activity-calendar`:
  - `data={view.data}`, `maxLevel={4}`.
  - `colorScheme={isDark ? "dark" : "light"}`, explicit 5-entry orange `theme`
    (`theme={{ light: [...], dark: [...] }}`, levels 0→4). **Colors are JS literals defined in
    the component**, not `index.css` tokens — this is the same documented chart-color exception
    `TrendChart`/`WeekChart` use (Recharts/the calendar lib need literal color strings; the lib
    validates `theme` colors and does not accept `var(...)`). The ramp mirrors the design's
    `rgba(252,76,2, …)` ladder, with the level-0 "empty" cell differing per theme.
  - `showWeekdayLabels={['mon','wed','fri']}`, `showMonthLabels`, `weekStart={0}` (Sunday, matching
    the design + GitHub), `showTotalCount={false}` (custom header instead), `showColorLegend`.
  - Native `<title>` tooltips via `renderBlock` (`{distanceLabel(count, units)} on {date}`) — no
    extra tooltip dependency.
  - Card chrome + a custom header `Activity` / `{year} · {activeDays} ACTIVE DAYS`.
  - **Fidelity note:** future days in the current year render as empty level-0 cells (the library
    does not distinguish future from past zero-days). The design dimmed future days a shade
    further; that extra treatment is dropped for Phase 2 simplicity.
- **`WeeklyGoalRing.tsx`** — `<WeeklyGoalRing goal={GoalView} />`. Presentational radial SVG ring
  (track circle + orange arc via `stroke-dasharray`/`stroke-dashoffset` from `goal.pct`), centered
  `{pctLabel}` / `OF GOAL`, `{doneLabel} / {targetLabel} {unit}` below, `{remainingLabel} {unit}
  to go`. Centered card layout per the design.

### Page (`frontend/src/pages/app-home/AppHome.tsx`)

Insert the new `grid-cols-[2.7fr_1fr] max-[1024px]:grid-cols-1` row between `SummaryCard` and
the existing lower grid, passing `overview.heatmap` + `isDark` + `units` to `ActivityHeatmap`
and `overview.goal` to `WeeklyGoalRing`. Extend the loading `SkeletonPanels` with a matching
block so the skeleton still covers the page.

### Tokens

**No `index.css` change.** The heatmap orange ramp lives as JS literal arrays inside
`ActivityHeatmap.tsx` (see above) under the documented chart-color exception, exactly as
`TrendChart`/`WeekChart` already pass literal Recharts colors. The `WeeklyGoalRing` is plain
SVG with the existing token utilities for text/surfaces and a literal orange arc stroke (the
same `#fc4c02` literal `TrendChart` already uses), so it needs no new tokens either.

## Testing

TDD per `backend/CLAUDE.md` and `frontend/CLAUDE.md`. Gates: backend `pytest && ruff check . &&
mypy`; frontend `npm test && npm run lint && npm run build`.

- **Backend (`tests/services/test_activities.py`):**
  - `heatmap` — buckets distance by local day for the current year; active days only
    (distance > 0); excludes other-year rows; sorted ascending; empty-safe (`days == []`).
  - `week_distance_m` — sums only the current Mon–Sun week, and is identical for
    `period in {week, month, year}` (selector-independent).
  - Existing Phase 1 period/trend/summary/ride-type tests stay green.
- **Frontend:**
  - Mapper (`api/overview.test.ts`) — heatmap level thresholds at the boundaries
    (0 / 9.99 / 10 / 25 / 50 km), Jan 1 + Dec 31 range sentinels present, `activeDays` count;
    goal math (pct cap at 100, remaining floor at 0, `DEFAULT` fallback when goal unset, imperial
    target label).
  - `WeeklyGoalRing` render test (pct/labels rendered).
  - `ActivityHeatmap` render test with `react-activity-calendar` mocked (jsdom can't size it) —
    asserts the active-days header and that data is passed.
  - `SettingsPage.test.tsx` — the goal input PATCHes `weekly_goal_m` (converted to meters).
  - `AppHome.test.tsx` — the new row renders within the loaded dashboard.

## Out of scope (Phase 2)

- Time in power/HR zones, top-avg-power stat (Phase 3).
- Streak counter; bikes & gear / component wear (cut entirely).
- Persisting the period selector or any other Settings control beyond `weekly_goal_m`.
