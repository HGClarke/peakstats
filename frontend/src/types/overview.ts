export type Period = "week" | "month" | "year";

export interface PeriodTotalsDTO {
  distance_m: number;
  elev_gain_m: number;
  moving_time_s: number;
  avg_speed_ms: number | null;
}

export interface TrendPointDTO {
  label: string;
  value: number; // distance in meters
}

export interface OverviewSummaryDTO {
  rides: number;
  prs: number;
  top_speed_ms: number | null;
  longest_ride_m: number;
  max_elev_m: number;
}

export interface RideTypeCountDTO {
  type: string;
  count: number;
}

export interface RecentRideDTO {
  id: number;
  name: string;
  type: string;
  start_date: string;
  start_date_local: string | null;
  distance_m: number;
  moving_time_s: number;
  is_pr: boolean;
}

export interface OverviewDTO {
  period: Period;
  this_period: PeriodTotalsDTO;
  last_period: PeriodTotalsDTO;
  trend: TrendPointDTO[];
  summary: OverviewSummaryDTO;
  ride_types: RideTypeCountDTO[];
  recent_rides: RecentRideDTO[];
}

/** Display shapes the Overview renders (formatted, units applied). */
export interface Kpi {
  label: string;
  value: string;
  unit: string;
  delta: string;
  deltaPositive: boolean;
}

export interface HeadlineKpi extends Kpi {
  periodLabel: string;   // "THIS WEEK" | "THIS MONTH" | "THIS YEAR"
  deltaCaption: string;  // "vs last week" | ...
}

export interface TrendPoint {
  label: string;
  value: number; // display distance units
}

export interface SummaryView {
  rides: string;
  prs: string;
  topSpeed: string;     // "11.0 km/h" or "—"
  longestRide: string;  // "64.0 km"
  maxElev: string;      // "980 m"
}

export interface RideTypeSlice {
  type: string;
  label: string;
  pct: string;       // "80%"
  fraction: number;  // 0..1
  color: string;     // CSS color (var(...))
}

export interface RideTypesView {
  total: number;
  items: RideTypeSlice[];
}

export interface DashRide {
  id: number;
  name: string;
  meta: string;       // "Tue · Jun 16 · Ride"
  distLabel: string;
  durLabel: string;
  isPr: boolean;
  dotColor: string;
}

export interface DashboardOverview {
  period: Period;
  headline: HeadlineKpi;
  secondary: Kpi[];
  trend: TrendPoint[];
  trendUnit: string;
  summary: SummaryView;
  rideTypes: RideTypesView;
  recentRides: DashRide[];
}
