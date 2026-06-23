# Demo mode — public `/demo` experience with curated example data

**Date:** 2026-06-22
**Branch:** fresh branch off `main` (routine feature).

## Problem

Anyone without a Strava account — recruiters in particular — currently sees only the
marketing landing page and the "Connect with Strava" wall. There's no way to view the
actual app (dashboard, activities, ride detail, segments) without authenticating with a
real Strava account that has ride history. We want a frictionless, shareable preview.

## Goal

A self-contained `/demo` experience that renders the **full app populated with example
data**, requiring no login and making **no backend calls**. A persistent banner frames it
as a demo and offers the "Connect with Strava" conversion path.

## Decisions (locked during brainstorming)

1. **Data source: frontend fixtures.** Demo data is bundled in the frontend; the `api/`
   layer resolves fixtures instead of hitting the backend. No login, no DB, works even if
   the backend is asleep. Fits the existing mock-swappable api-layer convention.
2. **Fixture source: handcrafted/curated** for everything *except* the hero-ride route
   geometry and stream arrays (see §7), which are pulled once from the real DB,
   anonymized, and frozen.
3. **Entry & URLs: dedicated `/demo/*` route prefix.** Demo mode is derived from the URL,
   so every link is shareable, bookmarkable, and unambiguously a demo. Real app routes are
   untouched.
4. **Interactivity: browse-only.** Navigation, maps, and charts are live; list controls
   (filter / sort / search / pagination) are hidden in demo. (See §9 Out of scope.)

## Architecture

### 1. Demo flag & routing — `src/demo/` + `src/app/router.tsx`

- New `src/demo/demo-context.ts` exports a `DemoContext` and the hooks `useDemoMode()`
  (`boolean`) and `useDemoLink()` (returns a `demoPath(path)` function). Context value +
  hooks live here; the provider component lives in its own file (per the repo's
  "provider and hook in separate files" rule for `react-refresh`).
- New `src/demo/DemoProvider.tsx` — provider component supplying `{ demo: true }`. Wraps
  the `/demo` subtree only.
- New `src/demo/DemoLayout.tsx` — a layout route element: renders the demo banner (§6) +
  `<AppShell>` + `<Outlet>`, wrapped in `<DemoProvider>`.
- `src/app/router.tsx` gains a `/demo` subtree that **reuses the exact same page
  components** as the real routes:

  | Demo path | Element |
  |---|---|
  | `/demo` | `AppHome` (the populated dashboard, not the marketing landing) |
  | `/demo/activities` | `ActivitiesPage` |
  | `/demo/activities/:id` | `ActivityDetailPage` |
  | `/demo/segments` | `SegmentsPage` |
  | `/demo/segments/:id` | `SegmentDetailPage` |
  | `/demo/settings` | `SettingsPage` |

  No `/demo/sync` — sync is an action page with no meaning in a read-only demo; it's
  dropped from demo nav.
- SPA deep-link fallback for `/demo/*` is already handled by the existing
  `"/(.*)" → "/index.html"` rewrite in `frontend/vercel.json`. No infra change.

### 2. Navigation — link prefixing

The one genuinely cross-cutting change. In demo, every in-app link must stay under
`/demo`. `useDemoLink()` returns `demoPath(path)` → `/demo${path}` when in demo,
`path` otherwise. Apply it at each link-building site:

- `components/app-shell/Sidebar.tsx`, `MobileNav.tsx`, `Topbar.tsx` (incl. the logo/home
  link).
- `pages/activities/components/ActivityTable.tsx` (row → ride detail).
- `pages/segments/components/SegmentTable.tsx` (row → segment detail).
- `pages/app-home/components/RecentRidesPanel.tsx` (recent-ride links).
- The back-arrow links in `ActivityDetailPage.tsx` / `SegmentDetailPage.tsx`.

`NavLink` active-state matching continues to work since the prefixed paths are still
absolute.

### 3. Data layer — fixtures + per-hook demo branch

- Each `use<Resource>()` hook in `src/api/*.ts` gains a demo branch: when `useDemoMode()`
  is `true`, it uses a demo `queryFn` that resolves from fixtures, under a distinct
  `["demo", …]` query key so demo and real caches never collide. Real fetch paths are
  untouched. Affected hooks: `useAthlete`, `useOverview`/overview, `useWeeklySummary`,
  `useActivities`, `useActivityDetail`, `useSegments`, `useSegmentDetail`, settings.
- `src/demo/resolvers.ts` maps each resource (and `:id` param) to its fixture, returning a
  resolved Promise so the hook's loading/empty states still exercise normally.
- Fixtures live in `src/demo/fixtures/` as **typed TS modules** that
  `satisfies` the existing `types/*.ts` shapes, so `tsc -b` flags any drift when those
  types change.

### 4. Browse-only — hide controls in demo

