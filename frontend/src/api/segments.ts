import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { fmtClock, fmtDate } from "@/lib/format";
import type {
  AttemptSortKey, EffortRowVM, SegmentDetailDTO, SegmentEffortDTO,
  SegmentListDTO, SegmentListItemDTO, SegmentRowVM, SortDir,
} from "@/types/segments";
import { apiFetch } from "./client";

const MINUS = "−"; // matches the design's "−4s"

function ordinal(n: number): string {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
  return `${n}${["th", "st", "nd", "rd"][n % 10] ?? "th"}`;
}

export function statusNote(s: SegmentListItemDTO): { text: string; isPr: boolean } {
  if (s.pr) {
    return {
      text: s.improvement_s != null ? `New PR · ${MINUS}${s.improvement_s}s` : "New PR",
      isPr: true,
    };
  }
  return { text: `${ordinal(s.latest_rank)} best`, isPr: false };
}

export function toSegmentRow(s: SegmentListItemDTO): SegmentRowVM {
  const note = statusNote(s);
  return {
    id: s.id,
    name: s.name,
    meta: `${(s.distance_m / 1000).toFixed(1)} km · ${s.avg_grade}% avg`,
    bestTime: fmtClock(s.best_time_s),
    statusText: note.text,
    isPr: note.isPr,
    attemptsLabel: `${s.attempts}×`,
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
}

export function buildSegmentsQuery(query: SegmentsQuery): string {
  const p = new URLSearchParams();
  const q = query.q.trim();
  if (q) p.set("q", q);
  p.set("sort", query.sort);
  p.set("direction", query.direction);
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
