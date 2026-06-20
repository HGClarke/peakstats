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
`/athlete/activities`, storing summaries. Detailed fetches (splits, segment efforts,
streams) are **lazy** — performed on ride-detail open — to respect rate limits
(200 req / 15 min, 2000 / day). `sync_state.progress` is updated as pages load; the
SPA polls `GET /sync/status`.

**Webhooks.** Subscribe to Strava push subscriptions. `POST /webhooks/strava`
receives create/update/delete events; on create/update the backend fetches that one
activity and upserts it (powers "auto-syncs after every ride"). `GET /webhooks/strava`
answers the subscription verification challenge. Webhook payloads are verified via the
configured verify token.

**Manual refresh.** The "Refresh from Strava" button calls `POST /sync/refresh`,
which pulls activities since `sync_state.last_sync_at`.

**Segments are derived**, not fetched from the segment API. Detailed activity payloads
include a `segment_efforts` array; the backend upserts segments and efforts from those,
then computes `is_best`/PR per athlete+segment.

## API surface (FastAPI)

| Endpoint | Purpose |
|---|---|
| `GET /auth/strava/login` → redirect | Start OAuth |
| `GET /auth/strava/callback` | Code exchange, create session |
| `POST /auth/logout` | End session |
| `GET /athlete` | Current athlete profile |
| `GET /athlete/settings` · `PATCH /athlete/settings` | Units / theme / default period |
| `DELETE /athlete/connection` | Disconnect Strava |
| `GET /athlete/stats/overview?period=` | KPIs (+deltas), trend series, recent rides, top segments |
| `GET /athlete/stats/trends?period=` | KPIs + full distance series |
| `GET /activities?q=&min_dist=&min_time=&min_elev=&sort=&page=` | Filtered/sorted/paginated table |
| `GET /activities/{id}` | Ride detail: route, KPIs, splits, elevation (lazy detail fetch) |
| `GET /segments?q=&sort=` | Segment list |
| `GET /segments/{id}` | Segment detail: PR + all attempts |
| `POST /sync/refresh` | Manual incremental sync |
| `GET /sync/status` | Backfill/sync progress |
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

## Build phasing

1. **Foundation** — scaffold Vite + FastAPI; Supabase schema + RLS; env/secrets;
   deploy skeletons to Vercel + Render.
2. **Auth** — Strava OAuth end-to-end; session; login/logout; landing.
3. **Sync pipeline** — backfill worker + sync screen; manual refresh; webhooks last.
4. **Read APIs + Overview** — stats aggregation; Overview wired to real data.
5. **Activities + Trends** — table (filter/sort/page); trends charts.
6. **Segments + Ride detail** — derived segments; compare; lazy ride detail.
7. **Settings + polish** — settings persistence; empty states; theming; responsive.

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

## Open questions / risks

- **Strava API approval:** webhook subscriptions and `activity:read_all` require a
  registered Strava API application with the correct callback domain. Must be set up
  before phases 2–3.
- **Rate limits at scale:** lazy detail fetch mitigates per-user cost; if many users
  backfill simultaneously the app-wide daily cap could bind. Acceptable for v1;
  revisit with a queue if needed.
- **Calories/power availability:** not all activities expose calories, power, or HR;
  the UI already handles missing values (em-dash), matching the prototype.
