# Overview Redesign — Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the activity heatmap (full calendar year, shaded by distance/day) and the weekly-goal ring (current-week distance vs an athlete-set target) to the Overview dashboard, backed by two new fields on `GET /activities/overview` and a new `weekly_goal_m` athlete setting.

**Architecture:** The backend extends the existing single-round-trip `get_overview` service with a year-scoped `heatmap` and a selector-independent `week_distance_m`, both derived from one widened row query. The goal *target* is **not** sent by the backend — it lives in athlete settings and is combined with `week_distance_m` in the frontend display mapper (so the ring reacts to a Settings change with no query invalidation, the same mechanism Phase 1 uses for units). New page-local presentational components render the two panels; `react-activity-calendar` draws the grid.

**Tech Stack:** FastAPI + Pydantic + Supabase (Python client), pytest; React 19 + Vite + TypeScript + Tailwind v4 + `react-activity-calendar`, Vitest + Testing Library.

## Global Constraints

- **Backend layering:** routers → services → db, no layer skipped. Services have no `fastapi` imports; routers own HTTP. DB modules return their `TypedDict` row shapes. (`backend/CLAUDE.md`)
- **Backend style:** type annotations on every public function; `def` (not `async def`) when not awaiting; Pydantic at all I/O boundaries. `ruff check .` and `mypy` must be clean.
- **Frontend styling:** token utilities only — **never raw hex**, never `text-[#..] dark:text-[#..]` pairs. The single exception is **chart colors**, which may be JS literals (as `TrendChart`/`WeekChart` already do); the heatmap ramp and the goal-ring progress arc use this exception. (`frontend/CLAUDE.md`)
- **Frontend structure:** page-only components live in `pages/app-home/components/`; pages compose, components render; data comes from the `api/` layer via a hook; imports use the `@/` alias.
- **Tests must pass before any task is done:** backend `pytest`; frontend `npm test && npm run lint && npm run build`.
- **Scope:** Phase 2 only — heatmap + weekly-goal ring + the `weekly_goal_m` setting. No power/HR zones, no top-avg-power, no streak counter, no bikes/gear.
- **Locked decisions:** goal metric = weekly **distance** (stored meters); unset goal falls back to `DEFAULT_WEEKLY_GOAL_M = 100_000` (100 km) frontend-side; heatmap spans the **current calendar year**, independent of the period selector; heatmap intensity levels (on meters) `0 / <10k / <25k / <50k / ≥50k`.

---

## File Structure

**Backend**
- Modify `backend/app/models/activities.py` — add `HeatmapDay`, `HeatmapData`; extend `OverviewResponse` with `heatmap` + `week_distance_m`.
- Modify `backend/app/services/activities.py` — import the new models; add `_heatmap`; compute current-week distance; widen the row query; populate the two new response fields.
- Modify `backend/app/models/athlete.py` — add `weekly_goal_m` to `SettingsUpdate`.
- Tests: `backend/tests/services/test_activities.py`, `backend/tests/routers/test_activities.py` (update 3 `OverviewResponse` constructions), `backend/tests/services/test_athletes.py`, `backend/tests/routers/test_athletes.py`.

**Frontend**
- Modify `frontend/src/types/overview.ts` — heatmap/goal DTO + display types; extend `OverviewDTO` + `DashboardOverview`.
- Modify `frontend/src/api/overview.ts` — `DEFAULT_WEEKLY_GOAL_M`, level fn, `buildHeatmapView`, `buildGoalView`, `toOverview` 3rd arg, `useOverview` reads the goal from `useAthlete()`.
- Modify `frontend/src/types/athlete.ts` — add `weekly_goal_m?: number` to `AthleteSettings`.
- Modify `frontend/src/api/settings.ts` — add `weekly_goal_m?: number` to `SettingsPatch`.
- Create `frontend/src/pages/app-home/components/WeeklyGoalRing.tsx` (+ test).
- Create `frontend/src/pages/app-home/components/ActivityHeatmap.tsx` (+ test).
- Modify `frontend/src/pages/app-home/AppHome.tsx` (+ `AppHome.test.tsx` fixture).
- Modify `frontend/src/pages/settings/SettingsPage.tsx` (+ `SettingsPage.test.tsx`).
- Add dependency `react-activity-calendar`.
- Tests: `frontend/src/api/overview.test.ts`.

---

## Task 1: Backend — heatmap + week-distance models, service aggregation

**Files:**
- Modify: `backend/app/models/activities.py:8-54`
- Modify: `backend/app/services/activities.py:11-28,44-46,139-192`
- Test: `backend/tests/services/test_activities.py`
- Modify (keep suite green): `backend/tests/routers/test_activities.py:3-13,22-37,76-83,98-105`

**Interfaces:**
- Produces: `HeatmapDay(date: str, distance_m: float)`; `HeatmapData(year: int, days: list[HeatmapDay])`; `OverviewResponse` gains `heatmap: HeatmapData` and `week_distance_m: float`. `get_overview(...)` signature unchanged.

- [ ] **Step 1: Write the failing service tests**

Append to `backend/tests/services/test_activities.py` (after `test_overview_recent_ride_exposes_start_date_local`, end of file):

