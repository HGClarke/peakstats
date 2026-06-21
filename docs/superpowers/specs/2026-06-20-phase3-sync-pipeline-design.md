# Peakstats Phase 3 (3a) — Sync Pipeline Design

**Date:** 2026-06-20
**Status:** Approved (design); pending implementation plan
**Parent spec:** `docs/superpowers/specs/2026-06-20-peakstats-design.md` (Phase 3 — Sync pipeline)

## Overview

Phase 3 gets real Strava activity data into the app. An athlete who has connected
their Strava account (Phase 2) gets their activity history **backfilled** into
Supabase, watches progress on a dedicated sync screen, and can later pull new rides
on demand with a **manual refresh**.

This document covers **Phase 3a** only: increments 1–3 of the parent spec's Phase 3
(backfill + `GET /sync/status`, the sync screen via polling, and manual refresh).
**Out of scope (deferred to Phase 3b):** Strava webhook subscription/ingest and the
`WS /ws/updates` realtime push channel. Those are the most complex pieces and add
the least value for a single-user product right now; the app is fully useful with
backfill + manual refresh.

## Goals

- Backfill an athlete's full activity history into `activities` on first connect.
- Show real backfill progress on a `/sync` screen driven by polling.
- Let the athlete pull new activities on demand from `/home`.
- Refresh expiring Strava access tokens transparently before any API call.

## Non-goals (Phase 3a)

- Webhooks / push subscriptions and realtime WebSocket updates (Phase 3b).
- Lazy detailed-activity fetch (splits, segment efforts, streams) — that is Phase 6.
  Backfill stores **summary** fields only; `calories`, `splits_metric`, and
  `detail_fetched_at` stay null.
- Any segment derivation (Phase 6).

## Key decisions

1. **Scope:** increments 1–3 only; webhooks + realtime deferred to Phase 3b.
2. **Backfill engine:** an **in-process async background task** in the FastAPI web
   service (Render free tier has no separate worker dyno). All progress/state lives
   in Supabase `sync_state`, so a free-dyno spin-down mid-backfill is recoverable.
   The task runs in a thread (our Strava/Supabase I/O is synchronous `httpx`).
3. **Trigger:** **SPA-driven**. The OAuth callback is unchanged (still redirects to
   `/home`). `/home` checks `GET /sync/status`; if never synced it routes to `/sync`,
   which calls `POST /sync/start` (idempotent) and polls. Auth and sync stay
   decoupled.
4. **Frontend data layer:** adopt **TanStack Query** now. Add a `QueryClientProvider`,
   migrate the existing hand-rolled `useAthlete` hook to `useQuery`, and build the new
   sync hooks on TanStack Query. This replaces the `useState`/`useEffect` pattern used
   in Phase 2.

## Architecture & data flow

```
First connect:
  OAuth callback ──► /home (unchanged)
  /home ──GET /sync/status──► "never_synced" ──► redirect to /sync
  /sync (mount) ──POST /sync/start──► sets status='backfilling', spawns bg task, returns
        └─poll GET /sync/status (while 'backfilling')──► {status, progress, synced}
        └─on 'idle'/done ──► redirect to /home

Background task (in web process, builds its OWN short-lived clients):
  get valid access token (refresh if expiring)
  for page in /athlete/activities (per_page=200):
      upsert page into activities
      bump sync_state.progress
  on done:  status='idle', progress=100, last_backfill_at=now, last_sync_at=now
  on error: status='error'

Manual refresh (from /home, post-backfill):
  "Refresh from Strava" ──POST /sync/refresh──► inline incremental
      list activities after last_sync_at, upsert, set last_sync_at=now ──► {synced: N}
```

The background task **must build its own Supabase/Strava clients** — it cannot reuse
the request-scoped clients from `deps`, which close as soon as the `POST /sync/start`
response is sent.

## Backend design (layered: routers → services → db)

Follows `backend/CLAUDE.md`: thin routers, fastapi-free services, typed db wrappers,
new env vars (none needed this phase) in `config.py` first. Sync I/O in plain `def`.

### Infrastructure

- **`app/strava.py`** (modify) — add:
  - `StravaClient.list_activities(access_token, *, page, per_page=200, after=None) -> list[dict]`
    — authenticated `GET https://www.strava.com/api/v3/athlete/activities` with a
    per-call `Authorization: Bearer <token>` header; `after` is epoch seconds for
    incremental pulls; raises for non-2xx.
  - `StravaClient.close()` — closes the underlying http client (so background tasks
    can clean up).
- **`app/clients.py`** (new, **no fastapi imports**) — `build_supabase(settings) -> httpx.Client`
  and `build_strava(settings) -> StravaClient` factories. `deps.get_supabase` /
  `deps.get_strava` are refactored to delegate to these; the background task uses the
  factories directly (keeping services free of fastapi/deps).

### Services

- **`app/services/tokens.py`** (new) —
  `get_valid_access_token(supabase, strava, athlete_id, *, now=None) -> str`: reads the
  stored tokens, and if `expires_at` is within a 60-second buffer of `now`, calls
  `strava.refresh`, persists the new tokens via `db.tokens.upsert_tokens`, and returns
  a usable access token. Never logs token values.
