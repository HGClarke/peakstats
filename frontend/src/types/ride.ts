/**
 * Domain types for ride analytics. These describe the shapes the UI consumes;
 * the `api/` layer is responsible for mapping raw Strava/backend payloads into
 * them, so components never see provider-specific JSON.
 */

export interface StatTile {
  label: string;
  value: string;
  unit: string;
}

export interface WeekPoint {
  /** Short weekday label, e.g. "MON". */
  day: string;
  km: number;
}

export interface RecentRide {
  id: string;
  name: string;
  /** Display label for when the ride happened, e.g. "TUE · 07:42". */
  timeLabel: string;
  /** Display label for distance, e.g. "12.4 km". */
  distanceLabel: string;
  /** Hex color for the ride's marker dot. */
  markerColor: string;
}

export interface WeeklySummary {
  /** Total distance this week, in km, e.g. 142.6. */
  totalDistanceKm: number;
  /** Pre-formatted comparison vs. the previous week, e.g. "+18% vs last". */
  deltaLabel: string;
  stats: StatTile[];
  week: WeekPoint[];
  recentRides: RecentRide[];
}
