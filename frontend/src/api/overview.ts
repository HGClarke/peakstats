import { useQuery } from "@tanstack/react-query";
import type {
  DashboardOverview,
  DashRide,
  Kpi,
  OverviewDTO,
  RecentRideDTO,
} from "@/types/overview";
import { apiFetch } from "./client";
import { fmtDate, fmtDuration } from "@/lib/format";

function delta(current: number, previous: number): Pick<Kpi, "delta" | "deltaPositive"> {
  if (previous <= 0) return { delta: "—", deltaPositive: true };
  const pct = Math.round(((current - previous) / previous) * 100);
  return { delta: `${pct >= 0 ? "+" : ""}${pct}%`, deltaPositive: pct >= 0 };
}

function toRide(r: RecentRideDTO): DashRide {
  return {
    id: r.id,
    name: r.name,
    meta: `${fmtDate(r.start_date_local ?? r.start_date)} · ${r.type}`,
    distLabel: `${(r.distance_m / 1000).toFixed(1)} km`,
    durLabel: fmtDuration(r.moving_time_s),
  };
}

/** Maps the raw overview payload into the formatted shape the page renders. */
export function toOverview(dto: OverviewDTO): DashboardOverview {
  const t = dto.this_week;
  const l = dto.last_week;
  const thisSpeed = t.avg_speed_ms ?? 0;
  const lastSpeed = l.avg_speed_ms ?? 0;

  const kpis: Kpi[] = [
    {
      label: "DISTANCE",
      value: (t.distance_m / 1000).toFixed(1),
      unit: "km",
      ...delta(t.distance_m, l.distance_m),
    },
    {
      label: "MOVING TIME",
      value: fmtDuration(t.moving_time_s),
      unit: "",
      ...delta(t.moving_time_s, l.moving_time_s),
    },
    {
      label: "ELEVATION",
      value: Math.round(t.elev_gain_m).toLocaleString("en-US"),
      unit: "m",
      ...delta(t.elev_gain_m, l.elev_gain_m),
    },
    {
      label: "AVG SPEED",
      value: t.avg_speed_ms === null ? "—" : (thisSpeed * 3.6).toFixed(1),
      unit: "km/h",
      ...delta(thisSpeed, lastSpeed),
    },
  ];

  return {
    kpis,
    week: dto.week,
    recentRides: dto.recent_rides.map(toRide),
  };
}

export function fetchOverview(): Promise<DashboardOverview> {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  return apiFetch<OverviewDTO>(
    `/activities/overview?tz=${encodeURIComponent(tz)}`,
  ).then(toOverview);
}

export const OVERVIEW_REFETCH_INTERVAL_MS = 60_000;

export function overviewQueryOptions() {
  return {
    queryKey: ["activities", "overview"] as const,
    queryFn: fetchOverview,
    refetchOnWindowFocus: true,
    refetchInterval: OVERVIEW_REFETCH_INTERVAL_MS,
  };
}

export function useOverview() {
  return useQuery(overviewQueryOptions());
}
