import { useQuery } from "@tanstack/react-query";
import type {
  DashboardOverview,
  DashRide,
  Kpi,
  OverviewDTO,
  RecentRideDTO,
} from "@/types/overview";
import { apiFetch } from "./client";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function fmtDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m < 10 ? "0" : ""}${m}m` : `${m}m`;
}

function delta(current: number, previous: number): Pick<Kpi, "delta" | "deltaPositive"> {
  if (previous <= 0) return { delta: "—", deltaPositive: true };
  const pct = Math.round(((current - previous) / previous) * 100);
  return { delta: `${pct >= 0 ? "+" : ""}${pct}%`, deltaPositive: pct >= 0 };
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return `${WEEKDAYS[d.getUTCDay()]} · ${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`;
}

function toRide(r: RecentRideDTO): DashRide {
  return {
    id: r.id,
    name: r.name,
    meta: `${fmtDate(r.start_date)} · ${r.type}`,
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
  return apiFetch<OverviewDTO>("/activities/overview").then(toOverview);
}

export function useOverview() {
  return useQuery({
    queryKey: ["activities", "overview"],
    queryFn: fetchOverview,
  });
}
