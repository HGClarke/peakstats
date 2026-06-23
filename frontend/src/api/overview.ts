import { useQuery } from "@tanstack/react-query";
import type {
  DashboardOverview, DashRide, Kpi, OverviewDTO, Period,
  RecentRideDTO, RideTypeSlice,
} from "@/types/overview";
import { apiFetch } from "./client";
import { fmtDate, fmtDuration } from "@/lib/format";
import { useSettings } from "@/app/providers/settings-context";
import {
  distanceLabel, distanceUnit, distanceValue, elevationLabel, fmtDistance,
  fmtElevation, fmtSpeed, speedLabel, type Units,
} from "@/lib/units";

/** Ride-type palette — CSS vars defined in index.css (both themes). */
const TYPE_COLORS = [
  "var(--color-strava)", "var(--color-ride-2)", "var(--color-ride-3)",
  "var(--color-ride-4)", "var(--color-ride-5)",
];
const DEFAULT_DOT = "var(--color-strava)";

const PERIOD_NOUN: Record<Period, string> = { week: "week", month: "month", year: "year" };

function delta(current: number, previous: number): Pick<Kpi, "delta" | "deltaPositive"> {
  if (previous <= 0) return { delta: "—", deltaPositive: true };
  const pct = Math.round(((current - previous) / previous) * 100);
  return { delta: `${pct >= 0 ? "+" : ""}${pct}%`, deltaPositive: pct >= 0 };
}

function toRide(r: RecentRideDTO, units: Units, colorByType: Map<string, string>): DashRide {
  return {
    id: r.id,
    name: r.name,
    meta: `${fmtDate(r.start_date_local ?? r.start_date)} · ${r.type}`,
    distLabel: distanceLabel(r.distance_m, units),
    durLabel: fmtDuration(r.moving_time_s),
    isPr: r.is_pr,
    dotColor: colorByType.get(r.type) ?? DEFAULT_DOT,
  };
}

export function toOverview(dto: OverviewDTO, units: Units): DashboardOverview {
  const t = dto.this_period;
  const l = dto.last_period;
  const noun = PERIOD_NOUN[dto.period];

  const dist = fmtDistance(t.distance_m, units);
  const headline = {
    label: "DISTANCE",
    periodLabel: `THIS ${noun.toUpperCase()}`,
    value: dist.value,
    unit: dist.unit,
    deltaCaption: `vs last ${noun}`,
    ...delta(t.distance_m, l.distance_m),
  };

  const elev = fmtElevation(t.elev_gain_m, units);
  const thisSpeed = t.avg_speed_ms ?? 0;
  const lastSpeed = l.avg_speed_ms ?? 0;
  const speed = fmtSpeed(thisSpeed, units);
  const secondary: Kpi[] = [
    { label: "MOVING TIME", value: fmtDuration(t.moving_time_s), unit: "", ...delta(t.moving_time_s, l.moving_time_s) },
    { label: "ELEVATION", value: elev.value, unit: elev.unit, ...delta(t.elev_gain_m, l.elev_gain_m) },
    { label: "AVG SPEED", value: t.avg_speed_ms === null ? "—" : speed.value, unit: speed.unit, ...delta(thisSpeed, lastSpeed) },
  ];

  const total = dto.ride_types.reduce((sum, rt) => sum + rt.count, 0);
  const items: RideTypeSlice[] = dto.ride_types.map((rt, i) => ({
    type: rt.type,
    label: rt.type,
    pct: total > 0 ? `${Math.round((rt.count / total) * 100)}%` : "0%",
    fraction: total > 0 ? rt.count / total : 0,
    color: TYPE_COLORS[i % TYPE_COLORS.length],
  }));
  const colorByType = new Map(items.map((it) => [it.type, it.color]));

  return {
    period: dto.period,
    headline,
    secondary,
    trend: dto.trend.map((p) => ({ label: p.label, value: distanceValue(p.value, units) })),
    trendUnit: distanceUnit(units),
    summary: {
      rides: String(dto.summary.rides),
      prs: String(dto.summary.prs),
      topSpeed: dto.summary.top_speed_ms === null ? "—" : speedLabel(dto.summary.top_speed_ms, units),
      longestRide: distanceLabel(dto.summary.longest_ride_m, units),
      maxElev: elevationLabel(dto.summary.max_elev_m, units),
    },
    rideTypes: { total, items },
    recentRides: dto.recent_rides.map((r) => toRide(r, units, colorByType)),
  };
}

export function fetchOverview(period: Period): Promise<OverviewDTO> {
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  return apiFetch<OverviewDTO>(
    `/activities/overview?tz=${encodeURIComponent(tz)}&period=${period}`,
  );
}

export const OVERVIEW_REFETCH_INTERVAL_MS = 60_000;

export function useOverview(period: Period) {
  const { units } = useSettings();
  return useQuery({
    queryKey: ["activities", "overview", period] as const,
    queryFn: () => fetchOverview(period),
    refetchOnWindowFocus: true,
    refetchInterval: OVERVIEW_REFETCH_INTERVAL_MS,
    select: (dto: OverviewDTO) => toOverview(dto, units),
  });
}
