import { useEffect, useState } from "react";
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

/** Loads the current athlete once on mount; a 401 surfaces as `error`. */
export function useAthlete(): UseAthlete {
  const [data, setData] = useState<Athlete | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let active = true;
    fetchAthlete().then(
      (athlete) => active && setData(athlete),
      (err) => active && setError(err as Error)
    );
    return () => {
      active = false;
    };
  }, []);

  return { data, isLoading: data === null && error === null, error };
}
