# Overview Redesign — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Overview page with the new dashboard frame — a Week/Month/Year period selector driving a hero KPI + trend chart, a records summary, a recent-rides list, and a ride-types donut — backed by a period-aware `/activities/overview` endpoint.

**Architecture:** Backend extends the existing single-round-trip `/activities/overview` service to accept a calendar `period` and return period totals, a zero-filled distance trend, summary records, ride-type counts, and recent rides (with PR flag). The frontend maps that DTO into display shapes (units applied in the mapper) and composes new page-local presentational components. Period is in-session React state seeded from `athlete.settings.default_period`.

**Tech Stack:** FastAPI + Pydantic + Supabase (Python client), React 19 + Vite + TypeScript + Tailwind v4 + Recharts, pytest, Vitest + Testing Library.

## Global Constraints

- **Backend layering:** routers → services → db, no layer skipped. Services have no `fastapi` imports; routers translate exceptions and own HTTP. DB modules return their `TypedDict` row shapes. (`backend/CLAUDE.md`)
- **Backend style:** type annotations on every public function; `async def` only when `await` is used (these are all plain `def`); Pydantic for all I/O boundaries. `ruff check .` and `mypy` must be clean.
- **Frontend styling:** use token utilities only — **never raw hex**, never `text-[#..] dark:text-[#..]` pairs. New colors get a var in **both** `:root` and `.dark` in `index.css`, mapped under `@theme inline`. (`frontend/CLAUDE.md`)
- **Frontend structure:** page-only components live in `pages/app-home/components/`; pages compose, components render; data comes from the `api/` layer via a hook; imports use the `@/` alias.
- **Tests must pass before any task is done:** backend `pytest`; frontend `npm test && npm run lint && npm run build`.
- **Scope:** Phase 1 only. No heatmap, weekly goal, zones, top-avg-power, or bikes/gear. Period is seeded but not persisted; no Settings-page control.

---

## File Structure

**Backend**
- Modify `backend/app/models/activities.py` — replace overview schemas: add `Period`, `TrendPoint`, `OverviewSummary`, `RideTypeCount`; rename `WeekTotals`→`PeriodTotals`; remove `WeekDay`; extend `RecentRideItem` with `is_pr`; rewrite `OverviewResponse`.
- Modify `backend/app/db/activities.py` — add `is_pr` to the `ActivityRow` TypedDict.
- Modify `backend/app/services/activities.py` — rewrite `get_overview` to be period-aware; add `_period_bounds`, `_add_month`, `_sub_month`, month/weekday label constants.
- Modify `backend/app/routers/activities.py` — add `period` query param.
- Modify `backend/tests/services/test_activities.py` and `backend/tests/routers/test_activities.py`.

**Frontend**
- Modify `frontend/src/lib/units.ts` — add `distanceValue` + `distanceUnit`.
- Modify `frontend/src/types/overview.ts` — new DTO + display interfaces.
- Modify `frontend/src/api/overview.ts` — `Period`, period-param fetch/hook, new `toOverview`.
- Create `frontend/src/pages/app-home/components/PeriodSelector.tsx`.
- Create `frontend/src/pages/app-home/components/TrendChart.tsx` (replaces `WeekChart`).
- Create `frontend/src/pages/app-home/components/RideTypesDonut.tsx`.
- Create `frontend/src/pages/app-home/components/HeroPanel.tsx`.
- Create `frontend/src/pages/app-home/components/SummaryCard.tsx`.
- Modify `frontend/src/pages/app-home/components/RecentRidesPanel.tsx`.
- Modify `frontend/src/pages/app-home/AppHome.tsx`.
- Modify `frontend/src/index.css` — ride-type palette tokens.
- Delete `frontend/src/components/WeekChart.tsx`, `frontend/src/pages/app-home/components/KpiCards.tsx`, `frontend/src/pages/app-home/components/DistancePanel.tsx`.
- Modify `frontend/src/api/overview.test.ts`, `frontend/src/pages/app-home/AppHome.test.tsx`; create component tests where logic exists.

---

## Task 1: Backend — period-aware overview models + aggregation service

**Files:**
- Modify: `backend/app/models/activities.py:6-36`
- Modify: `backend/app/db/activities.py:7-22` (ActivityRow)
- Modify: `backend/app/services/activities.py:62-128`
- Test: `backend/tests/services/test_activities.py`

**Interfaces:**
- Produces: `Period = Literal["week","month","year"]`; `OverviewResponse(period, this_period, last_period, trend, summary, ride_types, recent_rides)`; `PeriodTotals(distance_m, elev_gain_m, moving_time_s, avg_speed_ms)`; `TrendPoint(label: str, value: float)`; `OverviewSummary(rides: int, prs: int, top_speed_ms: float|None, longest_ride_m: float, max_elev_m: float)`; `RideTypeCount(type: str, count: int)`; `RecentRideItem(..., is_pr: bool)`; `get_overview(supabase, athlete_id, *, tz="UTC", period="week", now=None) -> OverviewResponse`.

- [ ] **Step 1: Rewrite the overview schemas**

In `backend/app/models/activities.py`, replace lines 6-36 (the `SortField`/`SortDir` aliases stay; replace `WeekTotals`, `WeekDay`, `RecentRideItem`, `OverviewResponse`) with:

```python
SortField = Literal["date", "distance", "time", "elevation", "speed"]
SortDir = Literal["asc", "desc"]
Period = Literal["week", "month", "year"]


class PeriodTotals(BaseModel):
    distance_m: float
    elev_gain_m: float
    moving_time_s: int
    avg_speed_ms: float | None


class TrendPoint(BaseModel):
    label: str
    value: float  # distance in meters for the bucket


class OverviewSummary(BaseModel):
    rides: int
    prs: int
    top_speed_ms: float | None
    longest_ride_m: float
    max_elev_m: float


class RideTypeCount(BaseModel):
    type: str
    count: int


class RecentRideItem(BaseModel):
    id: int
    name: str
    type: str
    start_date: str
    start_date_local: str | None = None
    distance_m: float
    moving_time_s: int
    is_pr: bool = False


class OverviewResponse(BaseModel):
    period: Period
    this_period: PeriodTotals
    last_period: PeriodTotals
    trend: list[TrendPoint]
    summary: OverviewSummary
    ride_types: list[RideTypeCount]
    recent_rides: list[RecentRideItem]
```

- [ ] **Step 2: Add `is_pr` to the activity row shape**

In `backend/app/db/activities.py`, add to the `ActivityRow` TypedDict (after `summary_polyline`, alongside the existing `created_at: NotRequired[str]`):

```python
    is_pr: NotRequired[bool]
```

- [ ] **Step 3: Write the failing service tests**

Replace the body of `backend/tests/services/test_activities.py` with:

