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
import { useSettings } from "@/app/providers/settings-context";
import { fmtDistance, fmtElevation, fmtSpeed, distanceLabel, type Units } from "@/lib/units";

function delta(current: number, previous: number): Pick<Kpi, "delta" | "deltaPositive"> {
  if (previous <= 0) return { delta: "—", deltaPositive: true };
  const pct = Math.round(((current - previous) / previous) * 100);
  return { delta: `${pct >= 0 ? "+" : ""}${pct}%`, deltaPositive: pct >= 0 };
}

function toRide(r: RecentRideDTO, units: Units): DashRide {
  return {
    id: r.id,
    name: r.name,
    meta: `${fmtDate(r.start_date_local ?? r.start_date)} · ${r.type}`,
    distLabel: distanceLabel(r.distance_m, units),
    durLabel: fmtDuration(r.moving_time_s),
  };
}

/** Maps the raw overview payload into the formatted shape the page renders. */
export function toOverview(dto: OverviewDTO, units: Units): DashboardOverview {
  const t = dto.this_week;
  const l = dto.last_week;
  const thisSpeed = t.avg_speed_ms ?? 0;
  const lastSpeed = l.avg_speed_ms ?? 0;
  const dist = fmtDistance(t.distance_m, units);
  const elev = fmtElevation(t.elev_gain_m, units);
  const speed = fmtSpeed(thisSpeed, units);

  const kpis: Kpi[] = [
    { label: "DISTANCE", value: dist.value, unit: dist.unit, ...delta(t.distance_m, l.distance_m) },
    { label: "MOVING TIME", value: fmtDuration(t.moving_time_s), unit: "", ...delta(t.moving_time_s, l.moving_time_s) },
    { label: "ELEVATION", value: elev.value, unit: elev.unit, ...delta(t.elev_gain_m, l.elev_gain_m) },
    { label: "AVG SPEED", value: t.avg_speed_ms === null ? "—" : speed.value, unit: speed.unit, ...delta(thisSpeed, lastSpeed) },
  ];

  return { kpis, week: dto.week, recentRides: dto.recent_rides.map((r) => toRide(r, units)) };
}

export function fetchOverview(): Promise<OverviewDTO> {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  return apiFetch<OverviewDTO>(`/activities/overview?tz=${encodeURIComponent(tz)}`);
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
  const { units } = useSettings();
  return useQuery({
    ...overviewQueryOptions(),
    select: (dto: OverviewDTO) => toOverview(dto, units),
  });
}
