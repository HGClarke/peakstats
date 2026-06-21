import { useEffect, useState } from "react";
import type { WeeklySummary } from "@/types/ride";
// import { apiFetch } from "./client";

/**
 * Placeholder data the landing dashboard renders today. When the backend
 * endpoint exists, delete this and have `fetchWeeklySummary` call
 * `apiFetch<WeeklySummary>("/api/weekly-summary")` — the shape is identical, so
 * no component needs to change.
 */
const MOCK_WEEKLY_SUMMARY: WeeklySummary = {
  totalDistanceKm: 142.6,
  deltaLabel: "+18% vs last",
  stats: [
    { label: "ELEVATION", value: "1,240", unit: "m" },
    { label: "MOVING TIME", value: "6h 12m", unit: "" },
    { label: "AVG SPEED", value: "24.8", unit: "km/h" },
  ],
  week: [
    { day: "MON", km: 8.2 },
    { day: "TUE", km: 12.4 },
    { day: "WED", km: 0 },
    { day: "THU", km: 24.1 },
    { day: "FRI", km: 0 },
    { day: "SAT", km: 59.3 },
    { day: "SUN", km: 38.6 },
  ],
  recentRides: [
    {
      id: "1",
      name: "Morning commute",
      timeLabel: "TUE · 07:42",
      distanceLabel: "12.4 km",
      markerColor: "#fc4c02",
    },
    {
      id: "2",
      name: "River loop",
      timeLabel: "SUN · 09:15",
      distanceLabel: "38.7 km",
      markerColor: "#1f9d63",
    },
  ],
};

/** Fetches the current week's ride summary. Mocked until the API endpoint lands. */
export async function fetchWeeklySummary(): Promise<WeeklySummary> {
  // return apiFetch<WeeklySummary>("/api/weekly-summary");
  return Promise.resolve(MOCK_WEEKLY_SUMMARY);
}

export type UseWeeklySummary = {
  data: WeeklySummary | null;
  isLoading: boolean;
  error: Error | null;
};

/** Loads the weekly summary once on mount, exposing loading/error state. */
export function useWeeklySummary(): UseWeeklySummary {
  const [data, setData] = useState<WeeklySummary | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let active = true;
    fetchWeeklySummary().then(
      (summary) => active && setData(summary),
      (err) => active && setError(err as Error)
    );
    return () => {
      active = false;
    };
  }, []);

  return { data, isLoading: data === null && error === null, error };
}
