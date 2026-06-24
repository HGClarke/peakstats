import { createBrowserRouter, type RouteObject } from "react-router";
import LandingPage from "@/pages/landing/LandingPage";
import NotFoundPage from "@/pages/not-found/NotFoundPage";

// The authenticated app pages pull in heavy, route-specific deps (Leaflet,
// recharts, the activity calendar). Code-split them via react-router's route
// `lazy` so the public landing chunk — the first paint for an unauthenticated
// visitor — doesn't ship any of it. Landing and the 404 catch-all stay eager:
// they're entry points where a chunk round-trip would only add latency.
//
// `lazy` resolves a page's default export to the route's `Component`, so the
// router fetches the chunk on navigation before swapping the view in.
const page = (load: () => Promise<{ default: React.ComponentType }>) => () =>
  load().then((m) => ({ Component: m.default }));

/**
 * Route table. Add new pages here, pointing at a `pages/<page>/<Page>.tsx`.
 * Kept as a plain array so tests can mount it with `createMemoryRouter`.
 */
export const routes: RouteObject[] = [
  { path: "/", element: <LandingPage /> },
  { path: "/home", lazy: page(() => import("@/pages/app-home/AppHome")) },
  { path: "/activities", lazy: page(() => import("@/pages/activities/ActivitiesPage")) },
  { path: "/activities/:id", lazy: page(() => import("@/pages/activity-detail/ActivityDetailPage")) },
  { path: "/sync", lazy: page(() => import("@/pages/sync/SyncPage")) },
  { path: "/segments", lazy: page(() => import("@/pages/segments/SegmentsPage")) },
  { path: "/segments/:id", lazy: page(() => import("@/pages/segments/SegmentDetailPage")) },
  { path: "/settings", lazy: page(() => import("@/pages/settings/SettingsPage")) },
  { path: "*", element: <NotFoundPage /> },
];

export const router = createBrowserRouter(routes);
