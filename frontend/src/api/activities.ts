import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { fmtDate, fmtDuration } from "@/lib/format";
import type {
  ActivityListDTO,
  ActivityListItemDTO,
  ActivityRowVM,
  SortDir,
  SortField,
} from "@/types/activities";
import { apiFetch } from "./client";

export interface ActivitiesQuery {
  q: string;
  minDist: string; // raw UI input, km
  minTime: string; // raw UI input, minutes
  minElev: string; // raw UI input, meters
  sort: SortField;
  direction: SortDir;
  page: number;
  asOf: string | null;
}

/** Build the `GET /activities` querystring, converting UI units to metric. */
export function buildActivitiesQuery(query: ActivitiesQuery): string {
  const p = new URLSearchParams();
  const q = query.q.trim();
  if (q) p.set("q", q);
  if (query.minDist !== "") p.set("min_dist", String(Number(query.minDist) * 1000));
  if (query.minTime !== "") p.set("min_time", String(Number(query.minTime) * 60));
  if (query.minElev !== "") p.set("min_elev", String(Number(query.minElev)));
  p.set("sort", query.sort);
  p.set("direction", query.direction);
  p.set("page", String(query.page));
  if (query.asOf) p.set("as_of", query.asOf);
  return p.toString();
}

export function toActivityRow(dto: ActivityListItemDTO): ActivityRowVM {
  return {
    id: dto.id,
    name: dto.name,
    meta: `${fmtDate(dto.start_date)} · ${dto.type}`,
    distLabel: `${(dto.distance_m / 1000).toFixed(1)} km`,
    durLabel: fmtDuration(dto.moving_time_s),
    elevLabel: `${Math.round(dto.elev_gain_m).toLocaleString("en-US")} m`,
    speedLabel:
      dto.avg_speed_ms === null ? "—" : `${(dto.avg_speed_ms * 3.6).toFixed(1)} km/h`,
  };
}

export function fetchActivities(query: ActivitiesQuery): Promise<ActivityListDTO> {
  return apiFetch<ActivityListDTO>(`/activities?${buildActivitiesQuery(query)}`);
}

export function useActivities(query: ActivitiesQuery) {
  return useQuery({
    queryKey: ["activities", "list", query],
    queryFn: () => fetchActivities(query),
    placeholderData: keepPreviousData,
  });
}
