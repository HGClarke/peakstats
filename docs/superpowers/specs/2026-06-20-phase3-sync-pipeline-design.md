# Peakstats Phase 3a — Sync Pipeline + App Foundation Design

**Date:** 2026-06-20
**Status:** Approved (design); pending implementation plan
**Parent spec:** `docs/superpowers/specs/2026-06-20-peakstats-design.md` (Phase 3 — Sync pipeline)
**Design source:** Claude Design project "Ride Analytics Platform"
(`646622a9-126e-4e80-b91c-8b2ccf507529`) → `Peakstats Sync.dc.html`,
`Peakstats Dashboard.dc.html`. Both are vendored into `docs/design/` as the porting
source of record.

## Overview

Phase 3 gets real Strava activity data into the app. An athlete who connected their
Strava account (Phase 2) gets their activity history **backfilled** into Supabase,
watches progress on a dedicated **sync screen**, and can later pull new rides on demand
with a **manual refresh**.

Because the supplied designs (`Peakstats Sync` / `Peakstats Dashboard`) introduce a new,
unified design system and a full authenticated **app shell** (sidebar + topbar), this
phase also lays the **frontend foundation** the rest of v1 builds on: the new design
system (migrating the existing landing page onto it), TanStack Query, and the shared
app-shell layout.

This is **Phase 3a**. **Out of scope (deferred):** Strava webhook subscription/ingest
and the `WS /ws/updates` realtime channel (Phase 3b); and the full Dashboard surfaces —
Overview KPIs/chart, Activities, Trends, Segments, ride/segment detail — which are the
parent spec's **Phases 4–6** and get built tab-by-tab against real endpoints. After sync
completes the user lands on a **minimal Overview shell** that those phases fill in.

## Goals

- Backfill an athlete's full activity history into `activities` on first connect.
- Show real backfill progress on a faithfully-ported `/sync` screen, driven by polling.
- Let the athlete pull new activities on demand from `/home`.
- Refresh expiring Strava access tokens transparently before any API call.
- Establish the unified design system + app shell + TanStack Query for the whole app.

## Non-goals (Phase 3a)

- Webhooks / push subscriptions and realtime WebSocket updates (Phase 3b).
- Lazy detailed-activity fetch (splits, segment efforts, streams) — Phase 6. Backfill
  stores **summary** fields only; `calories`, `splits_metric`, `detail_fetched_at` null.
- Real Dashboard data surfaces (Overview KPIs/chart/recent/PRs, Activities, Trends,
  Segments, detail views) — Phases 4–6. Phase 3a ships only a minimal Overview shell.
- The design's "Go to dashboard" button and "Continue in background" affordance, and the
  "banner" sync layout — see Sync screen below.

## Key decisions

1. **Scope:** backfill + sync screen + manual refresh; plus the frontend foundation
   (design system, app shell, TanStack Query) and a minimal `/home` Overview shell.
   Webhooks/realtime → Phase 3b; full Dashboard → Phases 4–6.
2. **Backfill engine:** an **in-process async background task** in the FastAPI web
   service (Render free tier has no separate worker dyno). All progress/state lives in
   Supabase `sync_state`, so a free-dyno spin-down mid-backfill is recoverable. The task
   runs in a thread (Strava/Supabase I/O is synchronous `httpx`).
3. **Trigger:** **SPA-driven**. The OAuth callback is unchanged (redirects to `/home`).
   `/home` checks `GET /sync/status`; if never synced it routes to `/sync`, which calls
   `POST /sync/start` (idempotent) and polls. Auth and sync stay decoupled.
4. **Frontend data layer:** adopt **TanStack Query**. Add a `QueryClientProvider`,
   migrate the existing `useAthlete` hook to `useQuery`, and build sync hooks on it.
