import type { WeekPoint } from "./ride";

/** Raw payload shapes returned by the backend `GET /activities/overview`. */
export interface WeekTotalsDTO {
  distance_m: number;
  elev_gain_m: number;
  moving_time_s: number;
  avg_speed_ms: number | null;
}

export interface RecentRideDTO {
  id: number;
  name: string;
  type: string;
  start_date: string;
  start_date_local: string | null;
  distance_m: number;
  moving_time_s: number;
}

export interface OverviewDTO {
  this_week: WeekTotalsDTO;
  last_week: WeekTotalsDTO;
  week: WeekPoint[];
  recent_rides: RecentRideDTO[];
}

/** Display shapes the Overview page renders (formatted, units applied). */
export interface Kpi {
  label: string;
  value: string;
  unit: string;
  /** Pre-formatted comparison vs. the previous week, e.g. "+18%" or "—". */
  delta: string;
  deltaPositive: boolean;
}

export interface DashRide {
  id: number;
  name: string;
  /** e.g. "Tue · Jun 16 · Ride". */
  meta: string;
  distLabel: string;
  durLabel: string;
}

export interface DashboardOverview {
  kpis: Kpi[];
  week: WeekPoint[];
  recentRides: DashRide[];
}
