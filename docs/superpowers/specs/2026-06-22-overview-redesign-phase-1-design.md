# Overview redesign — Phase 1: dashboard frame + activity-data panels

**Date:** 2026-06-22
**Branch:** feature branch off `main` (multi-phase work; merge each phase when green).
**Design source:** `Peakstats Overview.dc.html` (Claude Design project `646622a9…`).

## Problem

The current Overview (`/home`) is thin: four KPI cards for the current week, a single
"Distance over time" week chart, and a recent-rides list. The new design is a far richer
dashboard driven by a **Week / Month / Year period selector**, with a headline hero,
a records summary, ride-type breakdown, an activity heatmap, a weekly-goal ring, and
time-in-zones panels.

The full redesign is large and spans three effort tiers (see below), so it is split into
three independently shippable phases. **This spec covers Phase 1 only.**

## Phasing (whole redesign)

- **Phase 1 (this spec):** dashboard frame + period selector + hero + summary/records +
  recent rides + ride-types donut. Pure `activities`-table aggregation — no new data
  infrastructure.
- **Phase 2:** activity heatmap (`react-activity-calendar`) + weekly-goal ring (adds a
  goal-target field to athlete settings).
- **Phase 3:** Time in power zones + Time in HR zones (aggregated from stored
  `activity_streams` using FTP / HR-max), plus the "Top avg power" summary stat.

The "Bikes & gear / component wear" panel in the design is **out of scope entirely** (per
user instruction).

## Decisions (locked during brainstorming)

1. **Three phases**, each shipping end-to-end (backend + frontend + tests). Heavy
   stream-based zone work is isolated to Phase 3.
2. **Calendar periods**, not rolling windows:
   - **Week** = current Mon–Sun → 7 daily trend points → Δ vs last week.
   - **Month** = current calendar month → daily trend points → Δ vs last month.
   - **Year** = current calendar year → 12 monthly trend points → Δ vs last year.
3. **Reflow layout, no placeholders.** Phase 1 ships a complete, polished page. The grid
   re-flows as Phase 2/3 panels slot in — no "coming soon" empty panels.
4. **No "Refresh from Strava" button.** Removed from the header (sync is automatic via
   webhooks; sync status still shows in the sidebar user block). Matches the design.
5. **Headline metric = Distance.** The hero's big number and the trend chart both plot
   distance. The three secondary KPIs are Moving time, Elevation, Avg speed.
6. **"Top avg power" deferred to Phase 3** — no power column exists on `activities`
   (only on `segment_efforts`). The Phase 1 summary card shows five stats.
7. **Period is in-session state**, seeded from `settings.default_period` (default
   `"week"`). Switching the selector does **not** persist; surfacing a "Default time
   range" control on the Settings page is out of Phase 1 scope.

## Layout

Vertical order inside the scroll body (`p-7`), reusing existing surface/border tokens:

1. **Hero** — full-width card, two columns:
   - **Left:** headline KPI. Mono label `DISTANCE · THIS WEEK`, value ~64px
     (`font-display`), unit, and a delta pill (`+18% vs last week`, good/bad tokened).
     Below a divider, a 3-up row of secondary KPIs (Moving time, Elevation, Avg speed),
     each `label / value+unit / delta`.
   - **Right:** trend chart — area+line of distance over the selected period, with a small
     left Y-axis scale and X-axis labels. Built on Recharts (generalized `WeekChart`).
2. **Summary / records card** — full-width. Stat grid: `RIDES`, `PERSONAL RECORDS`
   (accent-colored), `TOP AVG SPEED`, `LONGEST RIDE`, `MAX ELEV GAIN`. Five stats in
   Phase 1; `TOP AVG POWER` slots in at Phase 3.
3. **Lower row** — two columns, exactly as designed:
   - **Recent rides** (wider, ~1.55fr): list rows with a type-colored dot, ride name +
     optional **PR badge**, `date · type` meta, distance + duration, chevron. Each row
     links to `/activities/:id`. A `VIEW ALL →` action links to `/activities`.
   - **Ride types donut** (~1fr): donut chart of ride count by activity type, with a
     legend (color swatch, type label, percentage) and a `{total} TOTAL` caption.

Responsive: collapse multi-column rows to single column at the existing `max-[1024px]`
breakpoint used by the current KPI grid.

### Header

