import { useQuery } from "@tanstack/react-query";
import { config } from "@/lib/config";
import type { Athlete } from "@/types/athlete";
import { apiFetch } from "./client";

/** Full-page navigation target that starts Strava OAuth on the backend. */
export const stravaLoginUrl = `${config.apiBaseUrl}/auth/strava/login`;

export function fetchAthlete(): Promise<Athlete> {
  return apiFetch<Athlete>("/athlete");
}

export function logout(): Promise<void> {
  return apiFetch<void>("/auth/logout", { method: "POST" });
}

export function disconnect(): Promise<void> {
  return apiFetch<void>("/athlete/connection", { method: "DELETE" });
}

export type UseAthlete = {
  data: Athlete | null;
  isLoading: boolean;
  error: Error | null;
};

/** Loads the current athlete; a 401 surfaces as `error` (no retry). */
export function useAthlete(): UseAthlete {
  const { data, isLoading, error } = useQuery({
    queryKey: ["athlete"],
    queryFn: fetchAthlete,
  });
  return { data: data ?? null, isLoading, error: (error as Error) ?? null };
}
