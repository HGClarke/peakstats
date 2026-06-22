import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { fmtClock, fmtDate } from "@/lib/format";
import type {
  AttemptSortKey, EffortRowVM, GradeBadge, SegmentDetailDTO, SegmentEffortDTO,
  SegmentListDTO, SegmentListItemDTO, SegmentRowVM, SortDir,
} from "@/types/segments";
import { apiFetch } from "./client";

/**
 * Grade badge color-coded by steepness, mirroring the design: grey for
 * descents, then green / yellow / amber / red as the climb gets steeper.
 * The fill is the same color at ~12% alpha (or --track for the var-based grey).
 */
export function gradeBadge(avgGrade: number): GradeBadge {
  const color =
    avgGrade < 0 ? "var(--muted2)" :   // descent
    avgGrade < 4 ? "#34d399" :         // flat / gentle
    avgGrade < 8 ? "#eab308" :         // moderate
    avgGrade < 12 ? "#f59e0b" :        // steep
    "#ef4444";                          // very steep
  const bg = color.startsWith("#") ? `${color}1f` : "var(--track)";
  return { label: `${avgGrade.toFixed(1)}%`, color, bg };
}

export function toSegmentRow(s: SegmentListItemDTO): SegmentRowVM {
  return {
    id: s.id,
    name: s.name,
    meta: `${(s.distance_m / 1000).toFixed(1)} km`,
    bestTime: fmtClock(s.best_time_s),
    attemptsLabel: `${s.attempts}×`,
    grade: gradeBadge(s.avg_grade),
    trend: s.recent_times_s.map((t, i) => ({ i, t })),
  };
}

export function toEffortRow(e: SegmentEffortDTO): EffortRowVM {
  return {
    id: e.id,
    date: fmtDate(e.start_date).replace(/^\w+ · /, ""), // "Jun 16"
    activity: e.activity_name,
    time: fmtClock(e.elapsed_time_s),
    power: e.avg_watts === null ? "—" : `${Math.round(e.avg_watts)} W`,
    speed: `${(e.avg_speed_ms * 3.6).toFixed(1)} km/h`,
    hr: e.avg_hr === null ? "—" : `${e.avg_hr} bpm`,
    isBest: e.is_best,
  };
}

export function compareDelta(bestSec: number, selSec: number): { text: string; isBest: boolean } {
  const d = selSec - bestSec;
  if (d === 0) return { text: "Personal best", isBest: true };
  return { text: `+${fmtClock(d).replace(/^0:/, "")} slower`, isBest: false };
}

export function barWidth(timeSec: number, maxSec: number): string {
  return `${((timeSec / (maxSec || 1)) * 100).toFixed(1)}%`;
}

const ATTEMPT_KEYS: Record<AttemptSortKey, (e: SegmentEffortDTO) => number | string | null> = {
  date: (e) => e.start_date,
  activity: (e) => e.activity_name.toLowerCase(),
  time: (e) => e.elapsed_time_s,
  power: (e) => e.avg_watts,
  speed: (e) => e.avg_speed_ms,
  hr: (e) => e.avg_hr,
};

export function prepareAttempts(
  efforts: SegmentEffortDTO[],
  opts: { query: string; sortKey: AttemptSortKey; sortDir: SortDir; page: number; pageSize: number },
): { rows: EffortRowVM[]; total: number; totalPages: number } {
  const q = opts.query.trim().toLowerCase();
  const filtered = efforts.filter(
    (e) => !q || e.activity_name.toLowerCase().includes(q) || fmtDate(e.start_date).toLowerCase().includes(q),
  );
  const key = ATTEMPT_KEYS[opts.sortKey];
  const dir = opts.sortDir === "asc" ? 1 : -1;
  const sorted = [...filtered].sort((a, b) => {
    const av = key(a);
    const bv = key(b);
    if (av === null) return 1; // nulls last regardless of direction
    if (bv === null) return -1;
    if (av < bv) return -1 * dir;
    if (av > bv) return 1 * dir;
    return 0;
  });
  const total = sorted.length;
  const totalPages = Math.max(1, Math.ceil(total / opts.pageSize));
  const start = (opts.page - 1) * opts.pageSize;
  return {
    rows: sorted.slice(start, start + opts.pageSize).map(toEffortRow),
    total,
    totalPages,
  };
}

export interface SegmentsQuery {
  q: string;
  sort: "attempts";
  direction: SortDir;
  page: number;
  asOf: string | null;
}

export function buildSegmentsQuery(query: SegmentsQuery): string {
  const p = new URLSearchParams();
  const q = query.q.trim();
  if (q) p.set("q", q);
  p.set("sort", query.sort);
  p.set("direction", query.direction);
  p.set("page", String(query.page));
  if (query.asOf) p.set("as_of", query.asOf);
  return p.toString();
}

export function fetchSegments(query: SegmentsQuery): Promise<SegmentListDTO> {
  return apiFetch<SegmentListDTO>(`/segments?${buildSegmentsQuery(query)}`);
}

export function useSegments(query: SegmentsQuery) {
  return useQuery({
    queryKey: ["segments", "list", query],
    queryFn: () => fetchSegments(query),
    placeholderData: keepPreviousData,
  });
}

export function fetchSegment(id: number): Promise<SegmentDetailDTO> {
  return apiFetch<SegmentDetailDTO>(`/segments/${id}`);
}

export function useSegment(id: number) {
  return useQuery({
    queryKey: ["segments", "detail", id],
    queryFn: () => fetchSegment(id),
  });
}