Pages read `useDemoMode()` and **do not render**:

- `pages/activities/ActivitiesPage.tsx`: the `<ActivityFilterBar>`, the `<SearchInput>`,
  sortable-header behavior, and the `<Pager>`. The table shows one curated fixture page.
- `pages/segments/SegmentsPage.tsx`: search, the attempts sort toggle, and the `<Pager>`.

### 5. Account / write actions in demo

- **Settings** (`SettingsProvider` + `SettingsPage`): theme + units toggles work
  **locally only** — `SettingsProvider` skips its backend `PATCH` when in demo, so toggles
  still visibly respond (km ↔ mi is a nice live touch). The `DisconnectCard` is hidden.
- **Logout / Sync**: not present in demo (no session; sync route omitted).

### 6. Demo framing & conversion

- **Banner** (rendered by `DemoLayout`, visible on every demo page): "You're viewing demo
  data — Connect with Strava to track your own rides," with the Strava CTA
  (`stravaLoginUrl` from `@/api/auth`) and an **Exit demo** link back to `/`.
- **Landing**: add a secondary **"View demo"** button beside "Connect with Strava" in
  `pages/landing/components/Hero.tsx`, linking to `/demo`.

### 7. Fixtures — content & the DB-sourced hero data

Handcrafted curated set, authored by hand as typed modules:

- ~12–20 rides for the activities list + the home-dashboard aggregates.
- A handful of segments + one segment-detail fixture (attempt history, sparkline data).
- Overview / weekly-summary aggregates; KPI tiles; settings defaults; a demo athlete
  (anonymized display name).
- **1–2 "hero" rides** with full detail: zones, climbs, laps (handcrafted) **plus a real
  route polyline and real power/HR/elevation streams pulled once from the DB**,
  anonymized, and frozen into fixture files. Hand-authoring polylines and stream arrays
  (hundreds–thousands of points) is impractical and looks synthetic; real frozen data
  makes the map and detail charts authentic with zero generation.

**One-time export step:** a small throwaway script (run locally, not shipped) selects a
couple of real rides, reads their `polyline` + `activity_streams`, strips identifiers, and
writes the result into `src/demo/fixtures/`. The script need not be committed; the frozen
JSON/TS fixtures are the deliverable.

### 8. Testing

- Per-page demo smoke tests: render each page inside `DemoProvider` (via a
  `renderInDemo` helper extending `@/test/providers`), assert key example content appears
  and **no network call is made** (fetch not invoked).
- `demoPath()` / `useDemoLink()` unit test (prefixes in demo, passthrough otherwise).
- A nav test asserting demo links carry the `/demo` prefix.
- Fixture shape is enforced at compile time via `satisfies`; no separate runtime test.

## Files

**Add**

- `src/demo/demo-context.ts` — context + `useDemoMode` + `useDemoLink`/`demoPath`.
- `src/demo/DemoProvider.tsx` — provider component.
- `src/demo/DemoLayout.tsx` — banner + AppShell + Outlet, wrapped in DemoProvider.
- `src/demo/resolvers.ts` — resource → fixture resolution.
- `src/demo/fixtures/*.ts` — typed fixtures (athlete, overview, weekly-summary, activities
  list, activity detail incl. hero streams/polyline, segments list, segment detail,
  settings).

**Change**

- `src/app/router.tsx` — add `/demo` subtree.
- `src/api/*.ts` — add demo branch to each resource hook.
- `components/app-shell/{Sidebar,MobileNav,Topbar}.tsx` — `demoPath()` links.
- `pages/activities/components/ActivityTable.tsx`,
  `pages/segments/components/SegmentTable.tsx`,
  `pages/app-home/components/RecentRidesPanel.tsx` — `demoPath()` row links.
- `pages/activity-detail/ActivityDetailPage.tsx`,
  `pages/segments/SegmentDetailPage.tsx` — `demoPath()` back links.
- `pages/activities/ActivitiesPage.tsx`, `pages/segments/SegmentsPage.tsx` — hide controls
  in demo.
- `app/providers/SettingsProvider.tsx`, `pages/settings/SettingsPage.tsx` — local-only
  toggles + hide disconnect in demo.
- `pages/landing/components/Hero.tsx` — add "View demo" button.

## Verification

- `cd frontend && npm test && npm run lint && npm run build`
- Manual: visit `/demo` (recruiter path) → dashboard populated; navigate to activities →
  detail (real map + charts) → segments → settings (units toggle responds, no disconnect);
  banner + Exit-demo present on every page; deep-link a shared `/demo/activities/:id`
  directly and confirm it loads; confirm **no requests to `/api/*`** in the network tab.

## Out of scope (v1)

- Working filters / sort / search / pagination in demo (browse-only by decision).
- A demo sync flow or any backend/DB involvement at runtime.
- A demo mode for write features (creating/editing) — there are none in the real app.
