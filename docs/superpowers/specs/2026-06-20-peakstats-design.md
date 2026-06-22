# Peakstats — Design Spec

**Date:** 2026-06-20
**Status:** Approved (design); pending implementation plan
**Source design:** Claude Design project "Ride Analytics Platform" → `Peakstats Dashboard.dc.html`

## Overview

Peakstats is a Strava-connected ride analytics web app. An athlete signs in with
Strava, their activities are synced into the app, and the app presents a richer
analytics surface than Strava's own: overview KPIs with period-over-period deltas,
distance trends, a filterable activity table, ride detail (route/splits/elevation),
and segment PR comparison.

This spec covers the complete v1 feature set defined by the design prototype. It is
one overarching spec; implementation is broken into 7 phases, each of which gets its
own implementation plan.

## Goals

- Real, deployed product: live Strava OAuth, real activity sync, persistent storage.
- Port the design prototype's screens and interaction model faithfully.
- Keep token handling and the Strava client secret entirely server-side.

## Non-goals (v1)

- Multiple auth providers (Strava is the only identity).
- Social features, following other athletes, leaderboards.
- Non-ride activity types beyond what Strava returns (we display ride/gravel; other
  types are stored but the UI is ride-centric, matching the design).
- Manual activity entry/editing.

## Tech stack

- **Frontend:** Vite + React SPA, deployed to Vercel. TanStack Query for data
  fetching/caching. Theme + units via React context. SVG charts ported from the
  prototype (no chart library).
- **Backend:** Python + FastAPI, deployed to Render. Handles OAuth, token refresh,
  sync workers, webhooks, and aggregation endpoints.
- **Data/Auth:** Supabase Postgres for storage; Strava OAuth as the sole identity,
  with the session/user record keyed to the Strava athlete id. Supabase RLS scopes
  every read to the owning athlete.

## Architecture

```
Browser (Vite React SPA, Vercel)
   │  auth: redirect to Strava OAuth; session via Supabase
   │  data: HTTPS JSON  ───────────────►  FastAPI (Render)
                                              ├─ OAuth code→token exchange (client secret)
                                              ├─ token refresh (hourly expiry)
                                              ├─ backfill + webhook ingest workers
                                              └─ stats/aggregation endpoints
                                              ▼
                                          Supabase Postgres
   Strava  ──webhook POST──►  FastAPI /webhooks/strava
```

- The SPA never sees the Strava client secret; all token handling is server-side.
- Data is stored **metric** (Strava-native). Unit conversion (km/mi, m/ft, km/h/mph)
  happens client-side at render, exactly as the prototype's `renderVals()` does.

## Data model (Supabase Postgres)

- **athletes** — `id` (Strava athlete id, PK), name, avatar_url, created_at,
  settings JSONB `{units, theme, default_period}`.
- **strava_tokens** — athlete_id FK, access_token, refresh_token, expires_at.
  Server-only; RLS denies all client access.
- **activities** — id (Strava id, PK), athlete_id FK, name, type, start_date,
  distance_m, moving_time_s, elapsed_time_s, elev_gain_m, avg_speed_ms, avg_hr,
  calories, summary_polyline, splits_metric JSONB, detail_fetched_at (nullable),
  is_pr boolean.
- **segments** — id (Strava segment id, PK), name, distance_m, avg_grade.
- **segment_efforts** — id (Strava effort id, PK), segment_id FK, athlete_id FK,
  activity_id FK, elapsed_time_s, avg_watts (nullable), avg_hr (nullable),
  avg_speed_ms, start_date, is_best (derived per athlete+segment).
- **sync_state** — athlete_id PK, status (idle|backfilling|error), progress (0-100),
  last_backfill_at, last_sync_at, last_webhook_event_id.

Indexes: activities(athlete_id, start_date), segment_efforts(athlete_id, segment_id),
segment_efforts(activity_id).

## Strava integration & sync pipeline