```python
from datetime import UTC, datetime

from app.services import activities as activities_service

NOW = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)  # Wednesday; week of Mon 2026-06-15


def _row(id, date_local, dist, time, elev, speed, type="Ride", is_pr=False):
    return {
        "id": id, "athlete_id": 7, "name": f"Ride {id}", "type": type,
        "start_date": date_local + "Z", "start_date_local": date_local,
        "distance_m": dist, "moving_time_s": time, "elapsed_time_s": time,
        "elev_gain_m": elev, "avg_speed_ms": speed, "avg_hr": None,
        "summary_polyline": None, "is_pr": is_pr,
    }


THIS_WEEK = [
    _row(1, "2026-06-16T10:00:00", 10000.0, 1000, 100.0, 10.0),
    _row(2, "2026-06-17T09:00:00", 20000.0, 2000, 50.0, 8.0, type="VirtualRide", is_pr=True),
]
LAST_WEEK = [_row(3, "2026-06-10T10:00:00", 5000.0, 500, 10.0, 6.0)]


def _patch(monkeypatch, since_rows, recent_rows):
    monkeypatch.setattr(activities_service.activities_db, "list_activities_since",
                        lambda supabase, athlete_id, since_iso: since_rows)
    monkeypatch.setattr(activities_service.activities_db, "list_recent_activities",
                        lambda supabase, athlete_id, limit: recent_rows)


def test_week_totals_and_deltas(monkeypatch):
    _patch(monkeypatch, THIS_WEEK + LAST_WEEK, THIS_WEEK)
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.period == "week"
    assert ov.this_period.distance_m == 30000.0
    assert ov.this_period.elev_gain_m == 150.0
    assert ov.this_period.moving_time_s == 3000
    assert ov.this_period.avg_speed_ms == 10.0  # 30000m / 3000s
    assert ov.last_period.distance_m == 5000.0


def test_week_trend_buckets_by_weekday(monkeypatch):
    _patch(monkeypatch, THIS_WEEK + LAST_WEEK, [])
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert [p.label for p in ov.trend] == ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    by_label = {p.label: p.value for p in ov.trend}
    assert by_label["TUE"] == 10000.0
    assert by_label["WED"] == 20000.0
    assert by_label["MON"] == 0.0


def test_summary_and_ride_types(monkeypatch):
    _patch(monkeypatch, THIS_WEEK + LAST_WEEK, [])
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.summary.rides == 2
    assert ov.summary.prs == 1
    assert ov.summary.top_speed_ms == 10.0
    assert ov.summary.longest_ride_m == 20000.0
    assert ov.summary.max_elev_m == 100.0
    assert {rt.type: rt.count for rt in ov.ride_types} == {"Ride": 1, "VirtualRide": 1}


def test_recent_rides_include_pr_flag(monkeypatch):
    _patch(monkeypatch, [], THIS_WEEK)
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert [r.id for r in ov.recent_rides] == [1, 2]
    assert ov.recent_rides[1].is_pr is True
    assert ov.recent_rides[0].is_pr is False


def test_month_trend_is_daily_for_calendar_month(monkeypatch):
    rows = [_row(1, "2026-06-01T10:00:00", 5000.0, 600, 0.0, 8.0),
            _row(2, "2026-05-31T10:00:00", 9000.0, 600, 0.0, 8.0)]  # last month
    _patch(monkeypatch, rows, [])
    ov = activities_service.get_overview(object(), 7, period="month", now=NOW)
    assert len(ov.trend) == 30          # June has 30 days
    assert ov.trend[0].label == "1"
    assert ov.trend[0].value == 5000.0
    assert ov.this_period.distance_m == 5000.0
    assert ov.last_period.distance_m == 9000.0


def test_year_trend_is_twelve_months(monkeypatch):
    rows = [_row(1, "2026-06-16T10:00:00", 10000.0, 1000, 0.0, 8.0),
            _row(2, "2025-06-16T10:00:00", 3000.0, 1000, 0.0, 8.0)]  # last year
    _patch(monkeypatch, rows, [])
    ov = activities_service.get_overview(object(), 7, period="year", now=NOW)
    assert [p.label for p in ov.trend] == ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                                           "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    assert ov.trend[5].value == 10000.0  # JUN
    assert ov.this_period.distance_m == 10000.0
    assert ov.last_period.distance_m == 3000.0


def test_empty_is_safe(monkeypatch):
    _patch(monkeypatch, [], [])
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.this_period.distance_m == 0.0
    assert ov.this_period.avg_speed_ms is None
    assert ov.summary.rides == 0
    assert ov.summary.top_speed_ms is None
    assert ov.summary.longest_ride_m == 0.0
    assert ov.ride_types == []
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `cd backend && pytest tests/services/test_activities.py -q`
Expected: FAIL — `get_overview()` doesn't accept `period`, and `ov.this_period`/`ov.trend`/`ov.summary` don't exist yet.

- [ ] **Step 5: Rewrite the service**

In `backend/app/services/activities.py`: update the model import block (lines 11-25) to import the new names — replace `OverviewResponse, RecentRideItem, ... WeekDay, WeekTotals` so the import list includes `OverviewResponse, OverviewSummary, Period, PeriodTotals, RecentRideItem, RideTypeCount, TrendPoint` (drop `WeekDay`, `WeekTotals`; keep the rest). Then replace the label constant and `_totals`/`get_overview` (lines 41, 62-128) with:

```python
_WEEKDAY_LABELS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
_MONTH_LABELS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                 "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _totals(rows: list[ActivityRow]) -> PeriodTotals:
    distance_m = sum(r["distance_m"] for r in rows)
    moving_time_s = sum(r["moving_time_s"] for r in rows)
    return PeriodTotals(
        distance_m=distance_m,
        elev_gain_m=sum(r["elev_gain_m"] for r in rows),
        moving_time_s=moving_time_s,
        avg_speed_ms=distance_m / moving_time_s if moving_time_s > 0 else None,
    )


def _add_month(d: datetime) -> datetime:
    return d.replace(year=d.year + 1, month=1) if d.month == 12 else d.replace(month=d.month + 1)


def _sub_month(d: datetime) -> datetime:
    return d.replace(year=d.year - 1, month=12) if d.month == 1 else d.replace(month=d.month - 1)


def _period_bounds(base: datetime, period: Period) -> tuple[datetime, datetime, datetime]:
    """Return (this_start, this_end, last_start) for the calendar period containing `base`.

    `base` is midnight of the current local day. Bounds are half-open [start, end).
    """
    if period == "week":
        this_start = base - timedelta(days=base.weekday())
        return this_start, this_start + timedelta(days=7), this_start - timedelta(days=7)
    if period == "month":
        this_start = base.replace(day=1)
        return this_start, _add_month(this_start), _sub_month(this_start)
    this_start = base.replace(month=1, day=1)  # year
    return this_start, this_start.replace(year=this_start.year + 1), this_start.replace(year=this_start.year - 1)


def _trend(rows: list[ActivityRow], this_start: datetime, this_end: datetime, period: Period) -> list[TrendPoint]:
    if period == "year":
        totals = [0.0] * 12
        for r in rows:
            totals[_local_naive(r).month - 1] += r["distance_m"]
        return [TrendPoint(label=_MONTH_LABELS[i], value=round(totals[i], 1)) for i in range(12)]

    n_days = (this_end.date() - this_start.date()).days
    totals = [0.0] * n_days
    for r in rows:
        idx = (_local_naive(r).date() - this_start.date()).days
        if 0 <= idx < n_days:
            totals[idx] += r["distance_m"]
    if period == "week":
        labels = _WEEKDAY_LABELS
    else:  # month — day-of-month numbers
        labels = [str((this_start.date() + timedelta(days=i)).day) for i in range(n_days)]
    return [TrendPoint(label=labels[i], value=round(totals[i], 1)) for i in range(n_days)]


def _summary(rows: list[ActivityRow]) -> OverviewSummary:
    speeds = [r["avg_speed_ms"] for r in rows if r["avg_speed_ms"] is not None]
    return OverviewSummary(
        rides=len(rows),
        prs=sum(1 for r in rows if r.get("is_pr")),
        top_speed_ms=max(speeds) if speeds else None,
        longest_ride_m=max((r["distance_m"] for r in rows), default=0.0),
        max_elev_m=max((r["elev_gain_m"] for r in rows), default=0.0),
    )