```python
def test_heatmap_buckets_current_year_active_days(monkeypatch):
    rows = [
        _row(1, "2026-01-02T10:00:00", 12000.0, 1000, 0.0, 8.0),
        _row(2, "2026-01-02T15:00:00", 8000.0, 800, 0.0, 8.0),    # same day → sums
        _row(3, "2025-12-31T10:00:00", 9000.0, 900, 0.0, 8.0),    # last year → excluded
    ]
    _patch(monkeypatch, rows, [])
    ov = activities_service.get_overview(object(), 7, period="year", now=NOW)
    assert ov.heatmap.year == 2026
    assert {d.date: d.distance_m for d in ov.heatmap.days} == {"2026-01-02": 20000.0}


def test_week_distance_is_current_week_regardless_of_period(monkeypatch):
    _patch(monkeypatch, THIS_WEEK + LAST_WEEK, [])
    for period in ("week", "month", "year"):
        ov = activities_service.get_overview(object(), 7, period=period, now=NOW)
        assert ov.week_distance_m == 30000.0


def test_heatmap_and_week_distance_empty_safe(monkeypatch):
    _patch(monkeypatch, [], [])
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.heatmap.days == []
    assert ov.heatmap.year == 2026
    assert ov.week_distance_m == 0.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/services/test_activities.py -k "heatmap or week_distance" -q`
Expected: FAIL — `OverviewResponse` has no `heatmap` / `week_distance_m`.

- [ ] **Step 3: Add the heatmap models**

In `backend/app/models/activities.py`, after the `Period` alias / before `PeriodTotals` (i.e. after line 8), add:

```python


class HeatmapDay(BaseModel):
    date: str          # local ride day, "YYYY-MM-DD"
    distance_m: float


class HeatmapData(BaseModel):
    year: int
    days: list[HeatmapDay]
```

Then extend `OverviewResponse` (currently lines 47-54) to:

```python
class OverviewResponse(BaseModel):
    period: Period
    this_period: PeriodTotals
    last_period: PeriodTotals
    trend: list[TrendPoint]
    summary: OverviewSummary
    ride_types: list[RideTypeCount]
    recent_rides: list[RecentRideItem]
    heatmap: HeatmapData
    week_distance_m: float
```

- [ ] **Step 4: Update the service imports + add the `_heatmap` helper**

In `backend/app/services/activities.py`, add `HeatmapData` and `HeatmapDay` to the model import block (lines 11-28), keeping alphabetical order (insert after `ClimbItem`):

```python
    ClimbItem,
    HeatmapData,
    HeatmapDay,
    OverviewResponse,
```

Then add this helper just before `get_overview` (after `_ride_types`, around line 145):

```python
def _heatmap(rows: list[ActivityRow], year: int) -> HeatmapData:
    by_day: dict[str, float] = {}
    for r in rows:
        d = _local_naive(r)
        if d.year != year:
            continue
        key = d.date().isoformat()
        by_day[key] = by_day.get(key, 0.0) + r["distance_m"]
    days = [
        HeatmapDay(date=k, distance_m=round(v, 1))
        for k, v in sorted(by_day.items())
        if v > 0
    ]
    return HeatmapData(year=year, days=days)
```

- [ ] **Step 5: Widen the query and populate the new fields in `get_overview`**

In `backend/app/services/activities.py`, replace the query + computation block. Replace lines 158-164 (from `this_start, this_end, last_start = _period_bounds(...)` through the `rows = activities_db.list_activities_since(...)` call) with:

```python
    this_start, this_end, last_start = _period_bounds(base, period)
    year_start = base.replace(month=1, day=1)
    week_start = base - timedelta(days=base.weekday())

    # One widened query feeds the period totals, the current-week distance, and the
    # full-year heatmap. Query by UTC start_date (can sit ~14h off local), so go back
    # an extra day and filter precisely by local time below.
    query_start = min(year_start, last_start) - timedelta(days=1)
    rows = activities_db.list_activities_since(
        supabase, athlete_id, query_start.isoformat()
    )
```

Then, immediately after the existing `this_rows` / `last_rows` lines (currently 171-172), add the current-week sum:

```python
    ws, we = week_start.replace(tzinfo=None), (week_start + timedelta(days=7)).replace(tzinfo=None)
    week_distance_m = sum(r["distance_m"] for r in rows if ws <= _local_naive(r) < we)
```

Finally, extend the `return OverviewResponse(...)` (currently lines 184-192) to include the two new fields:

```python
    return OverviewResponse(
        period=period,
        this_period=_totals(this_rows),
        last_period=_totals(last_rows),
        trend=_trend(this_rows, this_start, this_end, period),
        summary=_summary(this_rows),
        ride_types=_ride_types(this_rows),
        recent_rides=recent_rides,
        heatmap=_heatmap(rows, base.year),
        week_distance_m=week_distance_m,
    )
```

- [ ] **Step 6: Update the router-test `OverviewResponse` constructions**

The router test constructs `OverviewResponse` three times; add the two new required fields so the suite stays green.

In `backend/tests/routers/test_activities.py`, add `HeatmapData` to the top import block (lines 3-13), after `ActivityStreamsResponse`:

```python
    ActivityStreamsResponse,
    HeatmapData,
    OverviewResponse,
```

In `_overview()` (lines 34-37), change the tail of the constructor — replace:

