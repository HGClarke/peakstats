# Peakstats — Settings Phase Design Spec

**Date:** 2026-06-22
**Status:** Approved (design); pending implementation plan
**Parent spec:** `2026-06-20-peakstats-design.md` (Phase 7 — Settings & polish)

## Overview

This spec covers Phase 7.1 + 7.2 of the parent design: the Settings screen plus
units/theme persistence and **live metric↔imperial conversion** across the app. It
is one slice because the two items are tightly coupled — a units control is
meaningless without conversion, and both prefs share one persistence path.

**In scope:** `PATCH /athlete/settings`; a Settings screen at `/settings` (Units,
Appearance/Theme, Account/Disconnect); a `SettingsProvider` that hydrates from the
athlete record and persists changes server-side; a `lib/units.ts` conversion module;
refactoring the existing api transforms to format units on read.

**Out of scope:** `default_period` (no consumer today — Overview is week-only and
Trends was cut; the DB field is left untouched, no control surfaced); the 7.3 polish
pass (per-view empty states, responsive sweep) ships as a separate slice.

## Goals

- Toggling units instantly re-renders all distance / elevation / speed values
  app-wide, with no refetch.
- Units and theme persist to the athlete record (`athletes.settings` JSONB) and
  survive reload / new device — server is the source of truth.
- Disconnect (revoke Strava + delete data) is reachable from Settings.

## Non-goals

- A `default_period` control (deferred until a period selector exists).
- New unit dimensions beyond distance (km/mi), elevation (m/ft), speed (km/h /
  mph) — matching the prototype's `renderVals()`.
- Empty states / responsive polish (Phase 7.3).

## Key decisions

### 1. Conversion happens on read (format-on-read)

Today `api/overview.ts`, `api/activities.ts`, and `api/segments.ts` bake metric→km
strings at fetch time (e.g. `distLabel: "30.0 km"`, `unit: "km"`). To make a units
toggle reactive without refetching, unit-bearing fields move to **raw metric numbers
in the cache**, and formatting happens at render via a `useSettings()` hook + a pure,
tested `lib/units.ts` module. This mirrors the prototype's `renderVals()` (format at
render) and stays convention-clean: the frontend guide explicitly allows presentational
components to *read context*.

Rejected alternative: thread `units` into every api transform and re-key TanStack
queries on units. Keeps formatting in the api layer but triggers a refetch + loading
flash on every toggle.

### 2. One `SettingsProvider` (replaces the theme-only provider)

A single provider exposes `{ units, theme, setUnits, setTheme, toggleTheme }`,
hydrated from the existing `useAthlete()` query (server is source of truth) and
persisting each change via `PATCH /athlete/settings`. localStorage is retained **only**
as a pre-auth boot hint for theme, to avoid a flash of the wrong theme before the
athlete record loads. The provider keeps the existing `.dark`-class DOM side-effect.

Rejected alternative: two parallel providers (Theme + Units) — duplicates hydration
and persistence wiring for no benefit.

## Backend

`PATCH /athlete/settings` — partial update of the settings JSONB; returns the updated
profile. Follows the repo's routers→services→db layering.

- **models/athlete.py** — `SettingsUpdate(BaseModel)`: `units: Literal["metric",
  "imperial"] | None = None`, `theme: Literal["dark", "light"] | None = None`. All
  fields optional; at least one required (reject an empty body with 422). Unknown
  fields rejected. Reuse `AthleteResponse` for the return shape.
- **db/athletes.py** — `update_settings(client, athlete_id, patch: dict) -> AthleteRow`:
  read current settings, shallow-merge the patch, write back the merged JSONB, return
  the updated row. (Read-merge-write keeps unspecified keys like `default_period`
  intact and avoids clobbering.)
- **services/athletes.py** — `update_settings(supabase, athlete_id, patch:
  SettingsUpdate) -> AthleteResponse | None`: drop `None` fields, call the db helper,
  map to `AthleteResponse`. Returns `None` if the athlete row is missing (router → 404).
- **routers/athletes.py** — `@router.patch("/settings", response_model=AthleteResponse)`;
  auth-scoped via `get_current_athlete_id`; 404 when the service returns `None`.