**OAuth login.** SPA redirects to Strava authorize with scopes
`read,activity:read_all`. Strava redirects to `GET /auth/strava/callback`; FastAPI
exchanges the code for tokens, upserts the athlete + tokens, creates a Supabase
session, and redirects to the app (sync screen on first connect, else dashboard).

**Token refresh.** Access tokens expire hourly. The backend refreshes on demand
before any Strava call when `expires_at` is near, storing the new tokens.

**Backfill** (the "Syncing with Strava" screen). On first connect, paginate
`/athlete/activities`, storing summaries. Detailed payloads (splits, segment efforts,
streams) are filled two ways, both respecting rate limits (200 req / 15 min, 2000 /
day): the webhook ingest extracts efforts from the detail it already fetches for each
new ride, and a resumable, rate-limited background **detail-backfill worker** walks
historical activities (`detail_fetched_at IS NULL`) after the summary backfill —
storing efforts + splits and marking `detail_fetched_at` so nothing is re-fetched.
(This supersedes the original "lazy on ride-detail open" plan.) `sync_state.progress`
is updated as pages load; the SPA polls `GET /sync/status` to track progress for the
backfill screen.

**Real-time activity updates.** After the initial backfill, new activities arrive via
Strava webhooks (`POST /webhooks/strava`). Once the backend ingests a new or updated
activity, it pushes a notification to the connected frontend over a WebSocket
(`WS /ws/updates`). The SPA listens on this socket and invalidates the relevant
TanStack Query caches (overview, activities list) so the dashboard refreshes
automatically without a manual reload. The WebSocket carries lightweight event frames
(`{type: "activity_synced", activity_id}`) — the client re-fetches full data via the
normal REST endpoints.

**Webhooks.** Subscribe to Strava push subscriptions. `POST /webhooks/strava`
receives create/update/delete events; on create/update the backend fetches that one
activity and upserts it (powers "auto-syncs after every ride"). `GET /webhooks/strava`
answers the subscription verification challenge. Webhook payloads are verified via the
configured verify token.

**Manual refresh.** The "Refresh from Strava" button calls `POST /sync/refresh`,
which pulls activities since `sync_state.last_sync_at`.

**Segments are derived**, not fetched from the segment API. Detailed activity payloads
include a `segment_efforts` array; the backend upserts segments and efforts from those,
then computes `is_best`/PR per athlete+segment. Population is via the webhook extract
(new rides) + the background detail-backfill worker (history) described above — **not**
lazy on ride-detail open. `GET /segments/{id}` returns the athlete's full effort list;
attempt search/sort/pagination happens client-side.
_(Implemented 2026-06-21 — see `2026-06-21-segments-design.md`.)_

## API surface (FastAPI)

| Endpoint | Purpose |
|---|---|
| `GET /auth/strava/login` → redirect | Start OAuth |
| `GET /auth/strava/callback` | Code exchange, create session |
| `POST /auth/logout` | End session |
| `GET /athlete` | Current athlete profile |
| `GET /athlete/settings` · `PATCH /athlete/settings` | Units / theme / default period |
| `DELETE /athlete/connection` | Disconnect Strava |
| `GET /athlete/stats/overview?period=` | KPIs (+deltas), trend series, recent rides _(top-segments panel + the heatmap/donut/highlights Overview redesign = separate spec, not yet scheduled)_ |
| `GET /athlete/stats/trends?period=` | KPIs + full distance series |
| `GET /activities?q=&min_dist=&min_time=&min_elev=&sort=&page=` | Filtered/sorted/paginated table |
| `GET /activities/{id}` | Ride detail: route, KPIs, splits, elevation (lazy detail fetch) |
| `GET /segments?q=&sort=attempts&direction=` | Segment list (derived best/attempts/PR per segment) |
| `GET /segments/{id}` | Segment detail: meta + all efforts (attempt search/sort/paginate client-side) |
| `POST /sync/refresh` | Manual incremental sync |
| `GET /sync/status` | Backfill progress (polled during initial sync) |
| `WS /ws/updates` | Real-time activity notifications (WebSocket push, post-backfill) |
| `POST /webhooks/strava` · `GET /webhooks/strava` | Webhook ingest + subscription verify |

