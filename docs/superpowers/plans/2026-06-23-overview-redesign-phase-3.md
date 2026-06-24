# Overview Redesign — Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the final Overview-redesign elements — a Top-avg-power stat plus selector-scoped Time-in-power-zones and Time-in-HR-zones panels — backed by a compact, FTP-independent per-activity metrics store.

**Architecture:** A new `activity_metrics` table holds one row per activity: precomputed power scalars (`avg_power_w`/`np_w`/`work_kj`) plus FTP/HR-max-**independent** absolute-bin histograms (`power_hist`/`hr_hist`). Zone boundaries are applied at query time from the athlete's current `ftp_w`/`hr_max`, so changing them in Settings re-buckets instantly with no re-backfill. `get_overview` sums each period's histograms and reuses the existing `analysis` zone math + `ZonesBlock` model (one source of truth, shared with the activity-detail page). The frontend reuses the detail page's already-tokenized zone colors and `toZoneRows` mapper.

**Tech Stack:** FastAPI · Supabase (Postgres + supabase-py) · pytest/ruff/mypy · React 19 + Vite + TypeScript + Tailwind v4 · Vitest/Testing Library.

## Global Constraints

- **Layering:** routers → services → db; no layer skips another. Services contain **no `fastapi` imports**. db modules return their declared `TypedDict` (cast from `.data`).
- **Type annotations on every public function** (params + return). `ruff check .` and `mypy` must be clean before every backend commit.
- **Async only when `await`ing.** All work here is sync supabase-py / httpx-via-wrapper calls → plain `def`.
- **Pydantic at I/O boundaries only**; db row shapes stay `TypedDict`.
- **Reuse existing zone math** in `app/services/analysis.py` (`power_zones`, `hr_zones`) and the existing `ZoneBucket`/`ZonesBlock` models. Do not introduce a parallel set of zone definitions.
- **Power is not unit-converted** — watts are watts in metric and imperial.
- **Frontend:** `@/` import alias; token utilities (never raw hex) for text/surfaces; zone bar colors use the existing `--zone-*` CSS vars (see Deviation note). `npm test && npm run lint && npm run build` must pass before any frontend commit considered done.
- **Storage protection:** the streams backfill stores **metrics only** — it must never write a full stream blob for an un-viewed ride.
- **Frequent commits:** one commit per task (the final step of each task).

## Deviation from the design spec (intentional)

The design spec (`docs/superpowers/specs/2026-06-23-overview-redesign-phase-3-design.md`) was drafted assuming the frontend had no zone primitives, so it called for (a) **new** `ZoneBucketDTO`/`ZonesBlockDTO` duplicated into `types/overview.ts`, (b) new `ZoneRow`/`ZonesView` display types + a `buildZonesView` mapper, and (c) **two JS-literal color-array palettes**. The activity-detail page already ships all of this: shared `ZonesBlockDTO`/`ZoneBucketDTO`, a `toZoneRows`/`zoneColor` mapper, and tokenized `--zone-1..7` colors (both themes, in `index.css`). This plan **reuses** those instead of duplicating them — promoting the shared pieces to `types/zones.ts` + `api/zones.ts` (Task 13). Net effect is identical rendering with less code and one source of truth. All **backend** decisions in the spec are followed as written.

## File structure

**Backend**
- `supabase/migrations/0008_activity_metrics.sql` — **create**: `activity_metrics` table + `avg_watts` column on `activities` + RLS.
- `backend/app/services/analysis.py` — **modify**: bin constants, `histogram`, `zone_seconds_from_histogram`, `buckets_from_zone_seconds`, `compute_metrics`; refactor `time_in_zones` to delegate.
- `backend/app/db/metrics.py` — **create**: `MetricsRow` + `get_metrics`/`upsert_metrics`/`list_metrics_for_activities`/`list_activity_ids_needing_metrics`.
- `backend/app/db/activities.py` — **modify**: add `avg_watts` to `ActivityRow`.
- `backend/app/services/sync.py` — **modify**: `_to_activity_row` maps `average_watts`; add `_fetch_streams_with_backoff`, `run_streams_backfill`, `run_avg_watts_backfill`.
- `backend/app/services/activities.py` — **modify**: `ensure_streams` writes metrics; `get_overview` gains `top_avg_power_w` + `_period_zones`; (Task 12) `get_detail` reads metrics.
- `backend/app/models/activities.py` — **modify**: `OverviewSummary.top_avg_power_w`; `OverviewResponse.power_zones`/`hr_zones`.
- `backend/app/routers/sync.py` — **modify**: chain `run_streams_backfill` on `POST /sync/start`.
- Tests mirror each: `tests/services/test_analysis.py`, `tests/db/test_metrics.py` (new), `tests/services/test_sync.py`, `tests/services/test_activities_streams.py`, `tests/services/test_activities.py`, `tests/routers/test_sync.py`.

**Frontend**
- `frontend/src/types/zones.ts` — **create**: shared `ZoneBucketDTO`/`ZonesBlockDTO`.
- `frontend/src/api/zones.ts` — **create**: shared `ZoneRowVM`/`zoneColor`/`toZoneRows`.
- `frontend/src/types/activity-detail.ts` / `frontend/src/api/activity-detail.ts` — **modify**: re-export from the new shared modules (back-compat, no behavior change).
- `frontend/src/types/overview.ts` — **modify**: `top_avg_power_w` on `OverviewSummaryDTO`; `power_zones`/`hr_zones` on `OverviewDTO`; `topAvgPower` on `SummaryView`; `powerZones`/`hrZones` on `DashboardOverview`.
- `frontend/src/api/overview.ts` — **modify**: map `topAvgPower` + pass zone blocks through.
- `frontend/src/pages/app-home/components/ZonePanel.tsx` (+ test) — **create**.
- `frontend/src/pages/app-home/components/SummaryCard.tsx` (+ new test) — **modify**: TOP AVG POWER row.
- `frontend/src/pages/app-home/AppHome.tsx` / `AppHome.test.tsx` — **modify**: three-up zone row + skeleton + fixture.

---

## Task 0: Commit the design spec (preflight)

The Phase 3 design spec is currently untracked. Commit it first so history mirrors Phases 1–2 (design doc precedes plan precedes impl).

- [ ] **Step 1: Stage and commit the design spec + this plan**

```bash
cd /Users/hollandclarke/Desktop/peakstats
git add docs/superpowers/specs/2026-06-23-overview-redesign-phase-3-design.md \
        docs/superpowers/plans/2026-06-23-overview-redesign-phase-3.md
git commit -m "docs(overview): Phase 3 design + implementation plan — power/HR zones + top-avg-power"
```

---

## Task 1: Migration `0008` — `activity_metrics` table + `avg_watts` column

**Files:**
- Create: `supabase/migrations/0008_activity_metrics.sql`

**Interfaces:**
- Produces: table `activity_metrics(activity_id PK, athlete_id, avg_power_w, np_w, work_kj, power_hist jsonb, hr_hist jsonb, has_power, has_hr, computed_at)`; column `activities.avg_watts double precision`.

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/0008_activity_metrics.sql` (mirrors the `0006_activity_streams.sql` RLS pattern — service-role writes bypass RLS, athlete-scoped read policy):

```sql
-- Compact, FTP/HR-max-independent per-activity metrics: precomputed power
-- scalars plus absolute-bin histograms (seconds per wattage / bpm bin). Zone
-- boundaries are applied at QUERY time from the athlete's current ftp_w / hr_max,
-- so changing them re-buckets instantly with no re-backfill. One row per activity.
-- Histogram bin geometry is documented in app/services/analysis.py
-- (POWER_BIN_W=10/POWER_BINS=150 → [0,1500)W; HR_BIN_BPM=5/HR_BINS=44 → [0,220)bpm;
-- overflow folds into the last bin). hist columns are NULL when the ride has no
-- power / no HR.
create table if not exists activity_metrics (
  activity_id  bigint primary key references activities(id) on delete cascade,
  athlete_id   bigint not null references athletes(id) on delete cascade,
  avg_power_w  double precision,
  np_w         double precision,
  work_kj      double precision,
  power_hist   jsonb,
  hr_hist      jsonb,
  has_power    boolean not null default false,
  has_hr       boolean not null default false,
  computed_at  timestamptz not null default now()
);

create index if not exists activity_metrics_athlete_idx on activity_metrics(athlete_id);

alter table activity_metrics enable row level security;

create policy activity_metrics_self_read on activity_metrics
  for select using (athlete_id = (auth.jwt() ->> 'athlete_id')::bigint);

-- Highest single-ride average power for the period's "Top avg power" stat.
-- Sourced from Strava summary average_watts (nullable; no power meter → null).
alter table activities add column if not exists avg_watts double precision;
```

- [ ] **Step 2: Verify the file parses (local sanity, optional)**

The migration is applied to Supabase during rollout (Section "Migration & rollout"), the same way `0004`/`0005` were. No automated test gate; review the SQL for the FK + RLS shape against `0006`.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/0008_activity_metrics.sql
git commit -m "feat(db): activity_metrics table + activities.avg_watts (migration 0008)"
```

---

## Task 2: Analysis — histogram + zone-from-histogram helpers (pure math)

**Files:**
- Modify: `backend/app/services/analysis.py`
- Test: `backend/tests/services/test_analysis.py`

**Interfaces:**
- Produces:
  - `POWER_BIN_W = 10`, `POWER_BINS = 150`, `HR_BIN_BPM = 5`, `HR_BINS = 44`
  - `histogram(time: list[int], series: list | None, bin_w: int, n_bins: int) -> list[float]`
  - `zone_seconds_from_histogram(hist: list[float], bin_w: int, zones: list[dict]) -> list[float]`
  - `buckets_from_zone_seconds(secs: list[float], zones: list[dict]) -> list[dict]` (emits the same `{z,name,range,seconds,pct}` shape as `time_in_zones`)