5. **Design system:** **unify the whole product** on the design files' system (fonts
   Space Grotesk / Archivo / JetBrains Mono, `#fc4c02` accent, light/dark token set),
   **including re-porting the existing landing page**. Implemented by remapping/extending
   the Tailwind v4 token layer in `index.css` and keeping the existing `.dark`-class
   `ThemeProvider` mechanism (the prototype's `[data-theme]` maps to our class).
6. **App shell:** extract the design's sidebar + topbar into a shared `AppShell` layout
   used by both `/sync` and `/home` (and Phases 4–6).
7. **Sync screen:** port the **overlay** layout (full-screen "Importing your rides" card
   over a blurred skeleton dashboard) — not the "banner" layout, since there is no real
   dashboard to sit behind it yet. **Drop the "Go to dashboard" button and "Continue in
   background" affordance**; on completion the screen **auto-navigates to `/home`**. Keep
   the progress, staged checklist, `ready`, and `empty` (no rides → "Refresh from
   Strava" / "Skip") states.

## Architecture & data flow

```
First connect:
  OAuth callback ──► /home (unchanged)
  /home ──GET /sync/status──► "never_synced" ──► redirect to /sync
  /sync (mount) ──POST /sync/start──► sets status='backfilling', spawns bg task, returns
        └─poll GET /sync/status (while 'backfilling')──► {status, progress, synced}
        └─on 'idle'/done ──► auto-navigate to /home   (no manual button)

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

The background task **must build its own Supabase/Strava clients** — it cannot reuse the
request-scoped clients from `deps`, which close when the `POST /sync/start` response is
sent.

## Backend design (layered: routers → services → db)

Follows `backend/CLAUDE.md`: thin routers, fastapi-free services, typed `db` wrappers
(each returns a `TypedDict` row shape), new env vars in `config.py` first (none needed),
sync I/O in plain `def`, `ruff` + `mypy` clean. `test_architecture.py` enforces layering.

### Infrastructure

- **`app/strava.py`** (modify) — add
  `StravaClient.list_activities(access_token, *, page, per_page=200, after=None) -> list[dict]`
  (authenticated `GET https://www.strava.com/api/v3/athlete/activities`, per-call
  `Authorization: Bearer`, `after` = epoch seconds; raises for non-2xx) and
  `StravaClient.close()` (closes its http client, for background-task cleanup).
- **`app/clients.py`** (new, **no fastapi imports**) — `build_supabase(settings) -> httpx.Client`
  and `build_strava(settings) -> StravaClient` factories. `deps.get_supabase`/`get_strava`
  refactor to delegate to these; the background task uses the factories directly (keeping
  services free of fastapi/deps).

### Services

- **`app/services/tokens.py`** (new) —
  `get_valid_access_token(supabase, strava, athlete_id, *, now=None) -> str`: reads tokens,
  refreshes + persists via `db.tokens.upsert_tokens` if `expires_at` within a 60s buffer,
  returns a usable access token. Never logs token values.
- **`app/services/sync.py`** (new) —
  - `_to_activity_row(athlete_id, summary) -> dict` — pure Strava-summary → column mapper.
  - `start_backfill(supabase, athlete_id) -> SyncStatusResponse` — idempotent: if already
    `backfilling`, returns current state; else sets `backfilling`/progress 0.
  - `run_backfill(settings, athlete_id) -> None` — background entry point; builds its own
    clients, gets a valid token, paginates + upserts, bumps progress, finalizes
    (`idle`/100/timestamps); `error` on failure; closes clients in `finally`.
  - `get_status(supabase, athlete_id) -> SyncStatusResponse` — returns `never_synced` when
    no row; includes live `synced` count via `db.activities.count_activities`.
  - `refresh(settings, athlete_id) -> int` — inline incremental sync; returns count.

### Data access

- **`app/db/activities.py`** (new) — `upsert_activities(client, rows)` (bulk POST,
  `on_conflict=id`, `Prefer: resolution=merge-duplicates`); `count_activities(client,
  athlete_id) -> int` (PostgREST `Prefer: count=exact`, `Range: 0-0`, parse `Content-Range`).
- **`app/db/sync_state.py`** (new) — `get_sync_state(client, athlete_id) -> dict | None`;
  `upsert_sync_state(client, athlete_id, fields)` (`on_conflict=athlete_id`, merge).

### Models & router

- **`app/models/sync.py`** (new) — `SyncStatusResponse{ status, progress, synced,
  last_backfill_at, last_sync_at }`, `RefreshResponse{ synced }`.
- **`app/routers/sync.py`** (new, `prefix="/sync"`, all behind `get_current_athlete_id`):
  `GET /status` → status; `POST /start` → `start_backfill`, and if it transitioned into
  `backfilling`, schedule `run_backfill(settings, athlete_id)` via `BackgroundTasks`;
  `POST /refresh` → `refresh` (Strava/network failure → `HTTPException(502)`). Register in
  `main.py`.

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

**Progress semantics:** Strava exposes no total activity count, so `progress` is a coarse
loading indicator (steps up per page fetched, capped below 100 until completion, then
100). The honest user-facing signal is the **`synced` count**. The sync card shows the
percentage and "N of … activities"; "…" / total uses `synced` as the count and omits a
hard total (no fabricated denominator).

## Frontend design

React 19 + Vite + TS + Tailwind v4 + **TanStack Query** (new). Follows `frontend/CLAUDE.md`
(pages compose; `api/` hooks own data; `@/` imports; token utilities only — no raw hex;
co-located tests; react-router for navigation). Faithful port of the vendored design files.

### Unified design system (foundation — also re-ports the landing page)

- Vendor `Peakstats Sync.dc.html` + `Peakstats Dashboard.dc.html` under `docs/design/`.
- **`src/index.css`** — replace the token layer with the design's palette: light/dark
  CSS-variable sets (`--bg`, `--sidebar`, `--panel`/`--panel2`, `--border`/`--border2`/
  `--borderStrong`, `--text`/`--text2`/`--textHi`, `--muted`…`--muted5`, `--accent`
  `#fc4c02`/`--accentSoft`, `--good`/`--bad`, `--track`, `--grid`/`--chartgrid`,
  `--overlay`, `--skel`), exposed as Tailwind utilities via `@theme inline`. Add the three
  font families (Space Grotesk display, Archivo body, JetBrains Mono mono) via `@font-face`
  / Google Fonts and map them to `font-display`/`font-sans`/`font-mono` tokens. Keyframes
  (`pkpulse`, `pkspin`, `pkshimmer`, `pkskel`, `pkrise`) for sync/skeleton animations.
- **`ThemeProvider`** stays the single source of truth (toggles `.dark` on `<html>`); the
  prototype's `[data-theme="dark|light"]` maps onto our `.dark`/`:root` blocks. Update the
  `ThemeToggle` to the design's sun/moon button (used in the topbar).
- **Landing page** (`pages/landing/**`) — re-port onto the new tokens/fonts so the whole
  product shares one system. Keep existing landing tests green (update token-class
  assertions as needed; rendered structure stays equivalent).

### TanStack Query

- Add `@tanstack/react-query`. **`app/providers/QueryProvider.tsx`** (new) exports the
  `QueryClientProvider` wrapper (owns a shared `QueryClient`); `App.tsx` wraps the app in
  it alongside `ThemeProvider`. **`api/auth.ts`** — `useAthlete` becomes a `useQuery`
  (key `['athlete']`); same `{ data, isLoading, error }` shape; no retry on 401.

### App shell (shared authenticated layout)

- **`components/app-shell/`** — `AppShell` (sidebar + topbar + scroll body slot),
  `Sidebar` (logo, nav items Overview/Activities/Segments/Trends/Goals, user chip with
  avatar/initials + sync-status dot, logout button), `Topbar` (title/subtitle slot,
  optional period toggle slot, theme toggle). Nav items for not-yet-built sections render
  as disabled/placeholder in 3a. Used by `/sync` and `/home`.

### Sync feature

- **`types/sync.ts`** (new) — `SyncStatus` union
  (`'never_synced' | 'backfilling' | 'idle' | 'error'`) + payload type.
- **`api/sync.ts`** (new) — `fetchSyncStatus()`, `startSync()`, `refreshSync()`;
  `useSyncStatus()` (`useQuery` key `['sync','status']`, `refetchInterval` that polls
  (~1.5s) only while `backfilling`); `useStartSync()` / `useRefreshSync()` (`useMutation`
  invalidating `['sync','status']`).
- **`pages/sync/SyncPage.tsx`** (+ test, new) — the overlay sync experience inside
  `AppShell`: "Connected to Strava" card header, big percentage, progress bar with
  shimmer, the 4-stage checklist, over a blurred skeleton dashboard. On mount triggers
  `startSync`, then reads `useSyncStatus`. **Auto-navigates to `/home` when done** (no
  button). `empty` state → "Refresh from Strava" + "Skip" (Skip → `/home`). `error` state
  → retry (re-runs `startSync`). Route `/sync`.
- **`pages/app-home/`** (modify → Overview shell) — `AppHome` renders inside `AppShell`
  with a minimal **Overview**: real athlete (from `useAthlete`) and sync state, a
  "Refresh from Strava" action (`useRefreshSync`), and placeholder/skeleton blocks for the
  KPI/chart/recent/PR panels that Phases 4+ fill in. Redirects to `/sync` when status is
  `never_synced`.
- **`app/router.tsx`** (modify) — add the `/sync` route.

## Error handling

- **Backfill failures** (token refresh fail, Strava 401/429, network) → caught,
  `sync_state.status='error'` (logged, no secrets). Status endpoint surfaces `error`; the
  sync screen shows a retry that re-calls `POST /sync/start`.
- **Manual refresh** failures → `HTTPException(502)`; `/home` shows a transient error.
- **Unauthenticated** requests → `get_current_athlete_id` returns 401 (existing).

## Testing

- **Backend (pytest, Strava + Supabase stubbed via `httpx.MockTransport`; ruff + mypy):**
  `strava.list_activities` (Bearer + params); `services.tokens.get_valid_access_token`
  (expired→refresh+persist, valid→no-op); `db.activities`/`db.sync_state` wrappers;
  `services.sync` (`_to_activity_row` mapping incl. missing HR/polyline, `start_backfill`
  idempotency, `run_backfill` happy path, `get_status` never-synced, `refresh` count);
  `routers.sync` (`/status`, `/start` status-transition + background-task scheduled,
  `/refresh`, 401 without session).
- **Frontend (Vitest + RTL; components wrapped in a shared
  `QueryClientProvider`+`ThemeProvider` test helper):** landing re-port (existing tests
  green under new tokens); `useAthlete` migration; `AppShell`/`Sidebar`/`Topbar`;
  `api/sync` (credentials + methods); `useSyncStatus` (polls while `backfilling`, stops
  otherwise); `SyncPage` (progress render, empty/error states, auto-navigate on done);
  `AppHome` (redirect to `/sync` when `never_synced`, Refresh button). `npm test && npm
  run lint && npm run build` must pass.

## Increments (vertical slices, each implemented, verified, and committed)

1. **Backend backfill** — `strava.list_activities` + `StravaClient.close` +
   `services.tokens` + `clients.py` (deps refactor) + `db.activities` + `db.sync_state` +
   `services.sync` (mapping/start/run/status) + `routers.sync` (`GET /status`,
   `POST /start`) + register in `main.py`. Verify: pytest + ruff + mypy green.
2. **Unified design system + landing re-port** — vendor design files to `docs/design/`;
   new tokens/fonts/keyframes in `index.css`; updated `ThemeToggle`; re-port landing page;
   tests/lint/build green in both themes.
3. **TanStack Query foundation** — add dependency, `QueryProvider` in `App.tsx`, migrate
   `useAthlete` to `useQuery`, update tests with the provider wrapper. Behavior identical.
4. **App shell** — `AppShell` + `Sidebar` + `Topbar` (theme toggle, nav, user chip,
   logout/disconnect) with tests.
5. **Sync screen** — `types/sync`, `api/sync` (`useSyncStatus` + `useStartSync`),
   `pages/sync/SyncPage` (overlay, in shell), `/sync` route, `/home` redirect when
   `never_synced`, auto-navigate on done. Verify against the running backend.
6. **Minimal /home Overview shell** — `AppHome` rebuilt inside `AppShell` with the minimal
   Overview (real athlete + sync state, placeholders).
7. **Manual refresh** — `services.sync.refresh` + `POST /sync/refresh` (backend) +
   `useRefreshSync` + "Refresh from Strava" on `/home`. Verify end to end.

## Cross-cutting

- **Secrets:** no new env vars; Strava/Supabase credentials remain server-only.
- **Rate limits:** backfill paginates `per_page=200` (few pages per athlete); detail fetch
  stays lazy (Phase 6); refresh is incremental (`after=last_sync_at`).
- **Deployment:** runs on the existing single Render web service + Vercel SPA; no
  `render.yaml` change. Real backfill verified against the deployed stack with a live
  Strava account after automated tests pass.

## Open questions / risks

- **Free-dyno spin-down mid-backfill:** acceptable — state is in Supabase; re-entering
  `/sync` or hitting refresh continues. Revisit only if flaky in practice.
- **`progress` is approximate** (no Strava total count); the `synced` count is the precise
  signal.
- **Landing re-port scope:** unifying the design system touches the existing landing page
  and its tests; kept to a token/font re-skin with equivalent structure to limit churn.
