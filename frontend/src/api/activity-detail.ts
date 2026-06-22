import { useQuery } from "@tanstack/react-query";
import { fmtDuration } from "@/lib/format";
import { fmtDistance, fmtElevation, fmtSpeed, type Units } from "@/lib/units";
import type {
  ActivityDetailDTO, ActivityStreamsDTO, PrimaryStat,
} from "@/types/activity-detail";
import { apiFetch } from "./client";

const WD = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MO = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "Sat · Jun 21, 2026 · 7:42 AM" from start_date_local (fallback start_date). */
export function metaLabel(d: ActivityDetailDTO): string {
  // start_date_local is a naive wall-clock string (no zone); start_date ends in Z.
  // Append Z to naive strings so `new Date` parses them as UTC and getUTC* returns
  // the intended wall-clock components regardless of the machine's timezone.
  const raw = d.start_date_local ?? d.start_date;
  const iso = raw.endsWith("Z") || /[+-]\d\d:\d\d$/.test(raw) ? raw : `${raw}Z`;
  const t = new Date(iso);
  const h = t.getUTCHours();
  const m = t.getUTCMinutes();
  const ampm = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 === 0 ? 12 : h % 12;
  const clock = `${h12}:${String(m).padStart(2, "0")} ${ampm}`;
  return `${WD[t.getUTCDay()]} · ${MO[t.getUTCMonth()]} ${t.getUTCDate()}, ${t.getUTCFullYear()} · ${clock}`;
}

export function toPrimaryStats(d: ActivityDetailDTO, units: Units): PrimaryStat[] {
  const dist = fmtDistance(d.distance_m, units);
  const elev = fmtElevation(d.elev_gain_m, units);
  const speed = d.avg_speed_ms === null
    ? { value: "—", unit: "" } : fmtSpeed(d.avg_speed_ms, units);
  const round = (v: number | null) =>
    v === null ? "—" : Math.round(v).toLocaleString("en-US");
  return [
    { label: "DISTANCE", value: dist.value, unit: dist.unit },
    { label: "MOVING TIME", value: fmtDuration(d.moving_time_s), unit: "" },
    { label: "ELEV GAIN", value: elev.value, unit: elev.unit },
    { label: "AVG POWER", value: round(d.avg_power_w), unit: "W" },
    { label: "AVG SPEED", value: speed.value, unit: speed.unit },
    { label: "WORK", value: round(d.work_kj), unit: "kJ" },
  ];
}

export function fetchActivityDetail(id: number): Promise<ActivityDetailDTO> {
  return apiFetch<ActivityDetailDTO>(`/activities/${id}`);
}

export function useActivityDetail(id: number) {
  return useQuery({
    queryKey: ["activities", "detail", id],
    queryFn: () => fetchActivityDetail(id),
  });
}

export function fetchActivityStreams(id: number): Promise<ActivityStreamsDTO> {
  return apiFetch<ActivityStreamsDTO>(`/activities/${id}/streams`);
}

export function useActivityStreams(id: number) {
  return useQuery({
    queryKey: ["activities", "streams", id],
    queryFn: () => fetchActivityStreams(id),
  });
}

export interface ChartPoint { x: number; y: number }

export function toChartPoints(
  distance: number[] | null,
  series: (number | null)[] | null,
  units: Units,
  opts: { maxPoints?: number } = {},
): ChartPoint[] {
  if (!distance || !series) return [];
  const max = opts.maxPoints ?? 320;
  const n = Math.min(distance.length, series.length);
  const stride = Math.max(1, Math.ceil(n / max));
  const toX = (m: number) =>
    units === "imperial" ? m / 1609.344 : m / 1000;
  const out: ChartPoint[] = [];
  for (let i = 0; i < n; i += stride) {
    const y = series[i];
    if (y === null || y === undefined) continue;
    out.push({ x: Number(toX(distance[i]).toFixed(3)), y });
  }
  return out;
}

export function xAxisLabels(distanceMeters: number, units: Units): string[] {
  return [0, 0.25, 0.5, 0.75, 1].map(
    (f) => fmtDistance(distanceMeters * f, units).value,
  );
}

import type { ZonesBlockDTO } from "@/types/activity-detail";

export interface ZoneRowVM {
  z: string; name: string; range: string; color: string;
  barW: string; dur: string; pctLabel: string;
}

export function zoneColor(index: number): string {
  return `var(--color-zone-${Math.min(index + 1, 7)})`;
}

export function toZoneRows(block: ZonesBlockDTO): ZoneRowVM[] {
  const maxPct = Math.max(1, ...block.buckets.map((b) => b.pct));
  return block.buckets.map((b, i) => ({
    z: b.z, name: b.name, range: b.range, color: zoneColor(i),
    barW: `${((b.pct / maxPct) * 100).toFixed(1)}%`,
    dur: fmtDuration(b.seconds),
    pctLabel: `${Math.round(b.pct)}%`,
  }));
}
