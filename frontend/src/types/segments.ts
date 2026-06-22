export type SortDir = "asc" | "desc";
export type AttemptSortKey = "date" | "activity" | "time" | "power" | "speed" | "hr";

export interface SegmentListItemDTO {
  id: number;
  name: string;
  distance_m: number;
  avg_grade: number;
  best_time_s: number;
  attempts: number;
  pr: boolean;
  latest_rank: number;
  improvement_s: number | null;
}

export interface SegmentListDTO {
  segments: SegmentListItemDTO[];
}

export interface SegmentEffortDTO {
  id: number;
  activity_id: number;
  activity_name: string;
  start_date: string;
  elapsed_time_s: number;
  avg_watts: number | null;
  avg_hr: number | null;
  avg_speed_ms: number;
  is_best: boolean;
}

export interface SegmentDetailDTO {
  id: number;
  name: string;
  distance_m: number;
  avg_grade: number;
  pr_time_s: number;
  attempts: number;
  efforts: SegmentEffortDTO[];
}

/** Formatted row for the segments list table. */
export interface SegmentRowVM {
  id: number;
  name: string;
  meta: string;        // "1.2 km · 4.8% avg"
  bestTime: string;    // "1:58"
  statusText: string;  // "New PR · −4s" | "2nd best"
  isPr: boolean;
  attemptsLabel: string; // "8×"
}

/** Formatted row for the attempts table. */
export interface EffortRowVM {
  id: number;
  date: string;        // "Jun 16"
  activity: string;
  time: string;        // "1:58"
  power: string;       // "240 W" | "—"
  speed: string;       // "10.2 km/h"
  hr: string;          // "158 bpm" | "—"
  isBest: boolean;
}