```python
        recent_rides=[RecentRideItem(id=1, name="Tue ride", type="Ride",
                                     start_date="2026-06-16T10:00:00Z",
                                     distance_m=10000.0, moving_time_s=1000)],
    )
```

with:

```python
        recent_rides=[RecentRideItem(id=1, name="Tue ride", type="Ride",
                                     start_date="2026-06-16T10:00:00Z",
                                     distance_m=10000.0, moving_time_s=1000)],
        heatmap=HeatmapData(year=2026, days=[]),
        week_distance_m=30000.0,
    )
```

In the two inline `fake_overview` builders (lines 76-83 and 98-105), each has a local import line `from app.models.activities import OverviewResponse, OverviewSummary, PeriodTotals` and a `return OverviewResponse(...)`. For **both**, change the local import to include `HeatmapData`:

```python
        from app.models.activities import (
            HeatmapData, OverviewResponse, OverviewSummary, PeriodTotals,
        )
```

and change each `ride_types=[], recent_rides=[],` line to:

```python
            ride_types=[], recent_rides=[],
            heatmap=HeatmapData(year=2026, days=[]), week_distance_m=0.0,
        )
```

- [ ] **Step 7: Run the full backend suite + lint + types**

Run: `cd backend && pytest -q && ruff check . && mypy`
Expected: all pass (new + existing), lint/types clean.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/activities.py backend/app/services/activities.py backend/tests/services/test_activities.py backend/tests/routers/test_activities.py
git commit -m "feat(overview): heatmap + current-week distance on /activities/overview"
```

---

## Task 2: Backend — `weekly_goal_m` athlete setting

**Files:**
- Modify: `backend/app/models/athlete.py:13-27`
- Test: `backend/tests/services/test_athletes.py`, `backend/tests/routers/test_athletes.py`

**Interfaces:**
- Produces: `SettingsUpdate` accepts an optional `weekly_goal_m: int`. Persistence is unchanged — `athletes_service.update_settings` already merges `patch.model_dump(exclude_none=True)` over the stored settings dict, so the new field flows through with no service/db change.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/services/test_athletes.py`, add after `test_update_settings_merges_over_current`:

```python
def test_update_settings_merges_weekly_goal(monkeypatch):
    from app.models.athlete import SettingsUpdate

    written = {}
    monkeypatch.setattr(
        athletes.athletes_db, "get_athlete",
        lambda supabase, athlete_id: {
            "id": 7, "name": "Ada", "avatar_url": None,
            "settings": {"units": "metric", "theme": "dark", "default_period": "week"},
        },
    )
    monkeypatch.setattr(
        athletes.athletes_db, "update_settings",
        lambda supabase, athlete_id, settings: written.update(settings)
        or {"id": 7, "name": "Ada", "avatar_url": None, "settings": settings},
    )
    result = athletes.update_settings(object(), 7, SettingsUpdate(weekly_goal_m=120000))
    assert written["weekly_goal_m"] == 120000
    assert result is not None and result.settings["weekly_goal_m"] == 120000
```

In `backend/tests/routers/test_athletes.py`, add after `test_patch_settings_accepts_ftp_and_hr`:

```python
def test_patch_settings_accepts_weekly_goal(client, monkeypatch):
    from app.services import athletes as athletes_service
    captured = {}

    def fake(supabase, athlete_id, patch):
        captured["goal"] = patch.weekly_goal_m
        from app.models.athlete import AthleteResponse
        return AthleteResponse(id=athlete_id, name="A", avatar_url=None,
                               settings={"weekly_goal_m": patch.weekly_goal_m})

    monkeypatch.setattr(athletes_service, "update_settings", fake)
    _auth(client)
    r = client.patch("/athlete/settings", json={"weekly_goal_m": 120000})
    assert r.status_code == 200 and captured == {"goal": 120000}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/services/test_athletes.py tests/routers/test_athletes.py -k weekly_goal -q`
Expected: FAIL — `SettingsUpdate` has no `weekly_goal_m` (router returns 422 / `patch.weekly_goal_m` raises `AttributeError`).

- [ ] **Step 3: Add the field to `SettingsUpdate`**

In `backend/app/models/athlete.py`, replace the `SettingsUpdate` body (lines 13-27) with:

```python
class SettingsUpdate(BaseModel):
    """Partial update of athlete settings; at least one field required."""

    model_config = ConfigDict(extra="forbid")

    units: Literal["metric", "imperial"] | None = None
    theme: Literal["dark", "light"] | None = None
    ftp_w: int | None = None
    hr_max: int | None = None
    weekly_goal_m: int | None = None

    @model_validator(mode="after")
    def require_at_least_one(self) -> "SettingsUpdate":
        fields = (self.units, self.theme, self.ftp_w, self.hr_max, self.weekly_goal_m)
        if all(v is None for v in fields):
            raise ValueError(
                "at least one of units, theme, ftp_w, hr_max, weekly_goal_m is required"
            )
        return self
```

- [ ] **Step 4: Run the tests + full suite + lint + types**

