import type { Units } from "@/lib/units";
import type { Athlete } from "@/types/athlete";
import { apiFetch } from "./client";

export type SettingsPatch = {
  units?: Units;
  theme?: "dark" | "light";
  ftp_w?: number;
  hr_max?: number;
};

/** Persist a partial settings update; resolves with the updated athlete. */
export function patchSettings(patch: SettingsPatch): Promise<Athlete> {
  return apiFetch<Athlete>("/athlete/settings", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}
