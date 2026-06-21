export type SortField = "date" | "distance" | "time" | "elevation" | "speed";
export type SortDir = "asc" | "desc";

/** Raw activity item from `GET /activities`. */
export interface ActivityListItemDTO {
  id: number;
  name: string;
  type: string;
  start_date: string;
  distance_m: number;
  moving_time_s: number;
  elev_gain_m: number;
  avg_speed_ms: number | null;
}

export interface ActivityListDTO {
  activities: ActivityListItemDTO[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  as_of: string;
}

/** Formatted row the table renders. */
export interface ActivityRowVM {
  id: number;
  name: string;
  meta: string;       // "Tue · Jun 16 · Ride"
  distLabel: string;  // "38.7 km"
  durLabel: string;   // "1h 34m"
  elevLabel: string;  // "1,240 m"
  speedLabel: string; // "24.8 km/h" or "—"
}