- KPI deltas and trend buckets are computed server-side via SQL aggregation (period
  vs. previous period). One athlete's dataset is small; compute-on-read, no precompute
  tables in v1.
- `period` ∈ {week, month, year}. Filters/units in requests are interpreted in metric
  on the server (the client converts user-entered imperial values to metric before
  sending, matching the prototype).

## Frontend structure (Vite + React SPA)

- Port the prototype's views to components; swap mock data for API calls via TanStack
  Query. The prototype's `renderVals()` logic (unit conversion, SVG path building,
  pager construction, formatters) ports into hooks/utils with unit tests.
- **Routes:** `/login`, `/sync` (backfill progress), `/` (Overview), `/activities`,
  `/trends`, `/segments`, `/segments/:id`, `/activities/:id`, `/settings`. Empty
  states per data view.
- Theme + units live in a context provider, persisted to `/athlete/settings`. SVG
  charts reused as-is.

## Feature → build mapping

| Feature | Source data | Notes |
|---|---|---|
| Strava login + session | OAuth | identity = athlete |
| Sync/backfill screen | backfill worker | real progress via `/sync/status` |
| Overview KPIs + deltas | SQL aggregation | period-over-period |
| Distance trend chart | activities grouped by day/week/month | |
| Recent rides / Activities table | activities | search, 3 numeric filters, sort, pagination |
| Trends view | aggregation | week/month/year toggle |
| Segments list | derived segment_efforts | search, sort by attempts |
| Segment detail compare | segment_efforts | PR vs selected, power/speed/HR, bars |
| Ride detail | lazy activity detail | route, splits, elevation |
| Settings | `/athlete/settings` | units, theme, default period, disconnect |
| Empty states | — | per-view |

## Delivery principle

Build **one feature at a time, end to end**. Each increment below is a vertical
slice — backend endpoint(s) + frontend screen + tests — that is implemented,
reviewed, and verified working before the next one starts. No "build all the
backend, then all the frontend" and no batching multiple features into a single
change. Each increment should be independently demoable and, where it makes sense,
independently mergeable. The implementation plan must reflect this: one task group
per increment, with a verification checkpoint at the end of each.

## Build phasing

Phases are ordered so each builds on the last. Within a phase, each numbered item is
its own increment, built and verified before moving on.

1. **Foundation**
   1. Scaffold Vite + React app; deploy skeleton to Vercel.
   2. Scaffold FastAPI app; deploy skeleton to Render; health check.
   3. Supabase schema + RLS migration; verify policies.
   4. Env/secrets wiring across all three platforms.
2. **Auth**
   1. Strava OAuth login + callback + token storage (backend).
   2. Session creation + `GET /athlete`; login/landing screen (frontend).
   3. Logout + `DELETE /athlete/connection`.
3. **Sync pipeline**
   1. Backfill worker + `sync_state` + `GET /sync/status` (backend).
   2. Sync/backfill screen wired to real progress via polling (frontend).
   3. Manual refresh (`POST /sync/refresh` + button).
   4. Webhook subscribe + ingest + `WS /ws/updates` push to connected clients.
4. **Overview**
   1. `GET /athlete/stats/overview` aggregation (backend).
   2. KPI cards + deltas (frontend).
   3. Distance trend chart.
   4. Recent rides + top segments panels.
5. **Activities & Trends**
   1. `GET /activities` with filter/sort/pagination (backend).
   2. Activities table + filter bar + pager (frontend).
   3. `GET /athlete/stats/trends` + Trends screen.
6. **Segments & Ride detail**
   1. Segment derivation from activity detail (backend).
   2. `GET /segments` + segments list (frontend).
   3. `GET /segments/{id}` + segment compare detail.
   4. `GET /activities/{id}` lazy detail + ride detail screen (route, splits, elevation).