- Consumes: existing `deltas` (Task uses it inside `histogram`).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/services/test_analysis.py`:

```python
def test_histogram_dt_weighted_bins_and_overflow():
    # deltas([0,1,2,3]) = [1,1,1,1]; bin_w=10 → 5→bin0, 14→bin1, 25→bin2, 9999→last
    h = analysis.histogram([0, 1, 2, 3], [5, 14, 25, 9999], 10, 150)
    assert len(h) == 150
    assert h[0] == 1.0 and h[1] == 1.0 and h[2] == 1.0
    assert h[149] == 1.0          # 9999 W overflows into the last bin


def test_histogram_skips_none_and_empty_series():
    assert analysis.histogram([0, 1, 2], [50, None, 50], 10, 150)[5] == 2.0
    assert analysis.histogram([0, 1], None, 10, 150) == [0.0] * 150
    assert analysis.histogram([], [], 5, 44) == [0.0] * 44


def test_zone_seconds_from_histogram_maps_bin_midpoints():
    zones = analysis.power_zones(200)  # Z1 [0,110) Z2 [110,150) ... Z7 [300,None)
    hist = [0.0] * 150
    hist[5] = 7.0      # midpoint 55 W  → Z1
    hist[12] = 3.0     # midpoint 125 W → Z2
    hist[149] = 4.0    # midpoint 1495 W → Z7 (open top)
    secs = analysis.zone_seconds_from_histogram(hist, 10, zones)
    assert secs[0] == 7.0 and secs[1] == 3.0 and secs[6] == 4.0
    assert analysis.zone_seconds_from_histogram([0.0] * 150, 10, zones) == [0.0] * 7


