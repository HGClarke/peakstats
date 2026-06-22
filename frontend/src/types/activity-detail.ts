export interface ZoneBucketDTO { z: string; name: string; range: string; seconds: number; pct: number }
export interface ZonesBlockDTO { unset: boolean; avg: number | null; buckets: ZoneBucketDTO[] }

export interface ActivityDetailDTO {
  id: number;
  name: string;
  type: string;
  start_date: string;
  start_date_local: string | null;
  location: string | null;
  distance_m: number;
  moving_time_s: number;
  elev_gain_m: number;
  avg_speed_ms: number | null;
  avg_power_w: number | null;
  normalized_power_w: number | null;
  work_kj: number | null;
  avg_hr: number | null;
  summary_polyline: string | null;
  power_zones: ZonesBlockDTO;
  hr_zones: ZonesBlockDTO;
}

export interface ActivityStreamsDTO {
  point_count: number;
  time: number[] | null;
  distance: number[] | null;
  altitude: number[] | null;
  watts: (number | null)[] | null;
  heartrate: (number | null)[] | null;
  velocity_smooth: number[] | null;
}

export interface PrimaryStat {
  label: string;
  value: string;
  unit: string;
}