Run: `cd backend && pytest -q && ruff check . && mypy`
Expected: all pass, lint/types clean.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/athlete.py backend/tests/services/test_athletes.py backend/tests/routers/test_athletes.py
git commit -m "feat(settings): accept weekly_goal_m on PATCH /athlete/settings"
```

---

## Task 3: Frontend — DTO types, display mapper, goal/heatmap views

**Files:**
- Modify: `frontend/src/types/overview.ts`
- Modify: `frontend/src/api/overview.ts`
- Modify: `frontend/src/types/athlete.ts:1-5`
- Modify: `frontend/src/api/settings.ts:5-10`
- Test: `frontend/src/api/overview.test.ts`

**Interfaces:**
- Produces: `OverviewDTO` gains `heatmap: HeatmapDTO` + `week_distance_m: number`; `DashboardOverview` gains `heatmap: HeatmapView` + `goal: GoalView`. `toOverview(dto, units, weeklyGoalM?)`. `DEFAULT_WEEKLY_GOAL_M = 100_000`. `HeatmapView = { year, activeDays, data: { date, count, level }[] }`. `GoalView = { pct, pctLabel, doneLabel, targetLabel, unit, remainingLabel }`.
- Consumes (downstream): `WeeklyGoalRing` takes `GoalView`; `ActivityHeatmap` takes `HeatmapView`.

- [ ] **Step 1: Write the failing mapper tests**

In `frontend/src/api/overview.test.ts`, extend the `DTO` constant (lines 5-22) to include the two new fields — change its closing lines:

```typescript
  recent_rides: [
    { id: 1, name: "River loop", type: "Ride", start_date: "2026-06-16T07:42:00Z",
      start_date_local: "2026-06-16T07:42:00Z", distance_m: 38700, moving_time_s: 5662, is_pr: true },
  ],
  heatmap: { year: 2026, days: [{ date: "2026-06-16", distance_m: 38700 }] },
  week_distance_m: 38700,
};
```

Then add these test blocks inside the `describe("toOverview", …)` block (before its closing `});`):

```typescript
  it("builds a full-year heatmap with distance levels and range sentinels", () => {
    const dto: OverviewDTO = {
      ...DTO,
      heatmap: {
        year: 2026,
        days: [
          { date: "2026-03-10", distance_m: 9000 },   // <10k → level 1
          { date: "2026-03-11", distance_m: 10000 },  // <25k → level 2
          { date: "2026-03-12", distance_m: 25000 },  // <50k → level 3
          { date: "2026-03-13", distance_m: 50000 },  // ≥50k → level 4
        ],
      },
    };
    const { heatmap } = toOverview(dto, "metric", 100000);
    expect(heatmap.year).toBe(2026);
    expect(heatmap.activeDays).toBe(4);
    const lvl = Object.fromEntries(heatmap.data.map((d) => [d.date, d.level]));
    expect(lvl["2026-03-10"]).toBe(1);
    expect(lvl["2026-03-11"]).toBe(2);
    expect(lvl["2026-03-12"]).toBe(3);
    expect(lvl["2026-03-13"]).toBe(4);
    expect(lvl["2026-01-01"]).toBe(0); // range forced
    expect(lvl["2026-12-31"]).toBe(0);
  });

  it("builds the goal view with pct, labels, and remaining", () => {
    const { goal } = toOverview({ ...DTO, week_distance_m: 64000 }, "metric", 100000);
    expect(goal).toMatchObject({
      pct: 64, pctLabel: "64%", doneLabel: "64.0",
      targetLabel: "100.0", unit: "km", remainingLabel: "36.0",
    });
  });

  it("caps goal pct at 100 and floors remaining at 0", () => {
    const { goal } = toOverview({ ...DTO, week_distance_m: 120000 }, "metric", 100000);
    expect(goal.pct).toBe(100);
    expect(goal.remainingLabel).toBe("0.0");
  });

  it("falls back to the default goal when none is set", () => {
    const { goal } = toOverview({ ...DTO, week_distance_m: 50000 }, "metric", undefined);
    expect(goal.targetLabel).toBe("100.0"); // DEFAULT_WEEKLY_GOAL_M
  });

  it("imperial goal uses miles", () => {
    const { goal } = toOverview({ ...DTO, week_distance_m: 0 }, "imperial", 100000);
    expect(goal).toMatchObject({ unit: "mi", targetLabel: "62.1" });
  });
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/api/overview.test.ts`
Expected: FAIL — `OverviewDTO` has no `heatmap` (type error) and `toOverview` returns no `heatmap`/`goal`.

- [ ] **Step 3: Add the DTO + display types**

In `frontend/src/types/overview.ts`, add the DTO types after `RecentRideDTO` (line 37):

```typescript
export interface HeatmapDayDTO {
  date: string; // "YYYY-MM-DD"
  distance_m: number;
}

export interface HeatmapDTO {
  year: number;
  days: HeatmapDayDTO[];
}
```

Extend `OverviewDTO` (lines 39-47) — add the two fields before the closing brace:

```typescript
export interface OverviewDTO {
  period: Period;
  this_period: PeriodTotalsDTO;
  last_period: PeriodTotalsDTO;
  trend: TrendPointDTO[];
  summary: OverviewSummaryDTO;
  ride_types: RideTypeCountDTO[];
  recent_rides: RecentRideDTO[];
  heatmap: HeatmapDTO;
  week_distance_m: number;
}
```

Add the display types after `RideTypesView` (line 87):

```typescript
export interface HeatmapCell {
  date: string;   // "YYYY-MM-DD"
  count: number;  // distance in meters (tooltip formats it)
  level: number;  // 0..4
}