def test_buckets_from_zone_seconds_matches_time_in_zones_shape():
    zones = analysis.power_zones(200)
    buckets = analysis.buckets_from_zone_seconds([6.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0], zones)
    by_z = {b["z"]: b for b in buckets}
    assert by_z["Z1"]["seconds"] == 6 and by_z["Z1"]["pct"] == 75.0
    assert by_z["Z7"]["pct"] == 25.0
    assert set(buckets[0]) == {"z", "name", "range", "seconds", "pct"}
    # all-zero is a valid "no data" result: zero pct, no division error
    assert analysis.buckets_from_zone_seconds([0.0] * 7, zones)[0]["pct"] == 0.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/services/test_analysis.py -k "histogram or buckets_from" -v`
Expected: FAIL with `AttributeError: module 'app.services.analysis' has no attribute 'histogram'`.

- [ ] **Step 3: Implement the helpers and refactor `time_in_zones`**

In `backend/app/services/analysis.py`, add the constants after the existing `HR_ZONE_*` block:

```python
POWER_BIN_W = 10
POWER_BINS = 150       # [0, 1500) W; samples ≥ 1500 fold into the last bin
HR_BIN_BPM = 5
HR_BINS = 44           # [0, 220) bpm; overflow into the last bin
```

Add the three new functions (place near `time_in_zones`):

```python
def histogram(time: list[int], series: list | None, bin_w: int, n_bins: int) -> list[float]:
    """Δt-weighted seconds per absolute bin. Overflow folds into the last bin;
    None samples are skipped. Empty/None series → a zero array of length n_bins."""
    out = [0.0] * n_bins
    if not series:
        return out
    dt = deltas(time)
    for w, v in zip(dt, series, strict=False):
        if v is None:
            continue
        idx = int(v // bin_w)
        idx = 0 if idx < 0 else min(idx, n_bins - 1)
        out[idx] += w
    return out


def zone_seconds_from_histogram(
    hist: list[float], bin_w: int, zones: list[dict]
) -> list[float]:
    """Sum each bin's seconds into the zone whose [lo, hi) contains the bin midpoint."""
    secs = [0.0] * len(zones)
    for i, s in enumerate(hist):
        mid = i * bin_w + bin_w / 2
        for j, z in enumerate(zones):
            hi = z["hi"]
            if mid >= z["lo"] and (hi is None or mid < hi):
                secs[j] += s
                break
    return secs


def buckets_from_zone_seconds(secs: list[float], zones: list[dict]) -> list[dict]:
    """Format per-zone seconds into {z,name,range,seconds,pct} dicts."""
    total = sum(secs) or 1.0
    return [
        {"z": z["z"], "name": z["name"], "range": z["range"],
         "seconds": round(secs[i]), "pct": round(secs[i] / total * 100, 1)}
        for i, z in enumerate(zones)
    ]
```

Refactor the existing `time_in_zones` body to delegate (identical output):

```python
def time_in_zones(time: list[int], series: list, zones: list[dict]) -> list[dict]:
    """Δt-weighted seconds and percentage spent in each zone bucket."""
    dt = deltas(time)
    secs = [0.0] * len(zones)
    for w, v in zip(dt, series, strict=False):
        if v is None:
            continue
        for i, z in enumerate(zones):
            hi = z["hi"]
            if v >= z["lo"] and (hi is None or v < hi):
                secs[i] += w
                break
    return buckets_from_zone_seconds(secs, zones)
```

- [ ] **Step 4: Run the tests to verify they pass (incl. the existing `time_in_zones` tests)**

Run: `cd backend && pytest tests/services/test_analysis.py -v && ruff check app/services/analysis.py && mypy`
Expected: PASS — new tests green AND the existing `test_time_in_zones_*` tests still green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/analysis.py backend/tests/services/test_analysis.py
git commit -m "feat(analysis): histogram + zone-from-histogram helpers; time_in_zones delegates"
```

---

## Task 3: Analysis — `compute_metrics`

**Files:**
- Modify: `backend/app/services/analysis.py`
- Test: `backend/tests/services/test_analysis.py`

**Interfaces:**
- Produces: `compute_metrics(data: dict) -> dict` → keys `avg_power_w`, `np_w`, `work_kj`, `power_hist`, `hr_hist`, `has_power`, `has_hr`.
- Consumes: `weighted_mean`, `normalized_power`, `total_work_kj`, `histogram`, `POWER_BIN_W`, `POWER_BINS`, `HR_BIN_BPM`, `HR_BINS`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/services/test_analysis.py`:

```python
def test_compute_metrics_with_power_and_hr():
    data = {"time": [0, 1, 2, 3], "watts": [100, 200, 200, 200],
            "heartrate": [120, 130, 140, 150]}
    m = analysis.compute_metrics(data)
    assert m["has_power"] is True and m["has_hr"] is True
    assert round(m["avg_power_w"]) == 175      # (100+200+200+200)/4, 1s each
    assert m["np_w"] is not None and m["work_kj"] is not None
    assert sum(m["power_hist"]) == 4.0         # 4 weighted seconds total
    assert sum(m["hr_hist"]) == 4.0


def test_compute_metrics_no_power_nulls_power_fields():
    m = analysis.compute_metrics({"time": [0, 1], "heartrate": [120, 130]})
    assert m["has_power"] is False
    assert m["avg_power_w"] is None and m["np_w"] is None and m["work_kj"] is None
    assert m["power_hist"] is None
    assert m["has_hr"] is True and m["hr_hist"] is not None


def test_compute_metrics_empty_streams():
    m = analysis.compute_metrics({})
    assert m == {"avg_power_w": None, "np_w": None, "work_kj": None,
                 "power_hist": None, "hr_hist": None,
                 "has_power": False, "has_hr": False}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/services/test_analysis.py -k compute_metrics -v`
Expected: FAIL with `AttributeError: ... no attribute 'compute_metrics'`.

- [ ] **Step 3: Implement `compute_metrics`**

Add to `backend/app/services/analysis.py`:

```python
def compute_metrics(data: dict) -> dict:
    """From a flat stream dict ({time, watts, heartrate, ...}) produce the
    activity_metrics payload. Power fields are gated on has_power so an
    all-None watts stream yields nulls (not a misleading 0)."""
    time = data.get("time") or []
    watts = data.get("watts")
    hr = data.get("heartrate")
    has_power = bool(watts) and any(w is not None for w in watts)
    has_hr = bool(hr) and any(v is not None for v in hr)
    return {
        "avg_power_w": weighted_mean(time, watts) if has_power else None,
        "np_w": normalized_power(time, watts) if has_power else None,
        "work_kj": total_work_kj(time, watts) if has_power else None,
        "power_hist": histogram(time, watts, POWER_BIN_W, POWER_BINS) if has_power else None,
        "hr_hist": histogram(time, hr, HR_BIN_BPM, HR_BINS) if has_hr else None,
        "has_power": has_power,
        "has_hr": has_hr,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/services/test_analysis.py -k compute_metrics -v && ruff check app/services/analysis.py && mypy`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/analysis.py backend/tests/services/test_analysis.py
git commit -m "feat(analysis): compute_metrics — scalars + FTP-independent histograms"
```

---

## Task 4: DB module — `db/metrics.py`

**Files:**
- Create: `backend/app/db/metrics.py`
- Test: `backend/tests/db/test_metrics.py`

**Interfaces:**
- Produces:
  - `MetricsRow` TypedDict: `activity_id, athlete_id, avg_power_w, np_w, work_kj, power_hist, hr_hist, has_power, has_hr`
  - `get_metrics(client, activity_id) -> MetricsRow | None`
  - `upsert_metrics(client, row: MetricsRow) -> None` (`on_conflict="activity_id"`)
  - `list_metrics_for_activities(client, athlete_id, activity_ids: list[int]) -> list[MetricsRow]`
  - `list_activity_ids_needing_metrics(client, athlete_id) -> list[int]`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/db/test_metrics.py` (mirrors `tests/db/test_streams.py` — respx over a real supabase client):

```python
import respx
from app.db import metrics
from httpx import Response
from supabase import create_client

CLIENT = create_client("https://proj.supabase.co", "svc")


@respx.mock
def test_get_metrics_returns_row_or_none():
    respx.route(method="GET", path="/rest/v1/activity_metrics").mock(
        return_value=Response(200, json=[{"activity_id": 5, "athlete_id": 7,
                                          "avg_power_w": 180.0, "np_w": 195.0, "work_kj": 720.0,
                                          "power_hist": [1.0], "hr_hist": None,
                                          "has_power": True, "has_hr": False}])
    )
    row = metrics.get_metrics(CLIENT, 5)
    assert row is not None and row["avg_power_w"] == 180.0 and row["has_power"] is True


@respx.mock
def test_get_metrics_none_when_missing():
    respx.route(method="GET", path="/rest/v1/activity_metrics").mock(
        return_value=Response(200, json=[]))
    assert metrics.get_metrics(CLIENT, 5) is None


@respx.mock
def test_upsert_metrics_merges_on_activity_id():
    route = respx.route(method="POST", path="/rest/v1/activity_metrics").mock(
        return_value=Response(201, json=[]))
    metrics.upsert_metrics(CLIENT, {"activity_id": 5, "athlete_id": 7,
                                    "avg_power_w": None, "np_w": None, "work_kj": None,
                                    "power_hist": None, "hr_hist": None,
                                    "has_power": False, "has_hr": False})
    req = route.calls.last.request
    assert req.url.params["on_conflict"] == "activity_id"
    assert "merge-duplicates" in req.headers.get("prefer", "")


def test_list_metrics_for_activities_empty_ids_skips_query():
    # No respx route registered: an HTTP call would raise. Empty ids must short-circuit.
    assert metrics.list_metrics_for_activities(CLIENT, 7, []) == []


@respx.mock
def test_list_metrics_for_activities_filters_by_ids():
    route = respx.route(method="GET", path="/rest/v1/activity_metrics").mock(
        return_value=Response(200, json=[{"activity_id": 1, "athlete_id": 7,
                                          "avg_power_w": 1.0, "np_w": None, "work_kj": None,
                                          "power_hist": [2.0], "hr_hist": None,
                                          "has_power": True, "has_hr": False}]))
    rows = metrics.list_metrics_for_activities(CLIENT, 7, [1, 2])
    assert [r["activity_id"] for r in rows] == [1]
    assert "in.(1,2)" in route.calls.last.request.url.params["activity_id"]


@respx.mock
def test_list_activity_ids_needing_metrics_returns_difference():
    respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(200, json=[{"id": 1}, {"id": 2}, {"id": 3}]))
    respx.route(method="GET", path="/rest/v1/activity_metrics").mock(
        return_value=Response(200, json=[{"activity_id": 2}]))
    assert metrics.list_activity_ids_needing_metrics(CLIENT, 7) == [1, 3]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/db/test_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.db.metrics'`.

- [ ] **Step 3: Implement `db/metrics.py`**

Create `backend/app/db/metrics.py`:

```python
from typing import Any, TypedDict, cast

from supabase import Client

_COLS = "activity_id, athlete_id, avg_power_w, np_w, work_kj, power_hist, hr_hist, has_power, has_hr"


class MetricsRow(TypedDict):
    activity_id: int
    athlete_id: int
    avg_power_w: float | None
    np_w: float | None
    work_kj: float | None
    power_hist: list[float] | None
    hr_hist: list[float] | None
    has_power: bool
    has_hr: bool


def get_metrics(client: Client, activity_id: int) -> MetricsRow | None:
    resp = (
        client.table("activity_metrics")
        .select(_COLS)
        .eq("activity_id", activity_id)
        .execute()
    )
    return cast(MetricsRow, resp.data[0]) if resp.data else None


def upsert_metrics(client: Client, row: MetricsRow) -> None:
    client.table("activity_metrics").upsert(
        cast(dict[str, Any], row), on_conflict="activity_id"
    ).execute()


def list_metrics_for_activities(
    client: Client, athlete_id: int, activity_ids: list[int]
) -> list[MetricsRow]:
    if not activity_ids:
        return []
    resp = (
        client.table("activity_metrics")
        .select(_COLS)
        .eq("athlete_id", athlete_id)
        .in_("activity_id", activity_ids)
        .execute()
    )
    return cast(list[MetricsRow], resp.data)


def list_activity_ids_needing_metrics(client: Client, athlete_id: int) -> list[int]:
    """Activity ids with no activity_metrics row yet (ascending), by id-diff.

    Resumable backfill marker: a metrics row's existence means 'done'. ~hundreds
    of ids is trivial. NOTE: relies on PostgREST's default page size covering the
    athlete's activity count (same characteristic as list_activities_since)."""
    acts = client.table("activities").select("id").eq("athlete_id", athlete_id).execute()
    mets = (
        client.table("activity_metrics").select("activity_id").eq("athlete_id", athlete_id).execute()
    )
    have = {r["activity_id"] for r in mets.data}
    return sorted(r["id"] for r in acts.data if r["id"] not in have)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/db/test_metrics.py -v && ruff check app/db/metrics.py && mypy`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/metrics.py backend/tests/db/test_metrics.py
git commit -m "feat(db): metrics module — per-activity metrics store + id-diff backfill query"
```

---

## Task 5: `avg_watts` on `ActivityRow` + sync mapping

**Files:**
- Modify: `backend/app/db/activities.py:7-23` (`ActivityRow`)
- Modify: `backend/app/services/sync.py:28-45` (`_to_activity_row`)
- Test: `backend/tests/services/test_sync.py`

**Interfaces:**
- Produces: `ActivityRow["avg_watts"]: NotRequired[float | None]`; `_to_activity_row(...)["avg_watts"]` mapped from `summary["average_watts"]`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_sync.py`:

```python
def test_to_activity_row_maps_avg_watts():
    row = sync_service._to_activity_row(7, {
        "id": 9, "name": "Power ride", "type": "Ride",
        "start_date": "2026-06-21T05:00:00Z", "distance": 1000.0,
        "moving_time": 100, "elapsed_time": 100, "total_elevation_gain": 0.0,
        "average_watts": 211.4,
    })
    assert row["avg_watts"] == 211.4


def test_to_activity_row_avg_watts_missing_is_none():
    row = sync_service._to_activity_row(7, {
        "id": 1, "name": "Spin", "type": "Workout",
        "start_date": "2026-06-15T08:00:00Z", "distance": 0.0,
        "moving_time": 10, "elapsed_time": 10, "total_elevation_gain": 0.0,
    })
    assert row["avg_watts"] is None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/services/test_sync.py -k avg_watts -v`
Expected: FAIL with `KeyError: 'avg_watts'`.

- [ ] **Step 3: Implement**

In `backend/app/db/activities.py`, add to `ActivityRow` (after `avg_speed_ms`):

```python
    avg_watts: NotRequired[float | None]
```

In `backend/app/services/sync.py`, add to the dict returned by `_to_activity_row` (after `"avg_speed_ms": summary.get("average_speed"),`):

```python
        "avg_watts": summary.get("average_watts"),
```

- [ ] **Step 4: Run to verify pass (full sync + db suites stay green)**

Run: `cd backend && pytest tests/services/test_sync.py tests/db/test_activities.py -v && ruff check . && mypy`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/activities.py backend/app/services/sync.py backend/tests/services/test_sync.py
git commit -m "feat(sync): store avg_watts from Strava summary average_watts"
```

---

## Task 6: `ensure_streams` writes `activity_metrics`

**Files:**
- Modify: `backend/app/services/activities.py:7-9` (imports), `:266-287` (`ensure_streams`)
- Test: `backend/tests/services/test_activities_streams.py`

**Interfaces:**
- Consumes: `analysis.compute_metrics`, `metrics_db.upsert_metrics`.
- Produces: `ensure_streams` upserts an `activity_metrics` row (from `compute_metrics(data)`) on both cache-hit and fresh-fetch paths; return value unchanged.

- [ ] **Step 1: Update the existing streams tests (they must patch the new metrics write) and add a new assertion**

In `backend/tests/services/test_activities_streams.py`, add a metrics patch to the two tests that exercise `ensure_streams`, and add one new test. Replace `test_ensure_streams_returns_cached_without_fetch` and `test_ensure_streams_fetches_persists_on_miss` with:

```python
def test_ensure_streams_returns_cached_without_fetch(monkeypatch):
    saved = {}
    monkeypatch.setattr(svc.streams_db, "get_streams",
        lambda c, aid: {"activity_id": aid, "athlete_id": 7,
                        "data": {"time": [0, 1], "watts": [100, 200]},
                        "resolution": "high", "point_count": 2})
    monkeypatch.setattr(svc.metrics_db, "upsert_metrics", lambda c, row: saved.update(row))
    strava = _Strava()
    data = svc.ensure_streams(object(), strava, 7, 5)
    assert data == {"time": [0, 1], "watts": [100, 200]} and strava.calls == 0
    assert saved["activity_id"] == 5 and saved["has_power"] is True   # metrics self-heal on cache hit


def test_ensure_streams_fetches_persists_on_miss(monkeypatch):
    saved, metrics = {}, {}
    monkeypatch.setattr(svc.streams_db, "get_streams", lambda c, aid: None)
    monkeypatch.setattr(svc.streams_db, "upsert_streams", lambda c, row: saved.update(row))
    monkeypatch.setattr(svc.metrics_db, "upsert_metrics", lambda c, row: metrics.update(row))
    monkeypatch.setattr(svc, "get_valid_access_token", lambda c, s, a: "tok")
    data = svc.ensure_streams(object(), _Strava(), 7, 5)
    assert data["watts"] == [100, 200]
    assert saved["point_count"] == 2 and saved["activity_id"] == 5 and saved["athlete_id"] == 7
    assert metrics["activity_id"] == 5 and metrics["athlete_id"] == 7 and metrics["has_power"] is True
```

Also patch `svc.metrics_db.upsert_metrics` in `test_ensure_streams_sentinel_when_strava_empty` (add the line alongside the other monkeypatches):

```python
    monkeypatch.setattr(svc.metrics_db, "upsert_metrics", lambda c, row: None)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/services/test_activities_streams.py -v`
Expected: FAIL — `AttributeError: module ... activities has no attribute 'metrics_db'` (import not added yet).

- [ ] **Step 3: Implement**

In `backend/app/services/activities.py`, add the import (next to the other `from app.db import ...` lines):

```python
from app.db import metrics as metrics_db
```

Rewrite `ensure_streams` so metrics are written on both paths, then add `_store_metrics`:

```python
def ensure_streams(
    supabase: Client,
    strava: StravaClient,
    athlete_id: int,
    activity_id: int,
) -> dict[str, list]:
    """Return cached stream data for the activity, fetching from Strava on miss.

    Stores a sentinel (empty data, point_count 0) when Strava has no streams, so
    we never refetch. Always (re)computes and upserts the compact activity_metrics
    row so viewed/new rides' metrics stay current and self-heal. `data` is the flat
    object-of-arrays.
    """
    existing = streams_db.get_streams(supabase, activity_id)
    if existing is not None:
        data = existing["data"]
    else:
        token = get_valid_access_token(supabase, strava, athlete_id)
        data = strava.get_activity_streams(token, activity_id, STREAM_KEYS)
        point_count = len(data.get("time") or data.get("distance") or [])
        streams_db.upsert_streams(supabase, {
            "activity_id": activity_id, "athlete_id": athlete_id,
            "data": data, "resolution": "high", "point_count": point_count,
        })
    _store_metrics(supabase, athlete_id, activity_id, data)
    return data


def _store_metrics(
    supabase: Client, athlete_id: int, activity_id: int, data: dict
) -> None:
    """Compute and upsert the compact activity_metrics row from a stream dict."""
    row = {"activity_id": activity_id, "athlete_id": athlete_id, **analysis.compute_metrics(data)}
    metrics_db.upsert_metrics(supabase, row)  # type: ignore[arg-type]
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && pytest tests/services/test_activities_streams.py tests/services/test_activities_detail.py -v && ruff check . && mypy`
Expected: PASS (detail tests still green — `ensure_streams` return value unchanged).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/activities.py backend/tests/services/test_activities_streams.py
git commit -m "feat(streams): ensure_streams self-heals activity_metrics on read"
```

---

## Task 7: `run_streams_backfill` — paced, resumable metrics pass

**Files:**
- Modify: `backend/app/services/sync.py` (imports + new functions)
- Test: `backend/tests/services/test_sync.py`

**Interfaces:**
- Consumes: `metrics_db.list_activity_ids_needing_metrics`, `metrics_db.upsert_metrics`, `analysis.compute_metrics`, `activities_service.STREAM_KEYS`, existing `build_strava`/`get_valid_access_token`/`DETAIL_PAUSE_S`/`DETAIL_BACKOFF_S`.
- Produces: `_fetch_streams_with_backoff(strava, access_token, activity_id, keys) -> dict`; `run_streams_backfill(supabase, settings, athlete_id) -> None`.

- [ ] **Step 1: Write the failing tests** (mirror `test_run_detail_backfill_*`)

Append to `backend/tests/services/test_sync.py`:

```python
def test_run_streams_backfill_computes_and_upserts_only_pending(monkeypatch):
    fetched, upserts = [], []

    class FakeStrava:
        def get_activity_streams(self, access_token, activity_id, keys, resolution="high"):
            fetched.append(activity_id)
            return {"time": [0, 1], "watts": [100, 200], "heartrate": [120, 130]}

        def close(self):
            pass

    monkeypatch.setattr(sync_service, "build_strava", lambda settings: FakeStrava())
    monkeypatch.setattr(sync_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    monkeypatch.setattr(sync_service.metrics_db, "list_activity_ids_needing_metrics",
                        lambda supabase, athlete_id: [11, 12])
    monkeypatch.setattr(sync_service.metrics_db, "upsert_metrics",
                        lambda supabase, row: upserts.append(row["activity_id"]))
    monkeypatch.setattr(sync_service.time, "sleep", lambda s: None)

    sync_service.run_streams_backfill(FakeSupabase(), settings=object(), athlete_id=7)
    assert fetched == [11, 12]
    assert upserts == [11, 12]


def test_run_streams_backfill_isolates_failures(monkeypatch):
    upserts = []

    class FakeStrava:
        def get_activity_streams(self, access_token, activity_id, keys, resolution="high"):
            if activity_id == 12:
                raise RuntimeError("boom")
            return {"time": [0, 1], "watts": [100, 200]}

        def close(self):
            pass

    monkeypatch.setattr(sync_service, "build_strava", lambda settings: FakeStrava())
    monkeypatch.setattr(sync_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    monkeypatch.setattr(sync_service.metrics_db, "list_activity_ids_needing_metrics",
                        lambda supabase, athlete_id: [11, 12, 13])
    monkeypatch.setattr(sync_service.metrics_db, "upsert_metrics",
                        lambda supabase, row: upserts.append(row["activity_id"]))
    monkeypatch.setattr(sync_service.time, "sleep", lambda s: None)

    sync_service.run_streams_backfill(FakeSupabase(), settings=object(), athlete_id=7)
    assert upserts == [11, 13]   # 12 failed mid-fetch, batch continued


def test_run_streams_backfill_backs_off_on_429(monkeypatch):
    import httpx
    calls = {"n": 0}
    slept = []

    class FakeStrava:
        def get_activity_streams(self, access_token, activity_id, keys, resolution="high"):
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.HTTPStatusError("429", request=httpx.Request("GET", "http://x"),
                                            response=httpx.Response(429, headers={"Retry-After": "2"}))
            return {"time": [0, 1], "watts": [100, 200]}

        def close(self):
            pass

    monkeypatch.setattr(sync_service, "build_strava", lambda settings: FakeStrava())
    monkeypatch.setattr(sync_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    monkeypatch.setattr(sync_service.metrics_db, "list_activity_ids_needing_metrics",
                        lambda supabase, athlete_id: [11])
    monkeypatch.setattr(sync_service.metrics_db, "upsert_metrics", lambda supabase, row: None)
    monkeypatch.setattr(sync_service.time, "sleep", lambda s: slept.append(s))

    sync_service.run_streams_backfill(FakeSupabase(), settings=object(), athlete_id=7)
    assert calls["n"] == 2 and 2 in slept   # retried after 429, honoured Retry-After
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/services/test_sync.py -k run_streams_backfill -v`
Expected: FAIL with `AttributeError: ... 'run_streams_backfill'` (and `sync_service.metrics_db` missing).

- [ ] **Step 3: Implement**

In `backend/app/services/sync.py`, add imports (near the other `from app.db ...` / `from app.services ...`):

```python
from app.db import metrics as metrics_db
from app.services import analysis
from app.services.activities import STREAM_KEYS
```

Add the two functions (after `run_detail_backfill`):

```python
def _fetch_streams_with_backoff(
    strava: object, access_token: str, activity_id: int, keys: list[str]
) -> dict:
    while True:
        try:
            return strava.get_activity_streams(access_token, activity_id, keys)  # type: ignore[attr-defined]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429:
                raise
            retry_after = exc.response.headers.get("Retry-After")
            time.sleep(float(retry_after) if retry_after else DETAIL_BACKOFF_S)


def run_streams_backfill(supabase: Client, settings: Settings, athlete_id: int) -> None:
    """Compute and store compact metrics for activities lacking an activity_metrics row.

    Storage-protective: fetches streams to compute the histograms but stores ONLY the
    metrics row (never the full stream blob) for un-viewed rides. Resumable (a metrics
    row's existence is the marker), paced (~12/min) with 429 backoff, token re-validated
    each iteration; one transient error skips the activity, never aborts the batch.
    """
    strava = build_strava(settings)
    try:
        ids = metrics_db.list_activity_ids_needing_metrics(supabase, athlete_id)
        for activity_id in ids:
            try:
                access_token = get_valid_access_token(supabase, strava, athlete_id)
                data = _fetch_streams_with_backoff(strava, access_token, activity_id, STREAM_KEYS)
                row = {"activity_id": activity_id, "athlete_id": athlete_id,
                       **analysis.compute_metrics(data)}
                metrics_db.upsert_metrics(supabase, row)  # type: ignore[arg-type]
            except Exception:
                logger.exception("Streams backfill: skipping activity %s", activity_id)
            time.sleep(DETAIL_PAUSE_S)
    except Exception:
        logger.exception("Streams backfill failed for athlete %s", athlete_id)
    finally:
        strava.close()
```

> Note for the implementer: `from app.services.activities import STREAM_KEYS` is safe — `activities` does not import `sync`, so there is no import cycle. If mypy/ruff flags an unused-import edge, keep the import (it is used in `run_streams_backfill`).

- [ ] **Step 4: Run to verify pass (full sync suite stays green)**

Run: `cd backend && pytest tests/services/test_sync.py -v && ruff check . && mypy`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/sync.py backend/tests/services/test_sync.py
git commit -m "feat(sync): run_streams_backfill — paced, resumable metrics-only pass"
```

---

## Task 8: `run_avg_watts_backfill` — one-off history re-list

**Files:**
- Modify: `backend/app/services/sync.py`
- Test: `backend/tests/services/test_sync.py`

**Interfaces:**
- Produces: `run_avg_watts_backfill(supabase, settings, athlete_id) -> None` — re-lists all activities (paged, `after=None`) and upserts; populates `avg_watts` on existing rows. Idempotent; partial-column upsert preserves `is_pr`/`detail_fetched_at`/`splits_metric`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_sync.py`:

```python
def test_run_avg_watts_backfill_relists_and_upserts(monkeypatch):
    upserted_rows = []

    class FakeStrava:
        def __init__(self):
            self.pages = {1: [{"id": 1, "name": "R", "type": "Ride",
                               "start_date": "2026-06-15T08:00:00Z", "distance": 1.0,
                               "moving_time": 1, "elapsed_time": 1, "total_elevation_gain": 0.0,
                               "average_watts": 210.0}]}

        def list_activities(self, access_token, *, page, per_page=200, after=None):
            return self.pages.get(page, [])

        def close(self):
            pass

    monkeypatch.setattr(sync_service, "build_strava", lambda settings: FakeStrava())
    monkeypatch.setattr(sync_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    monkeypatch.setattr(sync_service.activities_db, "upsert_activities",
                        lambda supabase, rows: upserted_rows.extend(rows))

    sync_service.run_avg_watts_backfill(FakeSupabase(), settings=object(), athlete_id=7)
    assert len(upserted_rows) == 1 and upserted_rows[0]["avg_watts"] == 210.0
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/services/test_sync.py -k avg_watts_backfill -v`
Expected: FAIL with `AttributeError: ... 'run_avg_watts_backfill'`.

- [ ] **Step 3: Implement**

Add to `backend/app/services/sync.py` (after `run_avg_watts`... place near the other backfills):

```python
def run_avg_watts_backfill(supabase: Client, settings: Settings, athlete_id: int) -> None:
    """One-off: re-list every activity and upsert so avg_watts (added in 0008) is
    populated for historical rows. Partial-column upsert preserves is_pr / detail
    columns. Idempotent — safe to re-run."""
    strava = build_strava(settings)
    try:
        access_token = get_valid_access_token(supabase, strava, athlete_id)
        page = 1
        while True:
            summaries = strava.list_activities(access_token, page=page, per_page=PER_PAGE)
            if not summaries:
                break
            rows = [_to_activity_row(athlete_id, s) for s in summaries]
            activities_db.upsert_activities(supabase, rows)  # type: ignore[arg-type]
            if len(summaries) < PER_PAGE:
                break
            page += 1
    except Exception:
        logger.exception("avg_watts backfill failed for athlete %s", athlete_id)
    finally:
        strava.close()
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && pytest tests/services/test_sync.py -v && ruff check . && mypy`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/sync.py backend/tests/services/test_sync.py
git commit -m "feat(sync): run_avg_watts_backfill — one-off history re-list for avg_watts"
```

---

## Task 9: `get_overview` — `top_avg_power_w` stat

**Files:**
- Modify: `backend/app/models/activities.py:33-39` (`OverviewSummary`)
- Modify: `backend/app/services/activities.py:130-138` (`_summary`)
- Test: `backend/tests/services/test_activities.py`

**Interfaces:**
- Produces: `OverviewSummary.top_avg_power_w: float | None`; `_summary` sets it to `max(avg_watts over rows)` or `None`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/services/test_activities.py`. Note the `_row` helper currently emits no `avg_watts`; add a local helper for power rows:

```python
def _power_row(id, date_local, watts):
    r = _row(id, date_local, 10000.0, 1000, 100.0, 10.0)
    r["avg_watts"] = watts
    return r


def test_top_avg_power_is_max_over_period(monkeypatch):
    rows = [_power_row(10, "2026-06-16T10:00:00", 180.0),
            _power_row(11, "2026-06-17T09:00:00", 245.0)]
    _patch(monkeypatch, rows, [])
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.summary.top_avg_power_w == 245.0


def test_top_avg_power_none_when_no_power(monkeypatch):
    _patch(monkeypatch, THIS_WEEK, [])   # THIS_WEEK rows have no avg_watts key
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.summary.top_avg_power_w is None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/services/test_activities.py -k top_avg_power -v`
Expected: FAIL — `AttributeError: 'OverviewSummary' object has no attribute 'top_avg_power_w'`.

- [ ] **Step 3: Implement**

In `backend/app/models/activities.py`, add to `OverviewSummary`:

```python
    top_avg_power_w: float | None = None
```

In `backend/app/services/activities.py`, update `_summary` to compute it:

```python
def _summary(rows: list[ActivityRow]) -> OverviewSummary:
    speeds = [r["avg_speed_ms"] for r in rows if r["avg_speed_ms"] is not None]
    powers = [r["avg_watts"] for r in rows if r.get("avg_watts")]
    return OverviewSummary(
        rides=len(rows),
        prs=sum(1 for r in rows if r.get("is_pr")),
        top_speed_ms=max(speeds) if speeds else None,
        top_avg_power_w=max(powers) if powers else None,
        longest_ride_m=max((r["distance_m"] for r in rows), default=0.0),
        max_elev_m=max((r["elev_gain_m"] for r in rows), default=0.0),
    )
```

- [ ] **Step 4: Run to verify pass (existing overview tests stay green)**

Run: `cd backend && pytest tests/services/test_activities.py -v && ruff check . && mypy`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/activities.py backend/app/services/activities.py backend/tests/services/test_activities.py
git commit -m "feat(overview): top_avg_power_w stat (max avg_watts over the period)"
```

---

## Task 10: `get_overview` — period power/HR zone panels

**Files:**
- Modify: `backend/app/models/activities.py:57-67` (`OverviewResponse`)
- Modify: `backend/app/services/activities.py` (imports already have `athletes_db`/`metrics_db` after Task 6; add `_period_zones`, fetch settings in `get_overview`, wire response)
- Test: `backend/tests/services/test_activities.py`

**Interfaces:**
- Consumes: `athletes_db.get_athlete`, `metrics_db.list_metrics_for_activities`, `analysis.power_zones`/`hr_zones`/`zone_seconds_from_histogram`/`buckets_from_zone_seconds`/`POWER_BIN_W`/`HR_BIN_BPM`, `ZoneBucket`/`ZonesBlock`.
- Produces: `OverviewResponse.power_zones: ZonesBlock`, `OverviewResponse.hr_zones: ZonesBlock`; `_period_zones(supabase, athlete_id, this_rows, settings) -> tuple[ZonesBlock, ZonesBlock]`.

- [ ] **Step 1: Update `_patch` so existing tests survive the new settings/metrics reads, then write the failing zone tests**

In `backend/tests/services/test_activities.py`, extend `_patch` to stub the two new dependencies (default: no FTP/HR, no metrics):

```python
def _patch(monkeypatch, since_rows, recent_rows, *, settings=None, metrics=None):
    monkeypatch.setattr(activities_service.activities_db, "list_activities_since",
                        lambda supabase, athlete_id, since_iso: since_rows)
    monkeypatch.setattr(activities_service.activities_db, "list_recent_activities",
                        lambda supabase, athlete_id, limit: recent_rows)
    monkeypatch.setattr(activities_service.athletes_db, "get_athlete",
                        lambda supabase, athlete_id: {"settings": settings or {}})
    monkeypatch.setattr(activities_service.metrics_db, "list_metrics_for_activities",
                        lambda supabase, athlete_id, ids: metrics or [])
```

Add the zone tests:

```python
def test_period_zones_unset_without_ftp_or_hr_max(monkeypatch):
    _patch(monkeypatch, THIS_WEEK, [])
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.power_zones.unset is True
    assert ov.hr_zones.unset is True


def test_period_zones_buckets_from_summed_histograms(monkeypatch):
    rows = [_row(20, "2026-06-16T10:00:00", 10000.0, 1000, 100.0, 10.0)]
    # ftp=200 → Z1 [0,110); midpoint of bin 5 = 55 W → Z1. 9 weighted seconds.
    phist = [0.0] * 150
    phist[5] = 9.0
    met = [{"activity_id": 20, "athlete_id": 7, "avg_power_w": 100.0, "np_w": None,
            "work_kj": None, "power_hist": phist, "hr_hist": None,
            "has_power": True, "has_hr": False}]
    _patch(monkeypatch, rows, [], settings={"ftp_w": 200}, metrics=met)
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.power_zones.unset is False
    by_z = {b.z: b for b in ov.power_zones.buckets}
    assert by_z["Z1"].seconds == 9 and by_z["Z1"].pct == 100.0
    assert ov.hr_zones.unset is True   # hr_max still missing


def test_period_zones_configured_but_no_data_is_zeroed(monkeypatch):
    _patch(monkeypatch, THIS_WEEK, [], settings={"ftp_w": 200, "hr_max": 190}, metrics=[])
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.power_zones.unset is False
    assert all(b.seconds == 0 for b in ov.power_zones.buckets)
    assert ov.hr_zones.unset is False
    assert len(ov.hr_zones.buckets) == 5
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/services/test_activities.py -k period_zones -v`
Expected: FAIL — `AttributeError: 'OverviewResponse' object has no attribute 'power_zones'`.

- [ ] **Step 3: Implement**

In `backend/app/models/activities.py`, add to `OverviewResponse` (after `week_distance_m`):

```python
    power_zones: ZonesBlock = ZonesBlock(unset=True)
    hr_zones: ZonesBlock = ZonesBlock(unset=True)
```

(`ZonesBlock` is already imported in this module — it is used by `ActivityDetailResponse`.)

In `backend/app/services/activities.py`, add `_period_zones` (place above `get_overview`):

```python
def _zones_from_hists(
    hists: list[list[float]], bin_w: int, zone_defs: list[dict]
) -> ZonesBlock:
    summed = [0.0] * len(hists[0])
    for h in hists:
        for i, s in enumerate(h):
            summed[i] += s
    secs = analysis.zone_seconds_from_histogram(summed, bin_w, zone_defs)
    buckets = [ZoneBucket(**b) for b in analysis.buckets_from_zone_seconds(secs, zone_defs)]
    return ZonesBlock(unset=False, avg=None, buckets=buckets)


def _period_zones(
    supabase: Client, athlete_id: int, this_rows: list[ActivityRow], settings: dict
) -> tuple[ZonesBlock, ZonesBlock]:
    ftp = settings.get("ftp_w")
    hr_max = settings.get("hr_max")
    ids = [r["id"] for r in this_rows]
    rows = metrics_db.list_metrics_for_activities(supabase, athlete_id, ids) if (ftp or hr_max) else []

    def block(active: int | None, key: str, bin_w: int, zone_defs: list[dict]) -> ZonesBlock:
        if not active:
            return ZonesBlock(unset=True)
        hists = [m[key] for m in rows if m.get(key)]
        if not hists:
            return _zones_from_hists([[0.0] * 1], bin_w, zone_defs)  # zeroed buckets
        return _zones_from_hists(hists, bin_w, zone_defs)

    power = block(ftp, "power_hist", analysis.POWER_BIN_W,
                  analysis.power_zones(ftp) if ftp else [])
    hr = block(hr_max, "hr_hist", analysis.HR_BIN_BPM,
               analysis.hr_zones(hr_max) if hr_max else [])
    return power, hr
```

> Implementer note on the zeroed-buckets path: `_zones_from_hists([[0.0]*1], …)` sums a single 1-bin zero histogram, so `zone_seconds_from_histogram` returns all-zero per-zone seconds → `buckets_from_zone_seconds` yields zero-pct buckets aligned to `zone_defs`. (The bin count of the placeholder is irrelevant when every value is zero.)

In `get_overview`, fetch settings once and wire the blocks. After the `this_rows`/`last_rows` computation, add:

```python
    athlete_row = athletes_db.get_athlete(supabase, athlete_id)
    settings: dict = athlete_row.get("settings", {}) if athlete_row else {}
    power_zones, hr_zones = _period_zones(supabase, athlete_id, this_rows, settings)
```

Add `power_zones=power_zones, hr_zones=hr_zones,` to the `OverviewResponse(...)` constructor.

- [ ] **Step 4: Run to verify pass (all overview tests stay green)**

Run: `cd backend && pytest tests/services/test_activities.py tests/routers/test_activities.py -v && ruff check . && mypy`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/activities.py backend/app/services/activities.py backend/tests/services/test_activities.py
git commit -m "feat(overview): selector-scoped power/HR zone panels from summed histograms"
```

---

## Task 11: Chain `run_streams_backfill` on `POST /sync/start`

**Files:**
- Modify: `backend/app/routers/sync.py:28-35`
- Test: `backend/tests/routers/test_sync.py`

**Interfaces:**
- Consumes: `sync_service.run_streams_backfill`.

- [ ] **Step 1: Update the failing test**

In `backend/tests/routers/test_sync.py`, update `test_start_schedules_backfill_when_started` to also assert the streams task is scheduled:

```python
def test_start_schedules_backfill_when_started(client, monkeypatch):
    spawned = {}
    monkeypatch.setattr(sync_service, "start_backfill",
                        lambda supabase, athlete_id: (
                            SyncStatusResponse(status="backfilling", progress=0, synced=0), True))
    monkeypatch.setattr(sync_service, "run_backfill",
                        lambda supabase, settings, athlete_id: spawned.update(backfill=athlete_id))
    monkeypatch.setattr(sync_service, "run_detail_backfill",
                        lambda supabase, settings, athlete_id: spawned.update(detail=athlete_id))
    monkeypatch.setattr(sync_service, "run_streams_backfill",
                        lambda supabase, settings, athlete_id: spawned.update(streams=athlete_id))
    _auth(client)
    response = client.post("/sync/start")
    assert response.status_code == 200
    assert spawned == {"backfill": 99, "detail": 99, "streams": 99}
```

Also add `run_streams_backfill` to the `test_start_does_not_reschedule_when_already_running` patches so it doesn't hit the real function:

```python
    monkeypatch.setattr(sync_service, "run_streams_backfill",
                        lambda supabase, settings, athlete_id: None)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/routers/test_sync.py -k start -v`
Expected: FAIL — `spawned` missing `"streams"`.

- [ ] **Step 3: Implement**

In `backend/app/routers/sync.py`, inside the `if started:` block of `start`, add after the `run_detail_backfill` task:

```python
        background_tasks.add_task(
            sync_service.run_streams_backfill, supabase, settings, athlete_id
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && pytest tests/routers/test_sync.py -v && ruff check . && mypy`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/sync.py backend/tests/routers/test_sync.py
git commit -m "feat(sync): chain run_streams_backfill on POST /sync/start"
```

---

## Task 12 (DEFERRABLE): `get_detail` reads precomputed metrics

> **Implement only if Tasks 1–11 land green with time to spare.** Otherwise skip and track as the existing [[peakstats-activity-detail-perf]] follow-up — Phase 3's user-facing scope is complete after Task 11. This task is purely a detail-page perf win.

**Files:**
- Modify: `backend/app/services/activities.py` (`get_detail`)
- Test: `backend/tests/services/test_activities_detail.py`

**Interfaces:**
- Consumes: `metrics_db.get_metrics`, `analysis.zone_seconds_from_histogram`/`buckets_from_zone_seconds`/`power_zones`/`hr_zones`/`POWER_BIN_W`/`HR_BIN_BPM`.

- [ ] **Step 1: Write the failing test** — when a metrics row exists, `get_detail` derives zones from histograms without calling `ensure_streams`.

Append to `backend/tests/services/test_activities_detail.py` (mirror the file's existing patching style; patch `svc.metrics_db.get_metrics` to return a row and patch `svc.ensure_streams` to raise if called):

```python
def test_get_detail_uses_metrics_without_streams(monkeypatch):
    phist = [0.0] * 150
    phist[20] = 60.0  # midpoint 205 W
    monkeypatch.setattr(svc.activities_db, "get_activity",
        lambda c, a, i: {"id": i, "name": "R", "type": "Ride",
                         "start_date": "2026-06-16T10:00:00Z", "start_date_local": None,
                         "distance_m": 1.0, "moving_time_s": 1, "elev_gain_m": 0.0,
                         "avg_speed_ms": None, "avg_hr": None, "summary_polyline": None})
    monkeypatch.setattr(svc.metrics_db, "get_metrics",
        lambda c, i: {"activity_id": i, "athlete_id": 7, "avg_power_w": 205.0,
                      "np_w": 210.0, "work_kj": 50.0, "power_hist": phist, "hr_hist": None,
                      "has_power": True, "has_hr": False})
    monkeypatch.setattr(svc.athletes_db, "get_athlete",
        lambda c, a: {"settings": {"ftp_w": 200}})
    monkeypatch.setattr(svc.activities_db, "list_activity_climbs", lambda c, a, i: [])

    def boom(*a, **k):
        raise AssertionError("must not fetch streams when metrics exist")

    monkeypatch.setattr(svc, "ensure_streams", boom)
    detail = svc.get_detail(object(), object(), 7, 5)
    assert detail.avg_power_w == 205.0 and detail.work_kj == 50.0
    assert detail.power_zones.unset is False
    assert detail.hr_zones.unset is True
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/services/test_activities_detail.py -k uses_metrics -v`
Expected: FAIL (currently `get_detail` calls `ensure_streams` unconditionally → `AssertionError`).

- [ ] **Step 3: Implement** — branch on a precomputed metrics row; fall back to the current stream path.

In `backend/app/services/activities.py`, add a metrics-derived zone helper and branch at the top of `get_detail` after loading `row`:

```python
def _zones_from_metrics_hist(
    hist: list[float] | None, bin_w: int, zone_defs: list[dict], bound: int | None
) -> ZonesBlock:
    if not bound or not hist:
        return ZonesBlock(unset=True)
    secs = analysis.zone_seconds_from_histogram(hist, bin_w, zone_defs)
    buckets = [ZoneBucket(**b) for b in analysis.buckets_from_zone_seconds(secs, zone_defs)]
    return ZonesBlock(unset=False, avg=None, buckets=buckets)
```

In `get_detail`, after `row = ...` / not-found guard, insert the fast path:

```python
    metrics = metrics_db.get_metrics(supabase, activity_id)
    if metrics is not None:
        athlete_row = athletes_db.get_athlete(supabase, athlete_id)
        settings = athlete_row.get("settings", {}) if athlete_row else {}
        ftp, hr_max = settings.get("ftp_w"), settings.get("hr_max")
        climbs = _detail_climbs(supabase, athlete_id, activity_id)
        return ActivityDetailResponse(
            id=row["id"], name=row["name"], type=row["type"],
            start_date=row["start_date"], start_date_local=row.get("start_date_local"),
            location=None, distance_m=row["distance_m"], moving_time_s=row["moving_time_s"],
            elev_gain_m=row["elev_gain_m"], avg_speed_ms=row.get("avg_speed_ms"),
            avg_power_w=metrics["avg_power_w"], normalized_power_w=metrics["np_w"],
            work_kj=metrics["work_kj"], avg_hr=row.get("avg_hr"),
            summary_polyline=row.get("summary_polyline"),
            power_zones=_zones_from_metrics_hist(
                metrics["power_hist"], analysis.POWER_BIN_W,
                analysis.power_zones(ftp) if ftp else [], ftp),
            hr_zones=_zones_from_metrics_hist(
                metrics["hr_hist"], analysis.HR_BIN_BPM,
                analysis.hr_zones(hr_max) if hr_max else [], hr_max),
            climbs=climbs,
        )
```

Extract the existing climbs block into `_detail_climbs(supabase, athlete_id, activity_id) -> list[ClimbItem]` (lift the current `climb_rows`/`climbs` construction verbatim) and call it from both the fast path and the existing stream path so the climb logic stays DRY and unchanged.

- [ ] **Step 4: Run to verify pass (all detail tests green)**

Run: `cd backend && pytest tests/services/test_activities_detail.py -v && ruff check . && mypy`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/activities.py backend/tests/services/test_activities_detail.py
git commit -m "perf(detail): serve get_detail zones/scalars from activity_metrics when present"
```

---

## Task 13: Frontend — promote shared zone types + mapper

**Files:**
- Create: `frontend/src/types/zones.ts`
- Create: `frontend/src/api/zones.ts`
- Modify: `frontend/src/types/activity-detail.ts:1-2` (re-export)
- Modify: `frontend/src/api/activity-detail.ts:96-118` (re-export)

**Interfaces:**
- Produces (in `types/zones.ts`): `ZoneBucketDTO`, `ZonesBlockDTO`.
- Produces (in `api/zones.ts`): `ZoneRowVM`, `zoneColor(index: number): string`, `toZoneRows(block: ZonesBlockDTO): ZoneRowVM[]`.

This is a pure refactor: the existing activity-detail tests (`api/activity-detail.test.ts`, `pages/activity-detail/components/ZonesPanel.test.tsx`) are the safety net — they must stay green with **no edits**.

- [ ] **Step 1: Create the shared type module**

`frontend/src/types/zones.ts`:

```typescript
export interface ZoneBucketDTO { z: string; name: string; range: string; seconds: number; pct: number }
export interface ZonesBlockDTO { unset: boolean; avg: number | null; buckets: ZoneBucketDTO[] }
```

- [ ] **Step 2: Create the shared mapper module**

`frontend/src/api/zones.ts` (move the body verbatim from `api/activity-detail.ts`):

```typescript
import { fmtDuration } from "@/lib/format";
import type { ZonesBlockDTO } from "@/types/zones";

export interface ZoneRowVM {
  z: string; name: string; range: string; color: string;
  barW: string; dur: string; pctLabel: string;
}

// Reference the raw --zone-N vars (always emitted in :root/.dark), not the
// @theme `--color-zone-N` aliases — Tailwind tree-shakes aliases whose names
// aren't statically visible, and these names are built dynamically.
export function zoneColor(index: number): string {
  return `var(--zone-${Math.min(index + 1, 7)})`;
}

export function toZoneRows(block: ZonesBlockDTO): ZoneRowVM[] {
  return block.buckets.map((b, i) => ({
    z: b.z, name: b.name, range: b.range, color: zoneColor(i),
    barW: `${Math.min(100, b.pct).toFixed(1)}%`,
    dur: fmtDuration(b.seconds),
    pctLabel: `${Math.round(b.pct)}%`,
  }));
}
```

- [ ] **Step 3: Re-point the activity-detail modules at the shared ones (back-compat)**

In `frontend/src/types/activity-detail.ts`, replace lines 1–2 (the two interface declarations) with:

```typescript
export type { ZoneBucketDTO, ZonesBlockDTO } from "./zones";
```

In `frontend/src/api/activity-detail.ts`, remove the `ZoneRowVM`/`zoneColor`/`toZoneRows` block (lines ~96–118) **and** the now-redundant `import type { ZonesBlockDTO } from "@/types/activity-detail";` at line 96, and re-export instead (place near the other exports):

```typescript
export { type ZoneRowVM, zoneColor, toZoneRows } from "./zones";
```

(`ZonesPanel.tsx` imports `toZoneRows` from `@/api/activity-detail` and `ZonesBlockDTO` from `@/types/activity-detail` — both still resolve via the re-exports, so no component edits are needed.)

- [ ] **Step 4: Run the full frontend gate to confirm the refactor is behavior-preserving**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: PASS — every existing test (including `ZonesPanel` + `activity-detail` mapper) green; no type errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/zones.ts frontend/src/api/zones.ts \
        frontend/src/types/activity-detail.ts frontend/src/api/activity-detail.ts
git commit -m "refactor(zones): promote shared zone DTOs + toZoneRows mapper to shared modules"
```

---

## Task 14: Frontend — overview DTO + mapper (`topAvgPower` + zone blocks)

**Files:**
- Modify: `frontend/src/types/overview.ts`
- Modify: `frontend/src/api/overview.ts`
- Test: `frontend/src/api/overview.test.ts`

**Interfaces:**
- Produces (types): `OverviewSummaryDTO.top_avg_power_w: number | null`; `OverviewDTO.power_zones`/`hr_zones: ZonesBlockDTO`; `SummaryView.topAvgPower: string`; `DashboardOverview.powerZones`/`hrZones: ZonesBlockDTO`.
- Consumes: `ZonesBlockDTO` from `@/types/zones`.

- [ ] **Step 1: Write the failing tests**

In `frontend/src/api/overview.test.ts`, extend the `DTO` fixture (add the three fields) and add assertions. Append to the fixture object (before the closing `}`):

```typescript
  // add to the `summary` object: top_avg_power_w
  // add at top level:
  power_zones: {
    unset: false, avg: 210,
    buckets: [
      { z: "Z1", name: "Active Rec.", range: "< 110 W", seconds: 600, pct: 25 },
      { z: "Z2", name: "Endurance", range: "110–150 W", seconds: 1800, pct: 75 },
    ],
  },
  hr_zones: { unset: true, avg: null, buckets: [] },