- **Tests** — `tests/db`, `tests/services`, `tests/routers` mirroring each layer;
  the router test patches the service boundary (per testing conventions). Cover:
  partial update merges (doesn't drop other keys), enum validation rejects bad values,
  empty body → 422, unknown athlete → 404.

RLS already scopes writes to the owning athlete; no policy change needed. No DB
migration needed — the `settings` column and its default already exist (0001).

## Frontend

### `lib/units.ts` (pure, unit-tested)

- `type Units = "metric" | "imperial"`.
- Converters: `metersToDistance(m, units)`, `metersToElevation(m, units)`,
  `msToSpeed(ms, units)` returning numbers.
- Formatters returning `{ value: string, unit: string }`:
  `fmtDistance(m, units)` → `{ "30.0", "km" | "mi" }`,
  `fmtElevation(m, units)` → `{ …, "m" | "ft" }`,
  `fmtSpeed(ms, units)` → `{ …, "km/h" | "mph" }`.
- Rounding matches current behavior (distance 1 decimal, elevation integer, speed
  1 decimal). Constants: 1 mi = 1609.344 m, 1 ft = 0.3048 m.

### api transform refactor

`api/overview.ts`, `api/activities.ts`, `api/segments.ts` stop producing km strings
for unit-bearing fields and pass through raw metric numbers (`distance_m`,
`elev_gain_m`, `avg_speed_ms`). Non-unit formatting (durations, dates, clocks) is
unchanged. Consuming components format via the settings hook + `lib/units.ts`. Update
the affected component/api tests to assert structured numbers + render-time formatting.

### `SettingsProvider` (`app/providers/`)

- Files split per the react-refresh lint rule: `SettingsProvider.tsx` (component
  only) + `settings-context.ts` (context + `useSettings` hook). Supersedes
  `ThemeProvider` / `theme-context.ts`.
- Hydrates `units` + `theme` from `useAthlete()` when the query resolves; before
  that, `theme` comes from the localStorage boot hint (default `"dark"`), `units`
  defaults to `"metric"`.
- `setUnits` / `setTheme` / `toggleTheme`: optimistic local update + `PATCH
  /athlete/settings`; on failure, revert and surface an error. On success, mirror
  `theme` into localStorage so the next pre-auth paint is correct.
- Retains the `document.documentElement.classList.toggle("dark", …)` effect.
- `useTheme()` kept as a thin compatibility shim over `useSettings()` (or call sites
  migrated) so existing `ThemeToggle` / pages keep working.
- **The existing header `ThemeToggle` persists too.** Its `toggleTheme()` now routes
  through the provider's persisting path (optimistic update + `PATCH
  /athlete/settings` + localStorage mirror), so flipping the theme from the header —
  not just the Settings screen — updates the saved setting. There is one toggle
  implementation; both entry points call it. A test asserts that clicking
  `ThemeToggle` issues the PATCH.

### Settings screen (`pages/settings/`, route `/settings`)

- `SettingsPage.tsx` composes section components (page = composition only):
  - **Units** — Metric / Imperial segmented control → `setUnits`.
  - **Appearance** — Dark / Light control → `setTheme`.
  - **Account** — athlete name + avatar, "Connected to Strava", and **Disconnect**.
- **Disconnect** → confirmation dialog → `DELETE /athlete/connection` (existing
  `disconnectStrava()` in `api/auth.ts`) → on success redirect to `/` (landing).
- Add `{ path: "/settings", element: <SettingsPage /> }` to `app/router.tsx`
  (before the `*` catch-all).
- **Sidebar nav** — add a **Settings** item (route `/settings`), replacing the
  dead routeless "Goals" entry; wire `navActive` so it highlights on `/settings`.
- **Tests** — Settings page renders the three sections; toggling Units / Theme calls
  the provider setter (→ PATCH); Disconnect opens the dialog and, on confirm, calls
  `disconnectStrava` + navigates to `/`.

## Data flow

```
Settings screen toggle
  → useSettings().setUnits/setTheme  (optimistic state update)
  → PATCH /athlete/settings          (persist; revert on failure)
  → athletes_service.update_settings → db.update_settings (merge JSONB)
  ← AthleteResponse (updated settings)

Render of any distance/elev/speed value
  → component reads { units } from useSettings()
  → lib/units.ts formats the raw metric number → { value, unit }
  (no refetch; toggling units re-renders instantly)
```

## Testing

- **Backend:** pytest across db / service / router layers (merge-preserves-keys,
  enum validation, empty-body 422, unknown-athlete 404).
- **Frontend:** Vitest for `lib/units.ts` (conversion + formatting math), the
  `SettingsProvider` (hydrate from athlete, optimistic update, revert on PATCH
  failure, localStorage theme mirror), and the Settings page (toggles persist,
  disconnect confirm → DELETE → redirect). Existing overview/activities/segments
  tests updated for the format-on-read refactor.
- Gates: backend `pytest` + `ruff` + `mypy`; frontend `npm test` + `npm run lint`
  + `npm run build` — all green before done.

## Delivery (vertical slices)

Per the parent spec's one-feature-at-a-time principle, build and verify in order:

1. **Backend** `PATCH /athlete/settings` (model → db → service → router → tests).
2. **`lib/units.ts`** conversion module + tests (pure, no UI yet).
3. **`SettingsProvider`** — hydrate + persist + theme reconciliation (replaces
   ThemeProvider); existing theme behavior stays green.
4. **api transform refactor** to format-on-read; update consuming components/tests so
   km still renders correctly under the default metric setting.
5. **Settings screen** + route + sidebar nav + disconnect flow.

Each slice is independently verifiable; slice 4 is where the units toggle becomes
visibly live end-to-end.

## Risks / notes

- The format-on-read refactor (slice 4) touches the most files; keeping it a distinct
  slice after the provider exists limits blast radius and keeps each step demoable.
- `useTheme()` shim avoids a wide rename in one go; call sites can migrate to
  `useSettings()` opportunistically.
- Read-merge-write on the JSONB is non-atomic, but settings writes are single-user,
  low-frequency, and last-write-wins is acceptable here.
