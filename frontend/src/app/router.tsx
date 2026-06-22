import { createBrowserRouter, type RouteObject } from "react-router";
import AppHome from "@/pages/app-home/AppHome";
import ActivitiesPage from "@/pages/activities/ActivitiesPage";
import LandingPage from "@/pages/landing/LandingPage";
import NotFoundPage from "@/pages/not-found/NotFoundPage";
import SegmentDetailPage from "@/pages/segments/SegmentDetailPage";
import SegmentsPage from "@/pages/segments/SegmentsPage";
import SettingsPage from "@/pages/settings/SettingsPage";
import SyncPage from "@/pages/sync/SyncPage";

/**
 * Route table. Add new pages here, pointing at a `pages/<page>/<Page>.tsx`.
 * Kept as a plain array so tests can mount it with `createMemoryRouter`.
 */
export const routes: RouteObject[] = [
  { path: "/", element: <LandingPage /> },
  { path: "/home", element: <AppHome /> },
  { path: "/activities", element: <ActivitiesPage /> },
  { path: "/sync", element: <SyncPage /> },
  { path: "/segments", element: <SegmentsPage /> },
  { path: "/segments/:id", element: <SegmentDetailPage /> },
  { path: "/settings", element: <SettingsPage /> },
  { path: "*", element: <NotFoundPage /> },
];

export const router = createBrowserRouter(routes);