```

(Set `summary: { rides: 6, prs: 2, top_speed_ms: 11.0, top_avg_power_w: 287, longest_ride_m: 64000, max_elev_m: 980 }`.)

Add tests:

```typescript
  it("formats top avg power in watts (no unit conversion)", () => {
    expect(toOverview(DTO, "metric").summary.topAvgPower).toBe("287 W");
    expect(toOverview(DTO, "imperial").summary.topAvgPower).toBe("287 W");
  });

  it("renders an em dash when no ride has power", () => {
    const dto = { ...DTO, summary: { ...DTO.summary, top_avg_power_w: null } };
    expect(toOverview(dto, "metric").summary.topAvgPower).toBe("—");
  });

  it("passes the power/HR zone blocks through unchanged", () => {
    const ov = toOverview(DTO, "metric");
    expect(ov.powerZones.buckets).toHaveLength(2);
    expect(ov.powerZones.unset).toBe(false);
    expect(ov.hrZones.unset).toBe(true);
  });
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test -- overview.test.ts`
Expected: FAIL — `topAvgPower`/`powerZones` undefined.

- [ ] **Step 3: Implement**

In `frontend/src/types/overview.ts`:
- add `import type { ZonesBlockDTO } from "@/types/zones";` at the top;
- add `top_avg_power_w: number | null;` to `OverviewSummaryDTO`;
- add `power_zones: ZonesBlockDTO;` and `hr_zones: ZonesBlockDTO;` to `OverviewDTO`;
- add `topAvgPower: string;` to `SummaryView`;
- add `powerZones: ZonesBlockDTO;` and `hrZones: ZonesBlockDTO;` to `DashboardOverview`.

In `frontend/src/api/overview.ts`, inside `toOverview`, add `topAvgPower` to the returned `summary` object:

```typescript
      topAvgPower: dto.summary.top_avg_power_w != null
        ? `${Math.round(dto.summary.top_avg_power_w)} W` : "—",
