# Local-time ride day — design

**Date:** 2026-06-21
**Status:** Approved (pending spec review)

## Problem

The Overview dashboard buckets a ride into a weekday using its UTC `start_date`.
A ride that happens late in the local evening can cross into the next UTC day and
land on the wrong weekday. Example: an 11pm Saturday ride in California is 7am
Sunday UTC, so the weekly chart plots it on Sunday and the recent-rides list
labels it "Sun".

This affects three surfaces, all from the same root cause (UTC day arithmetic):

1. The weekly km chart (`week` buckets, MON–SUN).
2. The this-week / last-week totals + KPIs (which rides fall in which week).
3. The recent-rides date label `"Tue · Jun 16"` (frontend `fmtDate`, which reads
   `getUTCDay/Month/Date`).

## Decisions

- **A ride's weekday comes from Strava's per-ride `start_date_local`** — the local
  wall-clock time where the ride happened. This matches what Strava itself shows and
  stays correct when the athlete travels across time zones.
- **The "current week" boundary (this Monday vs last Monday) comes from the viewer's
  browser time zone.** The frontend sends its IANA zone; the backend uses it only to
  compute "today / this Monday". Ride bucketing still uses each ride's own
  `start_date_local`.
- **Scope includes the recent-rides label** — same root cause, fixed in the same change
  for a consistent UI.

## Non-goals

- No per-athlete stored time-zone setting. The browser zone is the source for "now"; the
  ride's own Strava local time is the source for each ride's day.
- No change to how `/activities` (the table) sorts or displays — it shows the raw
  `start_date` and is out of scope.

## Approach

Store Strava's `start_date_local` on each activity and bucket off it. This is the only
option that preserves "the day Strava says the ride happened"; deriving local time from a
stored `utc_offset`, or converting `start_date` client-side by the browser zone, both
re-introduce the travel failure mode or duplicate a value Strava already provides.

### Key invariant

`start_date_local` is a **wall-clock label, not an instant — never time-zone-convert it.**
Strava returns it as an ISO string with a trailing `Z` (e.g. `2026-06-20T18:30:00Z`) even
though the value is local wall-clock. Stored in a `text` column, the string is kept exactly
as Strava sent it (trailing `Z` and all), so its correctness does not depend on any Postgres
session timezone. The wall-clock numerals are read directly on both sides:

- Backend: `datetime.fromisoformat(start_date_local).weekday()` — **without** `.astimezone()` —
  yields the local weekday (`.weekday()` reads the stored y/m/d directly).
- Frontend: the existing `fmtDate` reads `getUTCDay/Month/Date` off `new Date(value)`, which
  reproduces those same wall-clock numerals.

Any code that calls `.astimezone()` / local-time conversion on this field is a bug.

## Components

### 1. Database — migration `0003_activities_start_date_local.sql`

```sql
alter table activities add column start_date_local text;
```

`text` (not `timestamptz`) so the value is stored byte-for-byte as Strava sent it — a
wall-clock label whose correctness is independent of any DB session timezone. Nullable:
existing rows have no value, and code falls back to `start_date` (UTC) for those until a
re-backfill fills them.

### 2. Ingest — `backend/app/services/sync.py`

`_to_activity_row` (shared by backfill and the webhook path via
`webhooks.process_event`) adds:

```python
"start_date_local": summary.get("start_date_local"),
```

### 3. DB layer — `backend/app/db/activities.py`

- `ActivityRow` TypedDict gains `start_date_local: str | None`.
- Existing queries already `select=*`, so the column is returned without query changes.
- The upsert sends the new key as part of the row dict.

### 4. Service — `backend/app/services/activities.py`

`get_overview(supabase, athlete_id, tz, now=None)`:

- New `tz: str` parameter (IANA zone name). Resolve via `zoneinfo.ZoneInfo(tz)`;
  on `ZoneInfoNotFoundError`/invalid input, fall back to UTC.
- Compute `now` in `tz`, then `this_monday` / `last_monday` as wall-clock dates in `tz`.
- Add a `_local_dt(row)` helper: parse `start_date_local`; if null, fall back to
  `start_date`. Returns a naive wall-clock datetime used for both weekday bucketing and
  this-week / last-week membership.
- **Widen the DB pre-filter.** Rows are still fetched by UTC `start_date`
  (`list_activities_since`), which can sit up to ~14h off the local date, so query from
  `last_monday − 1 day` and then filter precisely in Python by `_local_dt`.
- `km_by_day` and the `this_week`/`last_week` partitions all key off `_local_dt`, so the
  chart and the totals/KPIs move together.

### 5. Router — `backend/app/routers/activities.py`

`overview` reads `tz: str = Query("UTC")` and passes it to the service. (Service still
validates and falls back, so a bad value never 500s.)

### 6. Models — `backend/app/models/activities.py`

`RecentRideItem` gains `start_date_local: str | None`. `get_overview` populates it from the
recent rows. `OverviewResponse` is otherwise unchanged.

### 7. Frontend — `frontend/src/api/overview.ts` + `types/overview.ts`

- `RecentRideDTO` gains `start_date_local: string | null`.
- `fetchOverview` appends `?tz=${encodeURIComponent(Intl.DateTimeFormat().resolvedOptions().timeZone)}`.
- `toRide` formats from `r.start_date_local ?? r.start_date` (fallback for legacy rows).
- `fmtDate` is unchanged — it already reads the wall-clock numerals via `getUTC*`.
- `WeekChart` is unchanged.

### 8. Rollout

After deploy, trigger one re-backfill per athlete to populate `start_date_local` for
existing rides (the upsert merges the new column onto existing rows). Until that runs,
legacy rows fall back to UTC `start_date`, so nothing breaks — days just stay as they are
today for un-backfilled rows.

## Data flow

```
Strava summary.start_date_local
  → sync/webhook _to_activity_row
    → activities.start_date_local (text, stored verbatim)
      → get_overview:
          tz (browser) ──► this_monday / last_monday (wall-clock in tz)
          _local_dt(row) ─► ride weekday + week membership
        → week[], this_week/last_week totals, recent_rides[].start_date_local
          → frontend: chart buckets, KPIs, fmtDate label (all local)
```

## Error handling / edge cases

- **Invalid or missing `tz`** → backend falls back to `UTC`; no error surfaced.
- **Null `start_date_local`** (legacy rows pre-backfill) → fall back to UTC `start_date`
  on both backend bucketing and the frontend label.
- **Ride near local midnight** → buckets on the local day, the whole point of the change.
- **Athlete travelled across zones** → each ride uses its own recorded local time; the
  week window uses the viewer's current browser zone. These can disagree only for a ride
  within a few hours of a week boundary while the viewer is in a different zone than where
  they rode — an accepted edge case.

## Testing

**Backend** (`tests/services/test_activities.py`, `tests/routers/test_activities.py`):
- A ride whose UTC `start_date` and `start_date_local` fall on different weekdays buckets
  to the local weekday.
- `tz` changes which week a boundary ride lands in (week-window correctness).
- Null `start_date_local` falls back to `start_date`.
- The `overview` route forwards `tz` to the service; an invalid `tz` still returns 200.

**Frontend** (`api/overview.test.ts`, `lib/format.test.ts`):
- `fetchOverview` sends the browser `tz` query param.
- `toRide` builds its label from `start_date_local`, falling back to `start_date` when null.

## Definition of done

- Backend `pytest`, `ruff check .`, `mypy` clean.
- Frontend `npm test && npm run lint && npm run build` clean.
- Migration `0003` applied to Supabase; one re-backfill run to populate existing rows.
