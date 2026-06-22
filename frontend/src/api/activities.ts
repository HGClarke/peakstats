import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { fmtDate, fmtDuration } from "@/lib/format";
import { distanceLabel, distanceToMeters, elevationLabel, elevationToMeters, speedLabel, type Units } from "@/lib/units";
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
  minDist: string; // raw UI input, in user's distance unit
  minTime: string; // raw UI input, minutes
  minElev: string; // raw UI input, in user's elevation unit
  sort: SortField;
  direction: SortDir;
  page: number;
  asOf: string | null;
  units: Units;
}

/** Build the `GET /activities` querystring, converting UI units to metric. */
export function buildActivitiesQuery(query: ActivitiesQuery): string {
  const p = new URLSearchParams();
  const q = query.q.trim();
  if (q) p.set("q", q);
  if (query.minDist !== "") p.set("min_dist", String(distanceToMeters(Number(query.minDist), query.units)));
  if (query.minTime !== "") p.set("min_time", String(Number(query.minTime) * 60));
  if (query.minElev !== "") p.set("min_elev", String(elevationToMeters(Number(query.minElev), query.units)));
  p.set("sort", query.sort);
  p.set("direction", query.direction);
  p.set("page", String(query.page));
  if (query.asOf) p.set("as_of", query.asOf);
  return p.toString();
}

export function toActivityRow(dto: ActivityListItemDTO, units: Units): ActivityRowVM {
  return {
    id: dto.id,
    name: dto.name,
    meta: `${fmtDate(dto.start_date)} · ${dto.type}`,
    distLabel: distanceLabel(dto.distance_m, units),
    durLabel: fmtDuration(dto.moving_time_s),
    elevLabel: elevationLabel(dto.elev_gain_m, units),
    speedLabel: dto.avg_speed_ms === null ? "—" : speedLabel(dto.avg_speed_ms, units),
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