- **`app/services/sync.py`** (new) —
  - `_to_activity_row(athlete_id, summary) -> dict` — pure mapper, Strava summary →
    `activities` columns (see mapping below).
  - `start_backfill(supabase, athlete_id) -> SyncStatusResponse` — **idempotent**: if
    current status is `backfilling`, returns the current state unchanged; otherwise
    sets `status='backfilling'`, `progress=0` and returns. (Spawning the task is the
    router's job.)
  - `run_backfill(settings, athlete_id) -> None` — background entry point. Builds its
    own clients, gets a valid token, paginates `list_activities` until a short page,
    upserts each page, bumps `progress` per page (coarse; capped < 100), and on
    completion sets `status='idle'`, `progress=100`, `last_backfill_at=now`,
    `last_sync_at=now`. On any exception sets `status='error'` (logged, no secrets).
    Closes its clients in `finally`.
  - `get_status(supabase, athlete_id) -> SyncStatusResponse` — reads `sync_state`;
    returns `status='never_synced'`, `progress=0` when there is no row. Includes the
    live `synced` count from `db.activities.count_activities`.
  - `refresh(settings, athlete_id) -> int` — inline incremental sync: valid token →
    `list_activities(after=last_sync_at epoch)` → upsert → set `last_sync_at=now`;
    returns the number of activities written.

### Data access

- **`app/db/activities.py`** (new) — `upsert_activities(client, rows: list[dict]) -> None`
  (bulk POST, `on_conflict=id`, `Prefer: resolution=merge-duplicates`);
  `count_activities(client, athlete_id) -> int` (PostgREST `count` via
  `Prefer: count=exact`, `Range: 0-0`, reads `Content-Range`).
- **`app/db/sync_state.py`** (new) — `get_sync_state(client, athlete_id) -> dict | None`;
  `upsert_sync_state(client, athlete_id, fields: dict) -> None`
  (`on_conflict=athlete_id`, merge-duplicates).

### Models

- **`app/models/sync.py`** (new) — `SyncStatusResponse{ status: str, progress: int,
  synced: int, last_backfill_at: datetime | None, last_sync_at: datetime | None }`;
  `RefreshResponse{ synced: int }`.

### Router

- **`app/routers/sync.py`** (new, registered with `prefix="/sync"`), all behind
  `get_current_athlete_id`:
  - `GET /status` → `get_status(...)` → `SyncStatusResponse`.
  - `POST /start` → `start_backfill(...)`; if the call transitioned into `backfilling`,
    schedule `run_backfill(settings, athlete_id)` via FastAPI `BackgroundTasks`.
    Returns the current `SyncStatusResponse`.
  - `POST /refresh` → `refresh(...)` → `RefreshResponse`; Strava/network failure →
    `HTTPException(502)`.
- **`app/main.py`** (modify) — register the sync router.

### Activity field mapping (Strava summary → `activities`)

| Column | Source |
|---|---|
| `id` | `summary.id` |
| `athlete_id` | session athlete id |
| `name` | `summary.name` |
| `type` | `summary.sport_type` (fallback `summary.type`) |
| `start_date` | `summary.start_date` |
| `distance_m` | `summary.distance` |
| `moving_time_s` | `summary.moving_time` |
| `elapsed_time_s` | `summary.elapsed_time` |
| `elev_gain_m` | `summary.total_elevation_gain` |
| `avg_speed_ms` | `summary.average_speed` (nullable) |
| `avg_hr` | round(`summary.average_heartrate`) if present, else null |
| `summary_polyline` | `summary.map.summary_polyline` (nullable) |
| `calories`, `splits_metric`, `detail_fetched_at` | null (lazy detail = Phase 6) |
| `is_pr` | false (default) |

**Progress semantics:** Strava exposes no total activity count, so `progress` is a
coarse loading indicator (steps up per page fetched, capped below 100 until the run
completes, then 100). The honest user-facing signal is the **`synced` count** (live
count of activities stored), shown on the sync screen.

## Frontend design

React 19 + Vite + TS + Tailwind + **TanStack Query** (new), following
`frontend/CLAUDE.md` (pages compose, `api/` hooks own data, `@/` imports, token
utilities for styling, co-located tests, react-router `<Link>`/`navigate`).

### TanStack Query adoption (replaces Phase 2's hand-rolled hooks)

- Add `@tanstack/react-query` dependency.
- **`app/providers/QueryProvider.tsx`** (new) — exports the `QueryClientProvider`
  wrapper component; a shared `QueryClient` is created here. `App.tsx` wraps the app
  in it (alongside `ThemeProvider`).
- **`api/auth.ts`** (modify) — `useAthlete` becomes a `useQuery` (key `['athlete']`,
  `queryFn: fetchAthlete`); exposes the same `{ data, isLoading, error }` shape so
  `AppHome` changes minimally. A 401 surfaces as the query `error` (no retry on 401).

### Sync feature

- **`types/sync.ts`** (new) — `SyncStatus` union
  (`'never_synced' | 'backfilling' | 'idle' | 'error'`) and the status payload type.
- **`api/sync.ts`** (new) —
  - `fetchSyncStatus()`, `startSync()`, `refreshSync()` (typed `apiFetch` calls).
  - `useSyncStatus()` — `useQuery` (key `['sync','status']`) with a `refetchInterval`
    that polls (~1.5s) **only while** `status === 'backfilling'`, and stops otherwise.
  - `useStartSync()` / `useRefreshSync()` — `useMutation` that invalidate
    `['sync','status']` (and `useRefreshSync` also invalidates activity-related keys
    when those exist in later phases).
- **`pages/sync/SyncPage.tsx`** (+ test, new) — on mount triggers `startSync`, then
  reads `useSyncStatus`; renders a progress bar + "N rides synced"; navigates to
  `/home` when status is `idle`/done; shows an error state with a retry that re-runs
  `startSync`. Styled with design tokens.
- **`pages/app-home/AppHome.tsx`** (modify) — read `useSyncStatus`; redirect to
  `/sync` when status is `never_synced`. Add a "Refresh from Strava" button
  (`useRefreshSync`) that pulls new activities and invalidates the status query.
- **`app/router.tsx`** (modify) — add the `/sync` route.

## Error handling

- **Backfill failures** (token refresh failure, Strava 401/429, network) are caught;
  `sync_state.status='error'` and the error is logged without token values. The status
  endpoint surfaces `error`; the sync screen shows a retry that re-calls `POST
  /sync/start`.
- **Manual refresh** failures → router raises `HTTPException(502)`; `/home` shows a
  transient error.
- **Unauthenticated** requests → `get_current_athlete_id` returns 401 (existing).

## Testing

- **Backend (pytest, Strava + Supabase stubbed via `httpx.MockTransport`):**
  - `strava.list_activities` — Bearer header, `page`/`per_page`/`after` params, parse.
  - `services.tokens.get_valid_access_token` — expired → refresh + persist; valid →
    no refresh.
  - `db.activities` (upsert merge headers, count parsing) and `db.sync_state` wrappers.
  - `services.sync` — `_to_activity_row` mapping (incl. missing HR/polyline);
    `start_backfill` idempotency; `run_backfill` happy path (FakeStrava + monkeypatched
    db); `get_status` never-synced; `refresh` count.
  - `routers.sync` — `GET /status`, `POST /start` (status transition + background task
    scheduled), `POST /refresh`; 401 without session.
- **Frontend (Vitest + RTL, components wrapped in a shared `QueryClientProvider`
  test helper):**
  - `api/sync` — credentials + methods for status/start/refresh.
  - `useSyncStatus` — polls while `backfilling`, stops otherwise.
  - `SyncPage` — progress render, navigate-on-done, retry on error.
  - `AppHome` — redirect to `/sync` when `never_synced`; "Refresh from Strava" button.
  - `useAthlete` migration — existing auth/AppHome tests stay green under TanStack Query.

## Increments (vertical slices, each implemented, verified, and committed)

1. **Backend backfill** — `strava.list_activities` + `StravaClient.close` +
   `services.tokens` + `clients.py` (with `deps` refactor) + `db.activities` +
   `db.sync_state` + `services.sync` (mapping/start/run/status) + `routers.sync`
   (`GET /status`, `POST /start`) + register in `main.py`. Verify: pytest green.
2. **Introduce TanStack Query (frontend foundation)** — add dependency, `QueryProvider`
   wired in `App.tsx`, migrate `useAthlete` to `useQuery`, update auth/AppHome tests
   with a `QueryClientProvider` wrapper. Behavior identical. Verify: `npm test`,
   `npm run lint`, `npm run build`.
3. **Frontend sync screen** — `types/sync`, `api/sync` (`useSyncStatus` +
   `useStartSync`), `pages/sync/SyncPage`, `/sync` route, `/home` redirect when
   `never_synced`. Verify: tests + lint + build.
4. **Manual refresh** — `services.sync.refresh` + `POST /sync/refresh` (backend) +
   `useRefreshSync` + "Refresh from Strava" button on `/home`. Verify end to end:
   tests + lint + build.

## Cross-cutting

- **Secrets:** no new env vars. Strava/Supabase credentials remain server-only.
- **Rate limits:** backfill paginates at `per_page=200` (few pages for one athlete);
  detail fetch stays lazy (Phase 6); refresh is incremental (`after=last_sync_at`).
- **Deployment:** runs on the existing single Render web service; no `render.yaml`
  change. Real backfill is verified against the deployed stack with a live Strava
  account after the automated tests pass.

## Open questions / risks

- **Free-dyno spin-down mid-backfill:** acceptable — state is in Supabase; re-entering
  `/sync` or hitting refresh continues. Revisit only if it proves flaky in practice.
- **`progress` is approximate** (no Strava total count); the `synced` count is the
  precise signal. Acceptable for v1.
