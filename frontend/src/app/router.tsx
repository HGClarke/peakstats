import { createBrowserRouter, type RouteObject } from "react-router";
import AppHome from "@/pages/app-home/AppHome";
import ActivitiesPage from "@/pages/activities/ActivitiesPage";
import LandingPage from "@/pages/landing/LandingPage";
import NotFoundPage from "@/pages/not-found/NotFoundPage";
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
  { path: "*", element: <NotFoundPage /> },
];

export const router = createBrowserRouter(routes);