export interface HeatmapView {
  year: number;
  activeDays: number;
  data: HeatmapCell[]; // full-year, zero-filled, range-forced
}

export interface GoalView {
  pct: number;            // 0..100, capped
  pctLabel: string;       // "64%"
  doneLabel: string;      // "64.0"  (value only)
  targetLabel: string;    // "100.0"
  unit: string;           // "km" | "mi"
  remainingLabel: string; // "36.0"
}
```

Extend `DashboardOverview` (lines 99-108) — add the two fields before the closing brace:

```typescript
export interface DashboardOverview {
  period: Period;
  headline: HeadlineKpi;
  secondary: Kpi[];
  trend: TrendPoint[];
  trendUnit: string;
  summary: SummaryView;
  rideTypes: RideTypesView;
  recentRides: DashRide[];
  heatmap: HeatmapView;
  goal: GoalView;
}
```

- [ ] **Step 4: Add `weekly_goal_m` to the athlete + settings types**

In `frontend/src/types/athlete.ts`, extend `AthleteSettings` (lines 1-5):

```typescript
export type AthleteSettings = {
  units: string;
  theme: string;
  default_period: string;
  weekly_goal_m?: number;
};
```

In `frontend/src/api/settings.ts`, extend `SettingsPatch` (lines 5-10):

```typescript
export type SettingsPatch = {
  units?: Units;
  theme?: "dark" | "light";
  ftp_w?: number;
  hr_max?: number;
  weekly_goal_m?: number;
};
```

- [ ] **Step 5: Implement the mapper changes**

In `frontend/src/api/overview.ts`:

(a) Extend the type import block (lines 2-5) to add `GoalView`, `HeatmapDTO`, `HeatmapView`:

```typescript
import type {
  DashboardOverview, DashRide, GoalView, HeatmapDTO, HeatmapView, Kpi,
  OverviewDTO, Period, RecentRideDTO, RideTypeSlice,
} from "@/types/overview";
```

(b) Add the `useAthlete` import below the existing `useSettings` import (line 8):

```typescript
import { useAthlete } from "./auth";
```

(c) Add the default constant + helpers just above `export function toOverview` (line 41):

```typescript
export const DEFAULT_WEEKLY_GOAL_M = 100_000; // 100 km

function heatLevel(meters: number): number {
  if (meters <= 0) return 0;
  if (meters < 10_000) return 1;
  if (meters < 25_000) return 2;
  if (meters < 50_000) return 3;
  return 4;
}

function buildHeatmapView(dto: HeatmapDTO): HeatmapView {
  const byDate = new Map<string, number>();
  for (const d of dto.days) byDate.set(d.date, d.distance_m);
  // Force the calendar to span the whole year even with sparse data.
  for (const sentinel of [`${dto.year}-01-01`, `${dto.year}-12-31`]) {
    if (!byDate.has(sentinel)) byDate.set(sentinel, 0);
  }
  const data = [...byDate.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, meters]) => ({ date, count: Math.round(meters), level: heatLevel(meters) }));
  return { year: dto.year, activeDays: dto.days.length, data };
}

function buildGoalView(weekDistanceM: number, weeklyGoalM: number | undefined, units: Units): GoalView {
  const target = weeklyGoalM ?? DEFAULT_WEEKLY_GOAL_M;
  const pct = target > 0 ? Math.min(100, Math.round((weekDistanceM / target) * 100)) : 0;
  const remaining = Math.max(0, target - weekDistanceM);
  const done = fmtDistance(weekDistanceM, units);
  const tgt = fmtDistance(target, units);
  const rem = fmtDistance(remaining, units);
  return {
    pct,
    pctLabel: `${pct}%`,
    doneLabel: done.value,
    targetLabel: tgt.value,
    unit: tgt.unit,
    remainingLabel: rem.value,
  };
}
```

(d) Change the `toOverview` signature (line 41) to accept the goal:

```typescript
export function toOverview(dto: OverviewDTO, units: Units, weeklyGoalM?: number): DashboardOverview {
```

(e) In the `return { … }` of `toOverview` (lines 76-91), add the two fields before the closing brace (after `recentRides: …,`):

```typescript
    recentRides: dto.recent_rides.map((r) => toRide(r, units, colorByType)),
    heatmap: buildHeatmapView(dto.heatmap),
    goal: buildGoalView(dto.week_distance_m, weeklyGoalM, units),
  };
```

(f) Update `useOverview` (lines 103-112) to read the goal from the athlete settings:

```typescript
export function useOverview(period: Period) {
  const { units } = useSettings();
  const { data: athlete } = useAthlete();
  const weeklyGoalM = athlete?.settings.weekly_goal_m;
  return useQuery({
    queryKey: ["activities", "overview", period] as const,
    queryFn: () => fetchOverview(period),
    refetchOnWindowFocus: true,
    refetchInterval: OVERVIEW_REFETCH_INTERVAL_MS,
    select: (dto: OverviewDTO) => toOverview(dto, units, weeklyGoalM),
  });
}
```

- [ ] **Step 6: Run mapper tests + typecheck**

Run: `cd frontend && npx vitest run src/api/overview.test.ts && npx tsc -b`
Expected: PASS; no type errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types/overview.ts frontend/src/api/overview.ts frontend/src/types/athlete.ts frontend/src/api/settings.ts frontend/src/api/overview.test.ts
git commit -m "feat(overview): heatmap + weekly-goal display mapper + DTO types"
```