```

and add to the returned object (alongside `goal`):

```typescript
    powerZones: dto.power_zones,
    hrZones: dto.hr_zones,
```

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npm test -- overview.test.ts && npm run lint && npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/overview.ts frontend/src/api/overview.ts frontend/src/api/overview.test.ts
git commit -m "feat(overview): map top avg power + pass power/HR zone blocks to the dashboard"
```

---

## Task 15: Frontend — `ZonePanel` component

**Files:**
- Create: `frontend/src/pages/app-home/components/ZonePanel.tsx`
- Test: `frontend/src/pages/app-home/components/ZonePanel.test.tsx`

**Interfaces:**
- Consumes: `ZonesBlockDTO` (`@/types/zones`), `toZoneRows` (`@/api/zones`).
- Produces: `ZonePanel({ title, caption, kind, block }: { title: string; caption: string; kind: "power" | "hr"; block: ZonesBlockDTO })`.

States: `block.unset` → "Set your FTP/Max HR in Settings" prompt; configured but all buckets zero → "No power/heart-rate data for this period"; else one row per zone.

- [ ] **Step 1: Write the failing tests**

`frontend/src/pages/app-home/components/ZonePanel.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import type { ZonesBlockDTO } from "@/types/zones";
import { ZonePanel } from "./ZonePanel";

function renderPanel(block: ZonesBlockDTO, kind: "power" | "hr" = "power") {
  render(
    <MemoryRouter>
      <ZonePanel title="Power zones" caption="THIS WEEK" kind={kind} block={block} />
    </MemoryRouter>,
  );
}

describe("ZonePanel", () => {
  it("renders a row per zone with label, range and percentage", () => {
    renderPanel({
      unset: false, avg: null,
      buckets: [
        { z: "Z1", name: "Active Rec.", range: "< 110 W", seconds: 600, pct: 25 },
        { z: "Z2", name: "Endurance", range: "110–150 W", seconds: 1800, pct: 75 },
      ],
    });
    expect(screen.getByText("Power zones")).toBeInTheDocument();
    expect(screen.getByText("THIS WEEK")).toBeInTheDocument();
    expect(screen.getByText("Z1 · Active Rec.")).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();
  });

  it("shows the FTP prompt when power is unset", () => {
    renderPanel({ unset: true, avg: null, buckets: [] }, "power");
    expect(screen.getByText(/Set your FTP/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /settings/i })).toHaveAttribute("href", "/settings");
  });

  it("shows the Max HR prompt when hr is unset", () => {
    renderPanel({ unset: true, avg: null, buckets: [] }, "hr");
    expect(screen.getByText(/Set your Max HR/i)).toBeInTheDocument();
  });

  it("shows a no-data message when configured but the period has no data", () => {
    renderPanel({
      unset: false, avg: null,
      buckets: [{ z: "Z1", name: "Active Rec.", range: "< 110 W", seconds: 0, pct: 0 }],
    }, "power");
    expect(screen.getByText(/No power data for this period/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test -- ZonePanel.test.tsx`
