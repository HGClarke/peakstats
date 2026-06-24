export interface ZoneBucketDTO { z: string; name: string; range: string; seconds: number; pct: number }
export interface ZonesBlockDTO { unset: boolean; avg: number | null; buckets: ZoneBucketDTO[] }