7. **Settings & polish**
   1. `GET`/`PATCH /athlete/settings` + Settings screen.
   2. Theme + units context persistence.
   3. Empty states per view; responsive pass.

## Cross-cutting concerns

- **Secrets:** Strava client id/secret + Supabase service key only on Render. Frontend
  gets the Supabase anon key + API base URL.
- **Rate limits:** backfill paginates with backoff; detail fetches lazy; webhook
  ingest is single-activity.
- **Testing:** pytest for FastAPI (OAuth, sync, aggregation, with a Strava API stub);
  Vitest + React Testing Library for components; unit tests for the chart/format utils
  (the math matters).
- **Security:** Supabase RLS so an athlete reads only their own rows; tokens never
  leave the server; webhook signature/verify-token check.

## Beyond v1 — Planned enhancements

These features are not part of the v1 build phasing above. Each will get its own
implementation plan when scheduled. Grouped by theme.

### Analytics depth

- **Power curve** — plot best power output for every duration (5 s → 60 min),
  recalculated after each sync. Requires power data from the activity payload
  (`average_watts`, streams). Exposed as `GET /athlete/power-curve`.
- **Fitness & fatigue model** — rolling ATL (acute training load), CTL (chronic
  training load), and TSB (form) chart. Computed from daily TSS values server-side;
  displayed as an overlay on the trends screen. New endpoint:
  `GET /athlete/fitness?period=`.
- **Climb catalogue** — auto-detect and categorise climbs (HC / 1 / 2 / 3 / 4) from
  elevation streams attached to detailed activity payloads. Stored in a `climbs` table;
  browsable separately from Strava segments.
- **Year-over-year comparison** — overlay the current year's cumulative distance against
  prior years on the trends chart. Purely a frontend aggregation of existing
  `activities` data; no new endpoint needed.

### Goals & tracking

- **Annual goals** — athlete sets a target distance and/or elevation for the year; the
  overview shows a progress ring and projected finish date. Stored in
  `athletes.settings` JSONB; computed client-side from the existing activities data.
- **Personal records board** — all-time bests in one screen: longest ride, biggest
  climbing day, fastest segment PR, highest single-day TSS. Derived from existing
  tables via a new `GET /athlete/records` endpoint.
- **Streak tracking** — current and longest active streaks (consecutive days ridden,
  weekly minimums). Computed server-side from `activities.start_date`;
  surfaced on the overview.

### Activity experience

- **Ride heatmap** — aggregate all `summary_polyline` traces on a single Leaflet map.
  Rendered client-side from existing polyline data; no new endpoint. Accessible from a
  new `/heatmap` route.
- **Side-by-side ride comparison** — select two activities on the same route and compare
  splits, average power, HR, and speed side-by-side. New endpoint:
  `GET /activities/compare?a=<id>&b=<id>`.
- **Weather overlay** — surface historical weather (temperature, wind speed, precipitation)
  for each activity using a weather API (e.g. Open-Meteo, free tier). Fetched and
  stored at detail-fetch time; displayed on the ride detail screen. New column:
  `activities.weather JSONB`.

### Notifications

- **Weekly digest** — opt-in summary delivered each Monday covering the previous week's
  stats (distance, elevation, ride count, standout ride). Delivered via email using a
  transactional email provider (e.g. Resend). Backend cron job triggers
  `POST /notifications/digest`.

## Open questions / risks

- **Strava API approval:** webhook subscriptions and `activity:read_all` require a
  registered Strava API application with the correct callback domain. Must be set up
  before phases 2–3.
- **Rate limits at scale:** lazy detail fetch mitigates per-user cost; if many users
  backfill simultaneously the app-wide daily cap could bind. Acceptable for v1;
  revisit with a queue if needed.
- **Calories/power availability:** not all activities expose calories, power, or HR;
  the UI already handles missing values (em-dash), matching the prototype.