def _ride_types(rows: list[ActivityRow]) -> list[RideTypeCount]:
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["type"]] = counts.get(r["type"], 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [RideTypeCount(type=t, count=c) for t, c in ordered]


def get_overview(
    supabase: Client,
    athlete_id: int,
    *,
    tz: str = "UTC",
    period: Period = "week",
    now: datetime | None = None,
) -> OverviewResponse:
    zone = _resolve_tz(tz)
    now_local = (now or datetime.now(UTC)).astimezone(zone)
    base = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    this_start, this_end, last_start = _period_bounds(base, period)

    # Rows are queried by UTC start_date, which can sit up to ~14h off the local
    # date, so widen the query a day and filter precisely by local time below.
    rows = activities_db.list_activities_since(
        supabase, athlete_id, (last_start - timedelta(days=1)).isoformat()
    )

    ts, te, ls = (
        this_start.replace(tzinfo=None),
        this_end.replace(tzinfo=None),
        last_start.replace(tzinfo=None),
    )
    this_rows = [r for r in rows if ts <= _local_naive(r) < te]
    last_rows = [r for r in rows if ls <= _local_naive(r) < ts]

    recent = activities_db.list_recent_activities(supabase, athlete_id, RECENT_LIMIT)
    recent_rides = [
        RecentRideItem(
            id=r["id"], name=r["name"], type=r["type"], start_date=r["start_date"],
            start_date_local=r.get("start_date_local"), distance_m=r["distance_m"],
            moving_time_s=r["moving_time_s"], is_pr=bool(r.get("is_pr")),
        )
        for r in recent
    ]

    return OverviewResponse(
        period=period,
        this_period=_totals(this_rows),
        last_period=_totals(last_rows),
        trend=_trend(this_rows, this_start, this_end, period),
        summary=_summary(this_rows),
        ride_types=_ride_types(this_rows),
        recent_rides=recent_rides,
    )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && pytest tests/services/test_activities.py -q`
Expected: PASS (all 7 tests).

- [ ] **Step 7: Lint, type-check, commit**

Run: `cd backend && ruff check . && mypy`
Expected: clean.

```bash
git add backend/app/models/activities.py backend/app/db/activities.py backend/app/services/activities.py backend/tests/services/test_activities.py
git commit -m "feat(overview): period-aware aggregation service + schemas"
```

---

## Task 2: Backend — wire the `period` query param

**Files:**
- Modify: `backend/app/routers/activities.py:7-14,41-47`
- Test: `backend/tests/routers/test_activities.py`

**Interfaces:**
- Consumes: `activities_service.get_overview(..., period=...)`, `OverviewResponse`, `Period`.
- Produces: `GET /activities/overview?tz=&period=` returning `OverviewResponse`.

- [ ] **Step 1: Write the failing router test**

Add to `backend/tests/routers/test_activities.py` (follow the file's existing service-boundary mocking style — patch `activities_service.get_overview`):

```python
def test_overview_passes_period(client, monkeypatch):
    captured = {}

    def fake_overview(supabase, athlete_id, *, tz="UTC", period="week", now=None):
        captured["tz"] = tz
        captured["period"] = period
        from app.models.activities import OverviewResponse, OverviewSummary, PeriodTotals
        zero = PeriodTotals(distance_m=0, elev_gain_m=0, moving_time_s=0, avg_speed_ms=None)
        return OverviewResponse(
            period=period, this_period=zero, last_period=zero, trend=[],
            summary=OverviewSummary(rides=0, prs=0, top_speed_ms=None,
                                    longest_ride_m=0, max_elev_m=0),
            ride_types=[], recent_rides=[],
        )

    monkeypatch.setattr("app.routers.activities.activities_service.get_overview", fake_overview)
    resp = client.get("/activities/overview?tz=UTC&period=month")
    assert resp.status_code == 200
    assert captured["period"] == "month"
    assert resp.json()["period"] == "month"


def test_overview_defaults_to_week(client, monkeypatch):
    captured = {}

    def fake_overview(supabase, athlete_id, *, tz="UTC", period="week", now=None):
        captured["period"] = period
        from app.models.activities import OverviewResponse, OverviewSummary, PeriodTotals
        zero = PeriodTotals(distance_m=0, elev_gain_m=0, moving_time_s=0, avg_speed_ms=None)
        return OverviewResponse(
            period=period, this_period=zero, last_period=zero, trend=[],
            summary=OverviewSummary(rides=0, prs=0, top_speed_ms=None,
                                    longest_ride_m=0, max_elev_m=0),
            ride_types=[], recent_rides=[],
        )

    monkeypatch.setattr("app.routers.activities.activities_service.get_overview", fake_overview)
    resp = client.get("/activities/overview")
    assert resp.status_code == 200
    assert captured["period"] == "week"
```

> The `client` fixture auth-stubs `get_current_athlete_id`/`get_supabase` the same way the existing overview test in this file does — reuse that file's existing setup; do not add new auth plumbing.

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/routers/test_activities.py -k overview -q`
Expected: FAIL — `period` is not accepted / not forwarded.

- [ ] **Step 3: Add the param to the router**

In `backend/app/routers/activities.py`, add `Period` to the model import (line 7-14 block) and update the overview route (lines 41-47):

```python
@router.get("/overview", response_model=OverviewResponse)
def overview(
    tz: str = Query("UTC"),
    period: Period = Query("week"),
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: Client = Depends(get_supabase),
) -> OverviewResponse:
    return activities_service.get_overview(supabase, athlete_id, tz=tz, period=period)
```

(FastAPI validates `period` against the `Literal` and returns 422 for unknown values, so no manual fallback is needed.)

- [ ] **Step 4: Run to verify pass + full backend suite**

Run: `cd backend && pytest -q && ruff check . && mypy`
Expected: all pass, lint/types clean.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/activities.py backend/tests/routers/test_activities.py
git commit -m "feat(overview): accept period query param on /activities/overview"
```

---

## Task 3: Frontend — units helper, DTO types, and the display mapper

**Files:**
- Modify: `frontend/src/lib/units.ts`
- Modify: `frontend/src/types/overview.ts`
- Modify: `frontend/src/api/overview.ts`
- Test: `frontend/src/api/overview.test.ts`

**Interfaces:**
- Produces: `Period = "week"|"month"|"year"`; `OverviewDTO`; display type `DashboardOverview` with `{ period, headline, secondary, trend, trendUnit, summary, rideTypes, recentRides }`; `toOverview(dto, units) -> DashboardOverview`; `fetchOverview(period) -> Promise<OverviewDTO>`; `useOverview(period)`; `distanceValue(meters, units) -> number`, `distanceUnit(units) -> string`.
- Consumes (downstream): `DashRide` gains `isPr: boolean` and `dotColor: string`.

- [ ] **Step 1: Write the failing mapper tests**

Replace `frontend/src/api/overview.test.ts` with:

```typescript
import { describe, expect, it } from "vitest";
import type { OverviewDTO } from "@/types/overview";
import { toOverview } from "./overview";

const DTO: OverviewDTO = {
  period: "week",
  this_period: { distance_m: 30000, elev_gain_m: 1240, moving_time_s: 22320, avg_speed_ms: 6.889 },
  last_period: { distance_m: 25000, elev_gain_m: 1200, moving_time_s: 20000, avg_speed_ms: 6.0 },
  trend: [
    { label: "MON", value: 14800 },
    { label: "SUN", value: 38700 },
  ],
  summary: { rides: 6, prs: 2, top_speed_ms: 11.0, longest_ride_m: 64000, max_elev_m: 980 },
  ride_types: [
    { type: "Ride", count: 4 },
    { type: "VirtualRide", count: 1 },
  ],
  recent_rides: [
    { id: 1, name: "River loop", type: "Ride", start_date: "2026-06-16T07:42:00Z",
      start_date_local: "2026-06-16T07:42:00Z", distance_m: 38700, moving_time_s: 5662, is_pr: true },
  ],
};

describe("toOverview", () => {
  it("builds the headline KPI with period-aware labels and delta", () => {
    const { headline } = toOverview(DTO, "metric");
    expect(headline).toMatchObject({
      label: "DISTANCE", periodLabel: "THIS WEEK", value: "30.0", unit: "km",
      delta: "+20%", deltaPositive: true, deltaCaption: "vs last week",
    });
  });

  it("builds three secondary KPIs", () => {
    const { secondary } = toOverview(DTO, "metric");
    expect(secondary.map((k) => k.label)).toEqual(["MOVING TIME", "ELEVATION", "AVG SPEED"]);
    expect(secondary[2]).toMatchObject({ value: "24.8", unit: "km/h" });
  });

  it("converts trend values to display distance units", () => {
    const { trend, trendUnit } = toOverview(DTO, "metric");
    expect(trendUnit).toBe("km");
    expect(trend).toEqual([{ label: "MON", value: 14.8 }, { label: "SUN", value: 38.7 }]);
  });

  it("formats summary records", () => {
    const { summary } = toOverview(DTO, "metric");
    expect(summary).toMatchObject({
      rides: "6", prs: "2", topSpeed: "11.0 km/h",
      longestRide: "64.0 km", maxElev: "980 m",
    });
  });

  it("assigns percentages and colors to ride types", () => {
    const { rideTypes } = toOverview(DTO, "metric");
    expect(rideTypes.total).toBe(5);
    expect(rideTypes.items[0]).toMatchObject({ type: "Ride", pct: "80%" });
    expect(rideTypes.items[0].color).not.toEqual(rideTypes.items[1].color);
  });

  it("maps recent rides with PR flag and a dot color", () => {
    const { recentRides } = toOverview(DTO, "metric");
    expect(recentRides[0]).toMatchObject({ id: 1, name: "River loop", isPr: true });
    expect(recentRides[0].distLabel).toBe("38.7 km");
    expect(typeof recentRides[0].dotColor).toBe("string");
  });

  it("imperial summary uses miles", () => {
    const { summary } = toOverview(DTO, "imperial");
    expect(summary.longestRide).toBe("39.8 mi");
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/api/overview.test.ts`
Expected: FAIL — `toOverview` returns the old `{ kpis, week, recentRides }` shape.

- [ ] **Step 3: Add unit converters**

Append to `frontend/src/lib/units.ts`:

```typescript
/** Numeric distance in display units (km or mi), rounded to 1 decimal — for charts. */
export function distanceValue(meters: number, units: Units): number {
  return Math.round((meters / (units === "imperial" ? M_PER_MILE : 1000)) * 10) / 10;
}

/** The distance unit label for the given system, e.g. "km" / "mi". */
export function distanceUnit(units: Units): string {
  return units === "imperial" ? "mi" : "km";
}
```

- [ ] **Step 4: Replace the overview types**

Replace `frontend/src/types/overview.ts` with:

```typescript
export type Period = "week" | "month" | "year";

export interface PeriodTotalsDTO {
  distance_m: number;
  elev_gain_m: number;
  moving_time_s: number;
  avg_speed_ms: number | null;
}

export interface TrendPointDTO {
  label: string;
  value: number; // distance in meters
}

export interface OverviewSummaryDTO {
  rides: number;
  prs: number;
  top_speed_ms: number | null;
  longest_ride_m: number;
  max_elev_m: number;
}

export interface RideTypeCountDTO {
  type: string;
  count: number;
}

export interface RecentRideDTO {
  id: number;
  name: string;
  type: string;
  start_date: string;
  start_date_local: string | null;
  distance_m: number;
  moving_time_s: number;
  is_pr: boolean;
}

export interface OverviewDTO {
  period: Period;
  this_period: PeriodTotalsDTO;
  last_period: PeriodTotalsDTO;
  trend: TrendPointDTO[];
  summary: OverviewSummaryDTO;
  ride_types: RideTypeCountDTO[];
  recent_rides: RecentRideDTO[];
}

/** Display shapes the Overview renders (formatted, units applied). */
export interface Kpi {
  label: string;
  value: string;
  unit: string;
  delta: string;
  deltaPositive: boolean;
}

export interface HeadlineKpi extends Kpi {
  periodLabel: string;   // "THIS WEEK" | "THIS MONTH" | "THIS YEAR"
  deltaCaption: string;  // "vs last week" | ...
}

export interface TrendPoint {
  label: string;
  value: number; // display distance units
}

export interface SummaryView {
  rides: string;
  prs: string;
  topSpeed: string;     // "11.0 km/h" or "—"
  longestRide: string;  // "64.0 km"
  maxElev: string;      // "980 m"
}

export interface RideTypeSlice {
  type: string;
  label: string;
  pct: string;       // "80%"
  fraction: number;  // 0..1
  color: string;     // CSS color (var(...))
}

export interface RideTypesView {
  total: number;
  items: RideTypeSlice[];
}

export interface DashRide {
  id: number;
  name: string;
  meta: string;       // "Tue · Jun 16 · Ride"
  distLabel: string;
  durLabel: string;
  isPr: boolean;
  dotColor: string;
}

export interface DashboardOverview {
  period: Period;
  headline: HeadlineKpi;
  secondary: Kpi[];
  trend: TrendPoint[];
  trendUnit: string;
  summary: SummaryView;
  rideTypes: RideTypesView;
  recentRides: DashRide[];
}
```

- [ ] **Step 5: Rewrite the mapper + hook**

Replace `frontend/src/api/overview.ts` with:

```typescript
import { useQuery } from "@tanstack/react-query";
import type {
  DashboardOverview, DashRide, Kpi, OverviewDTO, Period,
  RecentRideDTO, RideTypeSlice,
} from "@/types/overview";
import { apiFetch } from "./client";
import { fmtDate, fmtDuration } from "@/lib/format";
import { useSettings } from "@/app/providers/settings-context";
import {
  distanceLabel, distanceUnit, distanceValue, elevationLabel, fmtDistance,
  fmtElevation, fmtSpeed, speedLabel, type Units,
} from "@/lib/units";

/** Ride-type palette — CSS vars defined in index.css (both themes). */
const TYPE_COLORS = [
  "var(--color-strava)", "var(--color-cat-2)", "var(--color-cat-3)",
  "var(--color-cat-4)", "var(--color-cat-5)",
];
const DEFAULT_DOT = "var(--color-strava)";

const PERIOD_NOUN: Record<Period, string> = { week: "week", month: "month", year: "year" };

function delta(current: number, previous: number): Pick<Kpi, "delta" | "deltaPositive"> {
  if (previous <= 0) return { delta: "—", deltaPositive: true };
  const pct = Math.round(((current - previous) / previous) * 100);
  return { delta: `${pct >= 0 ? "+" : ""}${pct}%`, deltaPositive: pct >= 0 };
}

function toRide(r: RecentRideDTO, units: Units, colorByType: Map<string, string>): DashRide {
  return {
    id: r.id,
    name: r.name,
    meta: `${fmtDate(r.start_date_local ?? r.start_date)} · ${r.type}`,
    distLabel: distanceLabel(r.distance_m, units),
    durLabel: fmtDuration(r.moving_time_s),
    isPr: r.is_pr,
    dotColor: colorByType.get(r.type) ?? DEFAULT_DOT,
  };
}

export function toOverview(dto: OverviewDTO, units: Units): DashboardOverview {
  const t = dto.this_period;
  const l = dto.last_period;
  const noun = PERIOD_NOUN[dto.period];

  const dist = fmtDistance(t.distance_m, units);
  const headline = {
    label: "DISTANCE",
    periodLabel: `THIS ${noun.toUpperCase()}`,
    value: dist.value,
    unit: dist.unit,
    deltaCaption: `vs last ${noun}`,
    ...delta(t.distance_m, l.distance_m),
  };

  const elev = fmtElevation(t.elev_gain_m, units);
  const thisSpeed = t.avg_speed_ms ?? 0;
  const lastSpeed = l.avg_speed_ms ?? 0;
  const speed = fmtSpeed(thisSpeed, units);
  const secondary: Kpi[] = [
    { label: "MOVING TIME", value: fmtDuration(t.moving_time_s), unit: "", ...delta(t.moving_time_s, l.moving_time_s) },
    { label: "ELEVATION", value: elev.value, unit: elev.unit, ...delta(t.elev_gain_m, l.elev_gain_m) },
    { label: "AVG SPEED", value: t.avg_speed_ms === null ? "—" : speed.value, unit: speed.unit, ...delta(thisSpeed, lastSpeed) },
  ];

  const total = dto.ride_types.reduce((sum, rt) => sum + rt.count, 0);
  const items: RideTypeSlice[] = dto.ride_types.map((rt, i) => ({
    type: rt.type,
    label: rt.type,
    pct: total > 0 ? `${Math.round((rt.count / total) * 100)}%` : "0%",
    fraction: total > 0 ? rt.count / total : 0,
    color: TYPE_COLORS[i % TYPE_COLORS.length],
  }));
  const colorByType = new Map(items.map((it) => [it.type, it.color]));

  return {
    period: dto.period,
    headline,
    secondary,
    trend: dto.trend.map((p) => ({ label: p.label, value: distanceValue(p.value, units) })),
    trendUnit: distanceUnit(units),
    summary: {
      rides: String(dto.summary.rides),
      prs: String(dto.summary.prs),
      topSpeed: dto.summary.top_speed_ms === null ? "—" : speedLabel(dto.summary.top_speed_ms, units),
      longestRide: distanceLabel(dto.summary.longest_ride_m, units),
      maxElev: elevationLabel(dto.summary.max_elev_m, units),
    },
    rideTypes: { total, items },
    recentRides: dto.recent_rides.map((r) => toRide(r, units, colorByType)),
  };
}

export function fetchOverview(period: Period): Promise<OverviewDTO> {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  return apiFetch<OverviewDTO>(
    `/activities/overview?tz=${encodeURIComponent(tz)}&period=${period}`,
  );
}

export const OVERVIEW_REFETCH_INTERVAL_MS = 60_000;

export function useOverview(period: Period) {
  const { units } = useSettings();
  return useQuery({
    queryKey: ["activities", "overview", period] as const,
    queryFn: () => fetchOverview(period),
    refetchOnWindowFocus: true,
    refetchInterval: OVERVIEW_REFETCH_INTERVAL_MS,
    select: (dto: OverviewDTO) => toOverview(dto, units),
  });
}
```

- [ ] **Step 6: Run mapper tests + typecheck**

Run: `cd frontend && npx vitest run src/api/overview.test.ts && npx tsc -b`
Expected: PASS; no type errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/units.ts frontend/src/types/overview.ts frontend/src/api/overview.ts frontend/src/api/overview.test.ts
git commit -m "feat(overview): period DTO types + display mapper"
```

---

## Task 4: Frontend — PeriodSelector component

**Files:**
- Create: `frontend/src/pages/app-home/components/PeriodSelector.tsx`
- Test: `frontend/src/pages/app-home/components/PeriodSelector.test.tsx`

**Interfaces:**
- Produces: `<PeriodSelector value={Period} onChange={(p: Period) => void} />`.

- [ ] **Step 1: Write the failing test**

Create `PeriodSelector.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PeriodSelector } from "./PeriodSelector";

describe("PeriodSelector", () => {
  it("renders the three periods and marks the active one", () => {
    render(<PeriodSelector value="month" onChange={() => {}} />);
    const active = screen.getByRole("button", { name: "Month" });
    expect(active).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Week" })).toHaveAttribute("aria-pressed", "false");
  });

  it("calls onChange with the chosen period", async () => {
    const onChange = vi.fn();
    render(<PeriodSelector value="week" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Year" }));
    expect(onChange).toHaveBeenCalledWith("year");
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/pages/app-home/components/PeriodSelector.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `PeriodSelector.tsx`:

```typescript
import type { Period } from "@/types/overview";

const OPTIONS: { value: Period; label: string }[] = [
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
  { value: "year", label: "Year" },
];

/** Segmented Week/Month/Year control for the Overview header. */
export function PeriodSelector({
  value,
  onChange,
}: {
  value: Period;
  onChange: (period: Period) => void;
}) {
  return (
    <div className="flex gap-[3px] bg-surface-inset border border-line rounded-[10px] p-[3px]">
      {OPTIONS.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(o.value)}
            className={`px-[13px] h-[30px] rounded-[7px] font-mono text-[11px] cursor-pointer transition-colors ${
              active ? "bg-surface-card text-ink" : "text-subtle hover:text-ink"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npx vitest run src/pages/app-home/components/PeriodSelector.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/app-home/components/PeriodSelector.tsx frontend/src/pages/app-home/components/PeriodSelector.test.tsx
git commit -m "feat(overview): PeriodSelector segmented control"
```

---

## Task 5: Frontend — TrendChart (replaces WeekChart)

**Files:**
- Create: `frontend/src/pages/app-home/components/TrendChart.tsx`
- Delete: `frontend/src/components/WeekChart.tsx`
- Test: `frontend/src/pages/app-home/components/TrendChart.test.tsx`

**Interfaces:**
- Consumes: `TrendPoint[]` (`{ label, value }`), `isDark`, `unit`.
- Produces: `<TrendChart points={TrendPoint[]} unit={string} isDark={boolean} />`.

- [ ] **Step 1: Write the failing test**

Create `TrendChart.test.tsx` (Recharts needs width; mock `ResponsiveContainer` to a fixed size as the repo does for `WeekChart` — if no such helper exists, assert on the rendered SVG path count via `container`):

```typescript
import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TrendChart } from "./TrendChart";

// Recharts ResponsiveContainer renders nothing at 0x0 in jsdom; force a size.
vi.mock("recharts", async (importOriginal) => {
  const actual = await importOriginal<typeof import("recharts")>();
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <actual.ResponsiveContainer width={600} height={180}>{children}</actual.ResponsiveContainer>
    ),
  };
});

describe("TrendChart", () => {
  it("renders an area path for the provided points", () => {
    const { container } = render(
      <TrendChart unit="km" isDark points={[{ label: "MON", value: 1 }, { label: "TUE", value: 4 }]} />,
    );
    expect(container.querySelector("svg")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/pages/app-home/components/TrendChart.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement TrendChart**

Create `TrendChart.tsx` (generalizes `WeekChart`; reuse the `edgeTickAnchor` helper that already lives in `@/components/edge-tick-anchor`):

```typescript
import { Area, AreaChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { edgeTickAnchor } from "@/components/edge-tick-anchor";
import type { TrendPoint } from "@/types/overview";

type TickProps = {
  x?: number; y?: number; index?: number; visibleTicksCount?: number;
  payload?: { value?: string | number }; fill?: string;
};

function LabelTick({ x = 0, y = 0, index = 0, visibleTicksCount = 1, payload, fill }: TickProps) {
  return (
    <text x={x} y={y} dy="0.71em" textAnchor={edgeTickAnchor(index, visibleTicksCount)}
      fontFamily="'JetBrains Mono', monospace" fontSize={11} fill={fill}>
      {payload?.value}
    </text>
  );
}

/** Distance trend (area+line) for the selected period. */
export function TrendChart({
  points, unit, isDark,
}: {
  points: TrendPoint[];
  unit: string;
  isDark: boolean;
}) {
  const tick = isDark ? "#6b7280" : "#8a909a";
  // Avoid crowding day-level labels on the month view.
  const interval = points.length > 12 ? Math.floor(points.length / 8) : 0;
  return (
    <ResponsiveContainer width="100%" height={180}>
      <AreaChart data={points} margin={{ top: 8, right: 6, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fc4c02" stopOpacity={0.28} />
            <stop offset="100%" stopColor="#fc4c02" stopOpacity={0} />
          </linearGradient>
        </defs>
        <YAxis
          width={40} axisLine={false} tickLine={false}
          tick={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, fill: tick }}
          tickFormatter={(v: number) => `${v}`}
          unit={` ${unit}`}
        />
        <XAxis
          dataKey="label" axisLine={false} tickLine={false} interval={interval}
          tick={<LabelTick fill={tick} />}
        />
        <Area
          type="monotone" dataKey="value" stroke="#fc4c02" strokeWidth={2.5}
          fill="url(#trendFill)" dot={false}
          activeDot={{ r: 4.5, fill: "#fc4c02", strokeWidth: 2.5, stroke: isDark ? "#13161c" : "#fff" }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
```

> Recharts chart colors stay as JS literals here, per the frontend styling contract (the same exception `WeekChart` used).

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npx vitest run src/pages/app-home/components/TrendChart.test.tsx`
Expected: PASS.

- [ ] **Step 5: Delete the old WeekChart**

```bash
git rm frontend/src/components/WeekChart.tsx
```

(`DistancePanel.tsx` is the only importer and is removed in Task 9; `edgeTickAnchor` + its test stay.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/app-home/components/TrendChart.tsx frontend/src/pages/app-home/components/TrendChart.test.tsx
git commit -m "feat(overview): generalized TrendChart, retire WeekChart"
```

---

## Task 6: Frontend — RideTypesDonut component

**Files:**
- Modify: `frontend/src/index.css` (palette tokens)
- Create: `frontend/src/pages/app-home/components/RideTypesDonut.tsx`
- Test: `frontend/src/pages/app-home/components/RideTypesDonut.test.tsx`

**Interfaces:**
- Consumes: `RideTypesView` (`{ total, items: RideTypeSlice[] }`).
- Produces: `<RideTypesDonut data={RideTypesView} />`; exported pure helper `donutSegments(items) -> { color, dashArray, dashOffset }[]`.

- [ ] **Step 1: Add palette tokens**

In `frontend/src/index.css`, add these vars to **both** the `:root` and `.dark` blocks (theme-invariant saturated values — same in both), then map them under `@theme inline`:

```css
/* in :root AND .dark (identical values): */
--cat-2: #3b82f6;
--cat-3: #22c55e;
--cat-4: #a855f7;
--cat-5: #eab308;
```

```css
/* under @theme inline { ... } : */
--color-cat-2: var(--cat-2);
--color-cat-3: var(--cat-3);
--color-cat-4: var(--cat-4);
--color-cat-5: var(--cat-5);
```

(`--color-strava` already exists and is `cat-1`.)

- [ ] **Step 2: Write the failing test**

Create `RideTypesDonut.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RideTypesDonut, donutSegments } from "./RideTypesDonut";

const DATA = {
  total: 5,
  items: [
    { type: "Ride", label: "Ride", pct: "80%", fraction: 0.8, color: "var(--color-strava)" },
    { type: "VirtualRide", label: "VirtualRide", pct: "20%", fraction: 0.2, color: "var(--color-cat-2)" },
  ],
};

describe("donutSegments", () => {
  it("produces cumulative dash offsets that don't overlap", () => {
    const segs = donutSegments(DATA.items);
    expect(segs).toHaveLength(2);
    expect(segs[0].dashOffset).toBe(0);
    // second segment starts where the first ends (negative offset = clockwise)
    expect(segs[1].dashOffset).toBeCloseTo(-0.8 * segs[0].circumference, 3);
  });
});

describe("RideTypesDonut", () => {
  it("renders the legend with labels and percentages", () => {
    render(<RideTypesDonut data={DATA} />);
    expect(screen.getByText("Ride")).toBeInTheDocument();
    expect(screen.getByText("80%")).toBeInTheDocument();
    expect(screen.getByText("5 TOTAL")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run to verify failure**

Run: `cd frontend && npx vitest run src/pages/app-home/components/RideTypesDonut.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement**

Create `RideTypesDonut.tsx`:

```typescript
import type { RideTypeSlice, RideTypesView } from "@/types/overview";

const R = 80;
const CIRC = 2 * Math.PI * R;

export interface DonutSegment {
  color: string;
  circumference: number;
  dashArray: string;
  dashOffset: number;
}

/** Stacked-circle donut segments: each slice is an arc via stroke-dasharray. */
export function donutSegments(items: RideTypeSlice[]): DonutSegment[] {
  let acc = 0;
  return items.map((it) => {
    const seg: DonutSegment = {
      color: it.color,
      circumference: CIRC,
      dashArray: `${it.fraction * CIRC} ${CIRC}`,
      dashOffset: -acc * CIRC,
    };
    acc += it.fraction;
    return seg;
  });
}

/** Ride-type breakdown: donut + legend. */
export function RideTypesDonut({ data }: { data: RideTypesView }) {
  const segments = donutSegments(data.items);
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-5 flex flex-col transition-colors duration-300">
      <div className="flex items-center justify-between mb-5">
        <span className="font-display font-medium text-[15px] text-ink">Ride types</span>
        <span className="font-mono text-[11px] text-faint">{data.total} TOTAL</span>
      </div>
      <div className="flex items-center gap-5">
        <div className="flex-1 flex flex-col gap-3 min-w-0">
          {data.items.map((it) => (
            <div key={it.type} className="flex items-center gap-[9px]">
              <span className="w-[9px] h-[9px] rounded-[2px] flex-none" style={{ background: it.color }} />
              <span className="flex-1 text-[13px] text-body truncate">{it.label}</span>
              <span className="font-mono text-[11px] text-subtle">{it.pct}</span>
            </div>
          ))}
        </div>
        <div className="flex-none w-[140px] h-[140px]">
          <svg viewBox="0 0 200 200" className="w-full h-full -rotate-90">
            {segments.map((s, i) => (
              <circle
                key={i} cx="100" cy="100" r={R} fill="none" stroke={s.color} strokeWidth={26}
                strokeDasharray={s.dashArray} strokeDashoffset={s.dashOffset}
              />
            ))}
          </svg>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run to verify pass**

Run: `cd frontend && npx vitest run src/pages/app-home/components/RideTypesDonut.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/index.css frontend/src/pages/app-home/components/RideTypesDonut.tsx frontend/src/pages/app-home/components/RideTypesDonut.test.tsx
git commit -m "feat(overview): RideTypesDonut + palette tokens"
```

---

## Task 7: Frontend — HeroPanel + SummaryCard (presentational)

**Files:**
- Create: `frontend/src/pages/app-home/components/HeroPanel.tsx`
- Create: `frontend/src/pages/app-home/components/SummaryCard.tsx`

These are presentational; they're verified by the `AppHome` page test in Task 9 (per the frontend contract: pure markup is covered by the page test). No standalone tests.

**Interfaces:**
- Produces: `<HeroPanel headline={HeadlineKpi} secondary={Kpi[]} trend={TrendPoint[]} trendUnit={string} isDark={boolean} />`; `<SummaryCard summary={SummaryView} />`.

- [ ] **Step 1: Implement HeroPanel**

Create `HeroPanel.tsx`:

```typescript
import type { HeadlineKpi, Kpi, TrendPoint } from "@/types/overview";
import { TrendChart } from "./TrendChart";

/** Hero: big headline KPI + 3 secondary KPIs, alongside the period trend chart. */
export function HeroPanel({
  headline, secondary, trend, trendUnit, isDark,
}: {
  headline: HeadlineKpi;
  secondary: Kpi[];
  trend: TrendPoint[];
  trendUnit: string;
  isDark: boolean;
}) {
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-6 mb-4 grid grid-cols-[0.92fr_1.32fr] gap-8 max-[1024px]:grid-cols-1 transition-colors duration-300">
      <div className="flex flex-col">
        <div className="flex items-center gap-[9px] mb-5">
          <span className="w-[7px] h-[7px] rounded-[2px] bg-strava flex-none" />
          <span className="font-mono text-[10px] tracking-[0.16em] text-subtle">
            {headline.label} · {headline.periodLabel}
          </span>
        </div>
        <div className="flex items-end gap-[10px] leading-[0.85]">
          <span className="font-display font-semibold text-[64px] tracking-[-0.035em] text-ink">
            {headline.value}
          </span>
          <span className="font-mono text-[16px] text-muted2 mb-[9px]">{headline.unit}</span>
        </div>
        <div className="mt-4">
          <span
            className={`font-mono text-[11px] px-[11px] py-[5px] rounded-full ${
              headline.deltaPositive ? "text-good bg-good-soft" : "text-bad bg-bad-soft"
            }`}
          >
            {headline.delta} {headline.deltaCaption}
          </span>
        </div>
        <div className="flex-1 min-h-[22px]" />
        <div className="grid grid-cols-3 gap-[14px] border-t border-line pt-[18px]">
          {secondary.map((k) => (
            <div key={k.label} className="flex flex-col gap-[7px]">
              <span className="font-mono text-[9.5px] tracking-[0.12em] text-subtle">{k.label}</span>
              <div className="flex items-baseline gap-1">
                <span className="font-display font-semibold text-[21px] tracking-[-0.01em] leading-none text-ink">
                  {k.value}
                </span>
                {k.unit && <span className="font-mono text-[10px] text-subtle">{k.unit}</span>}
              </div>
              <span className={`font-mono text-[10px] ${k.deltaPositive ? "text-good" : "text-bad"}`}>
                {k.delta}
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className="flex flex-col border-l border-line pl-8 min-w-0 max-[1024px]:border-l-0 max-[1024px]:pl-0 max-[1024px]:border-t max-[1024px]:pt-5">
        <div className="flex items-center justify-between mb-4">
          <span className="font-display font-medium text-[14px] text-body">Distance over time</span>
          <span className="font-mono text-[10px] tracking-[0.08em] text-faint">{headline.periodLabel}</span>
        </div>
        <TrendChart points={trend} unit={trendUnit} isDark={isDark} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Implement SummaryCard**

Create `SummaryCard.tsx`:

```typescript
import type { SummaryView } from "@/types/overview";

/** Records summary for the selected period. */
export function SummaryCard({ summary }: { summary: SummaryView }) {
  const stats: { label: string; value: string; accent?: boolean }[] = [
    { label: "RIDES", value: summary.rides },
    { label: "PERSONAL RECORDS", value: summary.prs, accent: true },
    { label: "TOP AVG SPEED", value: summary.topSpeed },
    { label: "LONGEST RIDE", value: summary.longestRide },
    { label: "MAX ELEV GAIN", value: summary.maxElev },
  ];
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-5 mb-4 transition-colors duration-300">
      <div className="grid grid-cols-5 gap-4 max-[1024px]:grid-cols-2">
        {stats.map((s) => (
          <div key={s.label} className="flex flex-col gap-[6px]">
            <span className="font-mono text-[9px] tracking-[0.1em] text-subtle">{s.label}</span>
            <span className={`font-display font-semibold text-[22px] tracking-[-0.01em] leading-none ${s.accent ? "text-strava" : "text-ink"}`}>
              {s.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Typecheck + commit**

Run: `cd frontend && npx tsc -b`
Expected: clean.

```bash
git add frontend/src/pages/app-home/components/HeroPanel.tsx frontend/src/pages/app-home/components/SummaryCard.tsx
git commit -m "feat(overview): HeroPanel + SummaryCard"
```

---

## Task 8: Frontend — update RecentRidesPanel

**Files:**
- Modify: `frontend/src/pages/app-home/components/RecentRidesPanel.tsx`
- Test: `frontend/src/pages/app-home/components/RecentRidesPanel.test.tsx`

**Interfaces:**
- Consumes: `DashRide[]` (now with `isPr`, `dotColor`).
- Produces: `<RecentRidesPanel rides={DashRide[]} />` — rows link to `/activities/:id`, header "VIEW ALL →" links to `/activities`, PR badge when `isPr`.

- [ ] **Step 1: Write the failing test**

Create `RecentRidesPanel.test.tsx` (needs a router for `<Link>`):

```typescript
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import { RecentRidesPanel } from "./RecentRidesPanel";
import type { DashRide } from "@/types/overview";

const RIDES: DashRide[] = [
  { id: 7, name: "River loop", meta: "Tue · Jun 16 · Ride", distLabel: "38.7 km",
    durLabel: "1h 34m", isPr: true, dotColor: "var(--color-strava)" },
];

function renderPanel() {
  const router = createMemoryRouter(
    [{ path: "/", element: <RecentRidesPanel rides={RIDES} /> }],
    { initialEntries: ["/"] },
  );
  return render(<RouterProvider router={router} />);
}

describe("RecentRidesPanel", () => {
  it("links each ride to its detail page", () => {
    renderPanel();
    expect(screen.getByRole("link", { name: /River loop/ })).toHaveAttribute("href", "/activities/7");
  });

  it("shows a PR badge and a VIEW ALL link", () => {
    renderPanel();
    expect(screen.getByText("PR")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /VIEW ALL/ })).toHaveAttribute("href", "/activities");
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/pages/app-home/components/RecentRidesPanel.test.tsx`
Expected: FAIL — current panel has no links/PR badge.

- [ ] **Step 3: Rewrite the panel**

Replace `RecentRidesPanel.tsx`:

```typescript
import { Link } from "react-router";
import type { DashRide } from "@/types/overview";

/** Recent rides list — links to detail pages, with optional PR badges. */
export function RecentRidesPanel({ rides }: { rides: DashRide[] }) {
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-2 pb-1 transition-colors duration-300">
      <div className="flex items-center justify-between px-[14px] pt-3 pb-[10px]">
        <span className="font-display font-medium text-[15px] text-ink">Recent rides</span>
        <Link to="/activities" className="font-mono text-[11px] text-strava hover:underline">
          VIEW ALL →
        </Link>
      </div>
      {rides.length === 0 ? (
        <div className="px-[14px] py-8 text-center text-[14px] text-subtle">No rides yet.</div>
      ) : (
        rides.map((r) => (
          <Link
            key={r.id}
            to={`/activities/${r.id}`}
            className="flex items-center justify-between px-[14px] py-3 rounded-[11px] hover:bg-surface-inset"
          >
            <div className="flex items-center gap-[13px] min-w-0">
              <span className="w-[9px] h-[9px] rounded-full flex-none" style={{ background: r.dotColor }} />
              <div className="min-w-0">
                <div className="text-[14px] font-medium text-ink truncate flex items-center gap-2">
                  {r.name}
                  {r.isPr && (
                    <span className="font-mono text-[9px] tracking-[0.08em] text-strava bg-strava-soft px-[6px] py-[2px] rounded-full">
                      PR
                    </span>
                  )}
                </div>
                <div className="font-mono text-[10.5px] text-faint mt-[2px]">{r.meta}</div>
              </div>
            </div>
            <div className="text-right flex-none pl-3">
              <div className="font-display font-semibold text-[15px] text-ink">{r.distLabel}</div>
              <div className="font-mono text-[10px] text-faint">{r.durLabel}</div>
            </div>
          </Link>
        ))
      )}
    </div>
  );
}
```

> `bg-strava-soft` resolves to the existing `--color-strava-soft` token (→ `--accent-soft`), so no new token or `index.css` change is needed for this task.

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npx vitest run src/pages/app-home/components/RecentRidesPanel.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/app-home/components/RecentRidesPanel.tsx frontend/src/pages/app-home/components/RecentRidesPanel.test.tsx
git commit -m "feat(overview): link recent rides + PR badges + VIEW ALL"
```

---

## Task 9: Frontend — compose AppHome + cleanup

**Files:**
- Modify: `frontend/src/pages/app-home/AppHome.tsx`
- Delete: `frontend/src/pages/app-home/components/KpiCards.tsx`, `frontend/src/pages/app-home/components/DistancePanel.tsx`
- Test: `frontend/src/pages/app-home/AppHome.test.tsx`

**Interfaces:**
- Consumes: `useOverview(period)`, `PeriodSelector`, `HeroPanel`, `SummaryCard`, `RideTypesDonut`, `RecentRidesPanel`, `useAthlete`, `useSettings`.

- [ ] **Step 1: Update the page test**

Open `frontend/src/pages/app-home/AppHome.test.tsx` and align it to the new page. It must (using the existing `renderWithProviders` helper + mocked api hooks already used in this file): assert the page renders the headline value and one secondary KPI label, the records card ("RIDES"), the ride-types "TOTAL" caption, a recent-ride link, the period selector, and **no "Refresh from Strava" button**. Example assertions to add/replace:

```typescript
// after the overview hook resolves with a DTO fixture:
expect(screen.getByText("DISTANCE · THIS WEEK")).toBeInTheDocument();
expect(screen.getByText("MOVING TIME")).toBeInTheDocument();
expect(screen.getByText("RIDES")).toBeInTheDocument();
expect(screen.getByRole("button", { name: "Week" })).toBeInTheDocument();
expect(screen.queryByRole("button", { name: /Refresh from Strava/ })).toBeNull();
```

Keep the file's existing mocking approach for `useOverview`/`useAthlete`/`useSyncStatus`; update the `useOverview` mock's resolved value to the new `DashboardOverview` shape (headline/secondary/trend/trendUnit/summary/rideTypes/recentRides).

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/pages/app-home/AppHome.test.tsx`
Expected: FAIL — old KPI/refresh markup gone, new assertions unmet.

- [ ] **Step 3: Rewrite AppHome**

Replace `frontend/src/pages/app-home/AppHome.tsx`:

```typescript
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { disconnect, logout, useAthlete } from "@/api/auth";
import { useOverview } from "@/api/overview";
import { useSyncStatus } from "@/api/sync";
import { useSettings } from "@/app/providers/settings-context";
import { AppShell } from "@/components/app-shell/AppShell";
import type { Period } from "@/types/overview";
import { HeroPanel } from "./components/HeroPanel";
import { PeriodSelector } from "./components/PeriodSelector";
import { RecentRidesPanel } from "./components/RecentRidesPanel";
import { RideTypesDonut } from "./components/RideTypesDonut";
import { SummaryCard } from "./components/SummaryCard";

const VALID_PERIODS: Period[] = ["week", "month", "year"];

function SkeletonPanels() {
  return (
    <div className="p-7" role="status" aria-label="Loading overview">
      <div className="bg-surface-card border border-line rounded-2xl p-6 mb-4">
        <div className="h-[11px] w-[120px] rounded bg-skel mb-5 animate-pkskel" />
        <div className="h-[180px] rounded-[10px] bg-skel animate-pkskel" />
      </div>
      <div className="bg-surface-card border border-line rounded-2xl p-5">
        <div className="h-[180px] rounded-[10px] bg-skel animate-pkskel" />
      </div>
    </div>
  );
}

export default function AppHome() {
  const { data: athlete, error } = useAthlete();
  const { data: status } = useSyncStatus();
  const { isDark } = useSettings();
  const navigate = useNavigate();

  const [period, setPeriod] = useState<Period>("week");
  const seeded = useRef(false);
  useEffect(() => {
    if (!seeded.current && athlete) {
      const dp = athlete.settings.default_period as Period;
      if (VALID_PERIODS.includes(dp)) setPeriod(dp);
      seeded.current = true;
    }
  }, [athlete]);

  const { data: overview, isLoading } = useOverview(period);

  useEffect(() => {
    if (error) navigate("/", { replace: true });
  }, [error, navigate]);

  useEffect(() => {
    if (status?.status === "never_synced") navigate("/sync", { replace: true });
  }, [status, navigate]);

  const synced = status?.status === "idle";

  const handleLogout = async () => {
    await logout();
    navigate("/", { replace: true });
  };

  const handleDisconnect = async () => {
    await disconnect();
    navigate("/", { replace: true });
  };

  return (
    <AppShell
      navActive="Overview"
      athlete={athlete}
      syncLabel={synced ? "Up to date" : "Syncing…"}
      onLogout={handleLogout}
      title="Overview"
      subtitle={synced ? "UP TO DATE" : "SYNCING"}
      headerRight={<PeriodSelector value={period} onChange={setPeriod} />}
    >
      <div className="h-full overflow-y-auto">
        {isLoading || !overview ? (
          <SkeletonPanels />
        ) : (
          <div className="p-7">
            <HeroPanel
              headline={overview.headline}
              secondary={overview.secondary}
              trend={overview.trend}
              trendUnit={overview.trendUnit}
              isDark={isDark}
            />
            <SummaryCard summary={overview.summary} />
            <div className="grid grid-cols-[1.55fr_1fr] gap-4 max-[1024px]:grid-cols-1">
              <RecentRidesPanel rides={overview.recentRides} />
              <RideTypesDonut data={overview.rideTypes} />
            </div>
          </div>
        )}
        <div className="px-7 pb-10">
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

- [ ] **Step 4: Delete the retired components**

```bash
git rm frontend/src/pages/app-home/components/KpiCards.tsx frontend/src/pages/app-home/components/DistancePanel.tsx
```

(Also delete their test files if any exist: `git rm` any `KpiCards.test.tsx` / `DistancePanel.test.tsx` that `ls` reveals.)

- [ ] **Step 5: Run the page test + full suite**

Run: `cd frontend && npx vitest run src/pages/app-home/AppHome.test.tsx`
Expected: PASS.

- [ ] **Step 6: Full gate**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: all pass (verify no leftover imports of `WeekChart`/`KpiCards`/`DistancePanel`; `npm run build`'s `tsc -b` will catch any).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/app-home/AppHome.tsx frontend/src/pages/app-home/AppHome.test.tsx
git commit -m "feat(overview): compose redesigned dashboard, retire old KPI/distance panels"
```

---

## Self-Review (completed during planning)

**Spec coverage:** period selector (Tasks 1,2,4,9) · calendar week/month/year semantics + deltas + trend granularity (Task 1) · hero headline + 3 secondary KPIs + trend chart (Tasks 3,5,7) · summary/records minus top-power (Tasks 1,3,7) · recent rides + PR badges + VIEW ALL + click-through (Tasks 1,3,8) · ride-types donut (Tasks 1,3,6) · no refresh button (Task 9) · reflow layout (Task 9) · period seeded from `default_period`, not persisted (Task 9) · tokens not raw hex (Tasks 6,8). Heatmap/goal/zones/top-power/gear correctly absent. **No gaps.**

**Type consistency:** `Period`, `OverviewResponse`/`OverviewDTO`, `PeriodTotals`/`PeriodTotalsDTO`, `TrendPoint`, `OverviewSummary`/`SummaryView`, `RideTypeCount`/`RideTypeSlice`, `DashRide` (with `isPr`/`dotColor`), `donutSegments`, `useOverview(period)`, `toOverview(dto, units)` are used identically across producing and consuming tasks.

**Placeholder scan:** no `TODO`/`TBD`/vague steps; every code step shows complete code. The one conditional (deleting any stray `*.test.tsx` for retired components in Task 9) is a grep-guarded cleanup, not a placeholder.