The page header (in `AppShell` via `AppHome`) shows the title "Overview", the sync
subtitle, and the **period selector** (Week / Month / Year segmented control) on the
right. The theme toggle remains where `AppShell` already renders it. No refresh button.

## Backend — extend `GET /activities/overview`

Add a `period` query param (`week` | `month` | `year`), defaulting to the athlete's
`settings.default_period`. Keep the existing `tz` param. The endpoint stays a single
round-trip.

New response shape (replaces the current `OverviewResponse`):

```jsonc
{
  "period": "week",
  "this_period": { "distance_m": 0, "elev_gain_m": 0, "moving_time_s": 0, "avg_speed_ms": 0 },
  "last_period": { "distance_m": 0, "elev_gain_m": 0, "moving_time_s": 0, "avg_speed_ms": 0 },
  "trend": [ { "label": "Mon", "value": 0 } ],            // distance per bucket over the period
  "summary": {
    "rides": 0,
    "prs": 0,                 // count of is_pr in period
    "top_speed_ms": 0,        // max avg_speed_ms in period (nullable)
    "longest_ride_m": 0,      // max distance_m in period
    "max_elev_m": 0           // max elev_gain_m in period
  },
  "ride_types": [ { "type": "Ride", "count": 0 } ],       // counts by activity type in period
  "recent_rides": [
    { "id": 0, "name": "", "type": "", "start_date": "", "start_date_local": null,
      "distance_m": 0, "moving_time_s": 0, "is_pr": false }
  ]
}
```

Aggregation is computed in `activities_service` against the `activities` table, bucketed
by the local ride day (`start_date_local`, consistent with existing chart bucketing):

- **Period bounds** derived from "now" in the request `tz`: current Mon–Sun / month /
  calendar year, plus the immediately preceding equivalent period for `last_period`.
- **trend** buckets the headline metric (distance) by day (week, month) or by month
  (year), zero-filled across the full period so the chart has a fixed point count.
- **summary** aggregates over the current period only.
- **ride_types** counts activities by `type` over the current period.
- **recent_rides** keeps the existing "latest N" behavior, now including `is_pr`.

## Frontend

- **`api/overview.ts`** — accept a `period` arg; map the new DTO into formatted display
  shapes (units applied in the mapper, as today). The hook reads the period from page
  state, seeded from `useSettings()`'s `default_period`.
- **`types/overview.ts`** — new DTO + display interfaces for hero/summary/trend/ride-types.
- **Components** (page-local under `pages/app-home/components/`):
  - `PeriodSelector.tsx` — 3-button segmented control; controlled value + onChange.
  - `HeroPanel.tsx` — headline KPI + 3 secondary KPIs + trend chart.
  - `TrendChart.tsx` — generalize the current `WeekChart` to take `{label,value}[]`
    (rename/relocate; `WeekChart` is removed once nothing else uses it).
  - `SummaryCard.tsx` — the five records/summary stats.
  - `RideTypesDonut.tsx` — donut + legend; computes slice paths + percentages.
  - Update `RecentRidesPanel.tsx` — PR badge, type-colored dot, row link to
    `/activities/:id`, `VIEW ALL →` to `/activities`.
  - Remove `KpiCards.tsx` and `DistancePanel.tsx` (folded into `HeroPanel`).
- **`AppHome.tsx`** — own the `period` state, drop the refresh button + handler, compose
  the new panels.
- **Tokens** — add ride-type / donut palette colors to **both** `:root` and `.dark` in
  `index.css`, mapped under `@theme inline` (per the frontend styling contract). No raw
  hex in components.

## Testing

TDD per the frontend/backend contracts; `npm test && npm run lint && npm run build` and
the backend test suite must pass.

- **Backend:** `activities_service` tests for each period (week/month/year) — bounds,
  `this_period`/`last_period` deltas, zero-filled `trend` length & ordering, `summary`
  aggregates (including empty-period edge cases), `ride_types` counts, `recent_rides`
  with `is_pr`. Router test for the `period` param + default fallback.
- **Frontend:** updated `AppHome.test.tsx`; unit tests for the DTO→display mapper,
  `RideTypesDonut` slice math, `TrendChart` data mapping, and `PeriodSelector` behavior.

## Out of scope (Phase 1)

- Activity heatmap, weekly-goal ring (Phase 2).
- Time in power/HR zones, top-avg-power stat (Phase 3).
- Bikes & gear / component wear (cut entirely).
- A Settings-page "Default time range" control (period is seeded but not persisted here).