Expected: FAIL — cannot resolve `./ZonePanel`.

- [ ] **Step 3: Implement** (mirrors the detail page's `ZonesPanel` markup + token classes)

`frontend/src/pages/app-home/components/ZonePanel.tsx`:

```typescript
import { Link } from "react-router";
import { toZoneRows } from "@/api/zones";
import type { ZonesBlockDTO } from "@/types/zones";

type Kind = "power" | "hr";

const PROMPT: Record<Kind, { setting: string; noData: string }> = {
  power: { setting: "Set your FTP", noData: "No power data for this period" },
  hr: { setting: "Set your Max HR", noData: "No heart-rate data for this period" },
};

export function ZonePanel(
  { title, caption, kind, block }: { title: string; caption: string; kind: Kind; block: ZonesBlockDTO },
) {
  const rows = toZoneRows(block);
  const hasData = !block.unset && block.buckets.some((b) => b.seconds > 0);
  const copy = PROMPT[kind];
  return (
    <div className="bg-surface-card border border-line rounded-2xl px-[22px] py-5 transition-colors duration-300">
      <div className="flex items-center justify-between mb-4">
        <span className="font-display font-medium text-[15px] text-ink">{title}</span>
        <span className="font-mono text-[9px] tracking-[0.1em] text-subtle">{caption}</span>
      </div>
      {block.unset ? (
        <div className="text-[13px] text-subtle py-6 text-center">
          {copy.setting} in{" "}
          <Link to="/settings" className="text-strava hover:underline">Settings</Link>{" "}
          to see zones.
        </div>
      ) : !hasData ? (
        <div className="text-[13px] text-subtle py-6 text-center">{copy.noData}</div>
      ) : (
        <div className="flex flex-col gap-[11px]">
          {rows.map((r) => (
            <div key={r.z} className="flex items-center gap-3">
              <span className="w-[9px] h-[9px] rounded-[3px] flex-none" style={{ background: r.color }} />
              <div className="w-[132px] flex-none">
                <div className="text-[12.5px] font-medium text-ink">{r.z} · {r.name}</div>
                <div className="font-mono text-[9.5px] text-faint mt-px">{r.range}</div>
              </div>
              <div className="flex-1 h-[13px] bg-track rounded-[4px] overflow-hidden">
                <div className="h-full rounded-[4px]" style={{ width: r.barW, background: r.color }} />
              </div>
              <span className="font-mono text-[11px] text-subtle w-[34px] text-right flex-none">{r.pctLabel}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

> Token note: `text-ink`/`text-subtle`/`text-faint`/`bg-track`/`bg-surface-card`/`border-line` are all existing utilities (`bg-track` maps to `--track`, both themes). Zone bar colors come from `r.color` (the `--zone-*` vars) — the documented chart-color exception.

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npm test -- ZonePanel.test.tsx && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/app-home/components/ZonePanel.tsx frontend/src/pages/app-home/components/ZonePanel.test.tsx
git commit -m "feat(overview): ZonePanel — power/HR zone bars with unset + no-data states"
```

---

## Task 16: Frontend — `SummaryCard` "TOP AVG POWER" row

**Files:**
- Modify: `frontend/src/pages/app-home/components/SummaryCard.tsx`
- Test: `frontend/src/pages/app-home/components/SummaryCard.test.tsx` (new)

**Interfaces:**
- Consumes: `SummaryView.topAvgPower`.

- [ ] **Step 1: Write the failing test**

`frontend/src/pages/app-home/components/SummaryCard.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SummaryView } from "@/types/overview";
import { SummaryCard } from "./SummaryCard";

const summary: SummaryView = {
  rides: "12", prs: "2", topSpeed: "42.0 km/h", topAvgPower: "287 W",
  longestRide: "64.0 km", maxElev: "980 m",
};

describe("SummaryCard", () => {
  it("renders the Top avg power stat", () => {
    render(<SummaryCard summary={summary} />);
    expect(screen.getByText("TOP AVG POWER")).toBeInTheDocument();
    expect(screen.getByText("287 W")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test -- SummaryCard.test.tsx`
Expected: FAIL — "TOP AVG POWER" not found.

- [ ] **Step 3: Implement**

In `frontend/src/pages/app-home/components/SummaryCard.tsx`, add the row to `stats` (after Top avg speed) and widen the grid from 5 to 6 columns:

```typescript
  const stats: { label: string; value: string; accent?: boolean }[] = [
    { label: "RIDES", value: summary.rides },
    { label: "PERSONAL RECORDS", value: summary.prs, accent: true },
    { label: "TOP AVG SPEED", value: summary.topSpeed },
    { label: "TOP AVG POWER", value: summary.topAvgPower },
    { label: "LONGEST RIDE", value: summary.longestRide },
    { label: "MAX ELEV GAIN", value: summary.maxElev },
  ];
```

Change the grid class `grid-cols-5` → `grid-cols-6`:

```typescript
      <div className="grid grid-cols-6 gap-4 max-[1024px]:grid-cols-2">
```

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npm test -- SummaryCard.test.tsx && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/app-home/components/SummaryCard.tsx frontend/src/pages/app-home/components/SummaryCard.test.tsx
git commit -m "feat(overview): Top avg power stat in the Weekly Highlights card"
```

---

## Task 17: Frontend — compose the Phase 3 zone row into `AppHome`

**Files:**
- Modify: `frontend/src/pages/app-home/AppHome.tsx`
- Test: `frontend/src/pages/app-home/AppHome.test.tsx`

**Interfaces:**
- Consumes: `overview.powerZones`, `overview.hrZones`, `overview.headline.periodLabel` (the existing "THIS WEEK"/… caption).

Per `overview.png`: the `SummaryCard` becomes the first cell of a three-up row with the two zone panels beside it, sitting above the heatmap/goal row.

- [ ] **Step 1: Update the page test fixture + add the assertion**

In `frontend/src/pages/app-home/AppHome.test.tsx`, add zone blocks to the `overview` fixture (alongside `goal`):

```typescript
  powerZones: {
    unset: false, avg: 210,
    buckets: [{ z: "Z1", name: "Active Rec.", range: "< 110 W", seconds: 600, pct: 100 }],
  },
  hrZones: { unset: true, avg: null, buckets: [] },
```

In the `"renders the headline, secondary KPIs, summary, and recent rides when loaded"` test, add:

```typescript
    expect(screen.getByText("Power zones")).toBeInTheDocument();
    expect(screen.getByText("Heart-rate zones")).toBeInTheDocument();
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npm test -- AppHome.test.tsx`
Expected: FAIL — "Power zones" not found.

- [ ] **Step 3: Implement**

In `frontend/src/pages/app-home/AppHome.tsx`:
- import the component: `import { ZonePanel } from "./components/ZonePanel";`
- replace the standalone `<SummaryCard ... />` line with the three-up row:

```tsx
            <div className="grid grid-cols-[1.1fr_1fr_1fr] gap-4 mb-4 max-[1024px]:grid-cols-1">
              <SummaryCard summary={overview.summary} />
              <ZonePanel
                title="Power zones"
                caption={overview.headline.periodLabel}
                kind="power"
                block={overview.powerZones}
              />
              <ZonePanel
                title="Heart-rate zones"
                caption={overview.headline.periodLabel}
                kind="hr"
                block={overview.hrZones}
              />
            </div>
```

> Note: `SummaryCard` already carries its own `mb-4`; inside the grid that bottom margin is harmless, but for tidiness the grid wrapper owns the spacing. Leaving `SummaryCard`'s `mb-4` is acceptable (the page test only checks presence). If lint/visual review prefers, drop `mb-4` from `SummaryCard`'s root in this task — optional.

- Extend `SkeletonPanels` so the loading state previews the new row. Add a third skeleton block after the existing two:

```tsx
      <div className="grid grid-cols-[1.1fr_1fr_1fr] gap-4 mb-4 max-[1024px]:grid-cols-1">
        {[0, 1, 2].map((i) => (
          <div key={i} className="bg-surface-card border border-line rounded-2xl p-5">
            <div className="h-[140px] rounded-[10px] bg-skel animate-pkskel" />
          </div>
        ))}
      </div>
```

- [ ] **Step 4: Run to verify pass + full frontend gate**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: PASS — all suites green, no type errors, build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/app-home/AppHome.tsx frontend/src/pages/app-home/AppHome.test.tsx
git commit -m "feat(overview): compose Summary + power/HR zone panels into the Phase 3 row"
```

---

## Final verification (before merge)

- [ ] **Backend gate:** `cd backend && pytest && ruff check . && mypy` — all green.
- [ ] **Frontend gate:** `cd frontend && npm test && npm run lint && npm run build` — all green.
- [ ] **Diff review:** `git log --oneline main..HEAD` shows the task commits; no stray files.

## Migration & rollout (operational — run after merge)

1. **Apply migration `0008`** to Supabase (via the Supabase MCP `apply_migration`, name `0008_activity_metrics`, body = the SQL from Task 1), then confirm with `list_tables` that `activity_metrics` exists and `activities.avg_watts` is present.
2. **Deploy** backend (Render) + frontend (Vercel) — push to `main` triggers both.
3. **Run the one-off `avg_watts` re-list backfill** for the existing athlete so "Top avg power" lights up immediately. Trigger `sync_service.run_avg_watts_backfill(supabase, settings, athlete_id)` once (the same operational path prior phase one-offs used). ~5 Strava calls for ~877 rides; no streams.
4. **Run the one-off `run_streams_backfill`** for the existing ~877-ride dataset. Paced (~12/min, ~1h+); the zone panels fill in progressively (partial data renders correctly — it just undercounts until complete). Resumable: re-running picks up only un-metriced activities.
5. **Browser smoke test:** open `/home`, switch Week/Month/Year, confirm the zone panels re-scope and the Top-avg-power stat shows; with FTP/Max-HR unset, confirm the Settings prompts; set FTP/Max-HR in `/settings` and confirm the panels re-bucket without a re-backfill.

## Out of scope (Phase 3)

- Trends view; bikes & gear / component-wear panel (cut for v1).
- Storing full stream blobs for un-viewed rides.
- A manual "rebuild metrics" UI control (the backfill is run operationally).

---

## Self-review (completed)

**Spec coverage:** ✅ Top-avg-power (Tasks 9, 14, 16); power zones (Tasks 2–4, 6, 7, 10, 15, 17); HR zones (same); `activity_metrics` table + `avg_watts` column (Task 1); histograms + zone math (Tasks 2–3); metrics db layer + id-diff (Task 4); `avg_watts` mapping (Task 5); ensure_streams self-heal (Task 6); resumable paced streams backfill (Task 7); avg_watts re-list (Task 8); `_period_zones` unset/no-data/data states (Task 10); router chaining (Task 11); detail-page perf bonus (Task 12, deferrable); frontend DTO/mapper/component/page (Tasks 13–17); rollout (closing section).

**Deviation flagged:** frontend reuses existing `--zone-*` tokens + shared DTO/`toZoneRows` instead of the spec's duplicated types + new JS-literal palettes (documented above). Backend follows the spec verbatim.

**Type consistency:** `MetricsRow` keys (`avg_power_w/np_w/work_kj/power_hist/hr_hist/has_power/has_hr`) match `compute_metrics` output and the `0008` columns; `_period_zones` reads `power_hist`/`hr_hist` matching those keys; `ZonesBlock`/`ZoneBucket` reused unchanged; frontend `ZonesBlockDTO` shape matches the backend `ZonesBlock` serialization; `SummaryView.topAvgPower` produced in Task 14, consumed in Task 16; `DashboardOverview.powerZones`/`hrZones` produced in Task 14, consumed in Task 17.