---

## Task 4: Frontend — WeeklyGoalRing component

**Files:**
- Create: `frontend/src/pages/app-home/components/WeeklyGoalRing.tsx`
- Test: `frontend/src/pages/app-home/components/WeeklyGoalRing.test.tsx`

**Interfaces:**
- Consumes: `GoalView`.
- Produces: `<WeeklyGoalRing goal={GoalView} />`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/pages/app-home/components/WeeklyGoalRing.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WeeklyGoalRing } from "./WeeklyGoalRing";

const goal = {
  pct: 64, pctLabel: "64%", doneLabel: "64.0",
  targetLabel: "100.0", unit: "km", remainingLabel: "36.0",
};

describe("WeeklyGoalRing", () => {
  it("renders the percentage, progress, and remaining", () => {
    render(<WeeklyGoalRing goal={goal} />);
    expect(screen.getByText("64%")).toBeInTheDocument();
    expect(screen.getByText("64.0")).toBeInTheDocument();
    expect(screen.getByText("/ 100.0 km")).toBeInTheDocument();
    expect(screen.getByText("36.0 km to go")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/pages/app-home/components/WeeklyGoalRing.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `frontend/src/pages/app-home/components/WeeklyGoalRing.tsx`:

```typescript
import type { GoalView } from "@/types/overview";

const R = 54;
const CIRC = 2 * Math.PI * R;

/** Radial progress ring: current-week distance against the athlete's weekly goal. */
export function WeeklyGoalRing({ goal }: { goal: GoalView }) {
  const offset = CIRC * (1 - goal.pct / 100);
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-6 flex flex-col items-center justify-center gap-[18px] text-center transition-colors duration-300">
      <div className="flex items-center gap-2 self-start">
        <span className="w-[7px] h-[7px] rounded-[2px] bg-strava flex-none" />
        <span className="font-display font-medium text-[14px] text-ink whitespace-nowrap">Weekly goal</span>
      </div>
      <div className="relative w-[124px] h-[124px] flex-none">
        <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
          <circle cx="60" cy="60" r={R} fill="none" className="stroke-surface-inset" strokeWidth={9} />
          <circle
            cx="60" cy="60" r={R} fill="none" stroke="#fc4c02" strokeWidth={9} strokeLinecap="round"
            strokeDasharray={CIRC} strokeDashoffset={offset}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display font-semibold text-[24px] leading-none text-ink">{goal.pctLabel}</span>
          <span className="font-mono text-[9px] tracking-[0.08em] text-subtle mt-[3px]">OF GOAL</span>
        </div>
      </div>
      <div className="flex flex-col items-center gap-[6px]">
        <div className="flex items-baseline gap-[5px]">
          <span className="font-display font-semibold text-[22px] text-ink">{goal.doneLabel}</span>
          <span className="font-mono text-[11px] text-subtle">/ {goal.targetLabel} {goal.unit}</span>
        </div>
        <div className="font-mono text-[10.5px] text-faint whitespace-nowrap">
          {goal.remainingLabel} {goal.unit} to go
        </div>
      </div>
    </div>
  );
}
```

> The progress arc uses the literal brand orange `#fc4c02` (chart-color exception, as `TrendChart` does). The track uses the `stroke-surface-inset` token utility; all text uses token utilities.

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npx vitest run src/pages/app-home/components/WeeklyGoalRing.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/app-home/components/WeeklyGoalRing.tsx frontend/src/pages/app-home/components/WeeklyGoalRing.test.tsx
git commit -m "feat(overview): WeeklyGoalRing component"
```

---

## Task 5: Frontend — ActivityHeatmap component + dependency

**Files:**
- Modify: `frontend/package.json` (add `react-activity-calendar`)
- Create: `frontend/src/pages/app-home/components/ActivityHeatmap.tsx`
- Test: `frontend/src/pages/app-home/components/ActivityHeatmap.test.tsx`

**Interfaces:**
- Consumes: `HeatmapView`, `Units`, `isDark: boolean`.
- Produces: `<ActivityHeatmap view={HeatmapView} isDark={boolean} units={Units} />`.

- [ ] **Step 1: Install the dependency**

Run: `cd frontend && npm install react-activity-calendar`
Expected: adds `react-activity-calendar` to `dependencies` in `frontend/package.json`.

- [ ] **Step 2: Write the failing test**

Create `frontend/src/pages/app-home/components/ActivityHeatmap.test.tsx` (mock the library — jsdom can't lay it out):

```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ActivityHeatmap } from "./ActivityHeatmap";

vi.mock("react-activity-calendar", () => ({
  ActivityCalendar: (props: { data: unknown[] }) => (
    <div data-testid="calendar" data-len={props.data.length} />
  ),
}));

const view = {
  year: 2026,
  activeDays: 3,
  data: [
    { date: "2026-01-01", count: 0, level: 0 },
    { date: "2026-03-10", count: 12000, level: 2 },
    { date: "2026-12-31", count: 0, level: 0 },
  ],
};

describe("ActivityHeatmap", () => {
  it("renders the active-days header and passes data to the calendar", () => {
    render(<ActivityHeatmap view={view} isDark units="metric" />);
    expect(screen.getByText("2026 · 3 ACTIVE DAYS")).toBeInTheDocument();
    expect(screen.getByTestId("calendar")).toHaveAttribute("data-len", "3");
  });
});
```

- [ ] **Step 3: Run to verify failure**

Run: `cd frontend && npx vitest run src/pages/app-home/components/ActivityHeatmap.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement**

Create `frontend/src/pages/app-home/components/ActivityHeatmap.tsx`:

```typescript
import { cloneElement } from "react";
import { ActivityCalendar } from "react-activity-calendar";
import { distanceLabel, type Units } from "@/lib/units";
import type { HeatmapView } from "@/types/overview";

// Distance ramp (level 0→4). JS literals per the chart-color exception; the empty
// (level-0) cell differs per theme, the saturated steps are theme-invariant.
const THEME = {
  light: ["#ebedf0", "#fcd9c8", "#fba271", "#fc7032", "#fc4c02"],
  dark: ["#1d2127", "#5a2a13", "#8f3d12", "#c44a0d", "#fc4c02"],
};

/** GitHub-style activity calendar for the year, shaded by distance/day. */
export function ActivityHeatmap({
  view, isDark, units,
}: {
  view: HeatmapView;
  isDark: boolean;
  units: Units;
}) {
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-6 transition-colors duration-300">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-[9px]">
          <span className="w-[7px] h-[7px] rounded-[2px] bg-strava flex-none" />
          <span className="font-display font-medium text-[15px] text-ink">Activity</span>
        </div>
        <span className="font-mono text-[11px] text-faint">
          {view.year} · {view.activeDays} ACTIVE DAYS
        </span>
      </div>
      <ActivityCalendar
        data={view.data}
        maxLevel={4}
        colorScheme={isDark ? "dark" : "light"}
        theme={THEME}
        weekStart={0}
        blockSize={11}
        blockMargin={3}
        fontSize={11}
        showWeekdayLabels={["mon", "wed", "fri"]}
        showMonthLabels
        showTotalCount={false}
        labels={{ legend: { less: "Less", more: "More" } }}
        renderBlock={(block, activity) =>
          cloneElement(
            block,
            {},
            <title>{`${distanceLabel(activity.count, units)} on ${activity.date}`}</title>,
          )
        }
      />
    </div>
  );
}
```

> All heatmap colors are JS literals (chart-color exception); the card chrome + header use token utilities. `count` is meters; the `<title>` tooltip formats it with `distanceLabel`.

- [ ] **Step 5: Run to verify pass**

Run: `cd frontend && npx vitest run src/pages/app-home/components/ActivityHeatmap.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/pages/app-home/components/ActivityHeatmap.tsx frontend/src/pages/app-home/components/ActivityHeatmap.test.tsx
git commit -m "feat(overview): ActivityHeatmap (react-activity-calendar)"
```

---

## Task 6: Frontend — compose the new row into AppHome

**Files:**
- Modify: `frontend/src/pages/app-home/AppHome.tsx:31-98`
- Test: `frontend/src/pages/app-home/AppHome.test.tsx:33-75,143-163`

**Interfaces:**
- Consumes: `overview.heatmap` (`HeatmapView`), `overview.goal` (`GoalView`), `ActivityHeatmap`, `WeeklyGoalRing`, `useSettings().units`.

- [ ] **Step 1: Mock the calendar lib, update the fixture, add a render assertion**

First, mock `react-activity-calendar` so the page test is deterministic (jsdom does not provide the sizing primitives the real component uses). Add this `vi.mock` next to the other `vi.mock` calls at the top of `frontend/src/pages/app-home/AppHome.test.tsx` (e.g. after the `@/api/overview` mock, before the `import` of `AppHome`):

```typescript
vi.mock("react-activity-calendar", () => ({
  ActivityCalendar: () => <div data-testid="calendar" />,
}));
```

Next, the `overview` fixture (lines 33-75) must satisfy the extended `DashboardOverview`. Add the two fields before the closing `};` (after `recentRides: [ … ]`):

```typescript
  recentRides: [
    {
      id: 1,
      name: "River loop",
      meta: "Tue · Jun 16 · Ride",
      distLabel: "38.7 km",
      durLabel: "1h 34m",
      isPr: false,
      dotColor: "var(--color-strava)",
    },
  ],
  heatmap: {
    year: 2026,
    activeDays: 3,
    data: [
      { date: "2026-01-01", count: 0, level: 0 },
      { date: "2026-06-16", count: 38700, level: 3 },
      { date: "2026-12-31", count: 0, level: 0 },
    ],
  },
  goal: {
    pct: 64, pctLabel: "64%", doneLabel: "64.0",
    targetLabel: "100.0", unit: "km", remainingLabel: "36.0",
  },
};
```

Then, so the new row is covered, add an assertion to the existing "renders the headline…" test (the `it` at lines 144-154) — append before its closing `});`:

```typescript
    expect(screen.getByText("Weekly goal")).toBeInTheDocument();
    expect(screen.getByText("2026 · 3 ACTIVE DAYS")).toBeInTheDocument();
```

> The active-days header and "Weekly goal" label are rendered by `ActivityHeatmap`/`WeeklyGoalRing` themselves (outside the mocked calendar), so the assertions hold with the lib mocked.

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/pages/app-home/AppHome.test.tsx`
Expected: FAIL — `AppHome` does not yet render `Weekly goal` / the active-days header.

- [ ] **Step 3: Compose the new row in AppHome**

In `frontend/src/pages/app-home/AppHome.tsx`:

(a) Add the component imports alongside the existing component imports (after line 13's `SummaryCard` import):

```typescript
import { ActivityHeatmap } from "./components/ActivityHeatmap";
import { WeeklyGoalRing } from "./components/WeeklyGoalRing";
```

(b) Read `units` from settings — change the destructure (line 34) from:

```typescript
  const { isDark } = useSettings();
```

to:

```typescript
  const { isDark, units } = useSettings();
```

(c) Insert the new row between `<SummaryCard … />` and the lower grid (lines 92-93). Replace:

```typescript
            <SummaryCard summary={overview.summary} />
            <div className="grid grid-cols-[1.55fr_1fr] gap-4 max-[1024px]:grid-cols-1">
```

with:

```typescript
            <SummaryCard summary={overview.summary} />
            <div className="grid grid-cols-[2.7fr_1fr] gap-4 mb-4 max-[1024px]:grid-cols-1">
              <ActivityHeatmap view={overview.heatmap} isDark={isDark} units={units} />
              <WeeklyGoalRing goal={overview.goal} />
            </div>
            <div className="grid grid-cols-[1.55fr_1fr] gap-4 max-[1024px]:grid-cols-1">
```

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npx vitest run src/pages/app-home/AppHome.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/app-home/AppHome.tsx frontend/src/pages/app-home/AppHome.test.tsx
git commit -m "feat(overview): compose heatmap + weekly-goal row into AppHome"
```

---

## Task 7: Frontend — Settings "Goals" input

**Files:**
- Modify: `frontend/src/pages/settings/SettingsPage.tsx:15-74`
- Test: `frontend/src/pages/settings/SettingsPage.test.tsx`

**Interfaces:**
- Consumes: `patchSettings({ weekly_goal_m })`, `distanceToMeters`, `distanceUnit`, `useSettings().units`.

- [ ] **Step 1: Write the failing test**

In `frontend/src/pages/settings/SettingsPage.test.tsx`, add after the Max HR test (line 66):

```typescript
it("typing a weekly goal blurs and patches weekly_goal_m in meters", async () => {
  renderPage();
  const input = screen.getByRole("spinbutton", { name: "Weekly distance goal" });
  fireEvent.change(input, { target: { value: "120" } });
  fireEvent.blur(input);
  // metric default units → 120 km = 120000 m
  await waitFor(() => expect(patchSettings).toHaveBeenCalledWith({ weekly_goal_m: 120000 }));
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/pages/settings/SettingsPage.test.tsx`
Expected: FAIL — no "Weekly distance goal" input.

- [ ] **Step 3: Add the Goals section**

In `frontend/src/pages/settings/SettingsPage.tsx`:

(a) Add the unit helpers — add this import near the other imports (after line 9):

```typescript
import { distanceToMeters, distanceUnit, distanceValue } from "@/lib/units";
```

(b) Read the current goal value below the existing `ftp`/`hrMax` lines (after line 23). `distanceValue` returns the meters converted to the display unit (km/mi), so the input shows the athlete's stored goal in their own units; empty when unset:

```typescript
  const goalMeters = (athlete?.settings as { weekly_goal_m?: number })?.weekly_goal_m;
  const goalDisplay = goalMeters === undefined ? "" : distanceValue(goalMeters, units);
```

(c) Insert a new section card after the "Training zones" section's closing `</div>` (after line 74, before the "Account" section):

```tsx
        <div className={section}>
          <div className={heading}>Goals</div>
          <div className={sub}>Your weekly distance target powers the goal ring on Overview.</div>
          <label className="flex flex-col gap-1 text-[12px] text-subtle">
            Weekly distance goal ({distanceUnit(units)})
            <input
              type="number"
              defaultValue={goalDisplay}
              aria-label="Weekly distance goal"
              onBlur={(e) =>
                e.target.value &&
                patchSettings({ weekly_goal_m: Math.round(distanceToMeters(Number(e.target.value), units)) })
                  .then((updated) => queryClient.setQueryData(["athlete"], updated))
                  .catch(() => {})
              }
              className="w-[120px] bg-surface-inset border border-line rounded-[8px] px-3 py-2 text-ink text-[14px]"
            />
          </label>
        </div>
```

- [ ] **Step 4: Run to verify pass + the full settings suite**

Run: `cd frontend && npx vitest run src/pages/settings/SettingsPage.test.tsx`
Expected: PASS (new test + existing units/FTP/HR/disconnect tests).

- [ ] **Step 5: Full frontend gate**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/settings/SettingsPage.tsx frontend/src/pages/settings/SettingsPage.test.tsx
git commit -m "feat(settings): weekly distance goal input"
```

---

## Final verification

- [ ] **Backend:** `cd backend && pytest -q && ruff check . && mypy` — all green.
- [ ] **Frontend:** `cd frontend && npm test && npm run lint && npm run build` — all green.
- [ ] **Manual smoke (optional, per `peakstats-deployments`):** load `/home`, confirm the heatmap renders the year with month/weekday labels and tooltips, the goal ring shows current-week progress, switching Week/Month/Year leaves both unchanged, and setting a goal on `/settings` updates the ring.
