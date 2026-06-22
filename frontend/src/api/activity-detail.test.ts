import { describe, expect, it } from "vitest";
import type { ActivityDetailDTO } from "@/types/activity-detail";
import { metaLabel, toPrimaryStats } from "./activity-detail";

const d = (o: Partial<ActivityDetailDTO> = {}): ActivityDetailDTO => ({
  id: 5, name: "Gravel", type: "Ride",
  start_date: "2026-06-21T14:42:00Z", start_date_local: "2026-06-21T07:42:00",
  location: null, distance_m: 84300, moving_time_s: 11820, elev_gain_m: 1284,
  avg_speed_ms: 7.13, avg_power_w: 198, normalized_power_w: 221, work_kj: 2342,
  avg_hr: 148, summary_polyline: "abc", ...o,
});

describe("toPrimaryStats", () => {
  it("builds 6 tiles in metric", () => {
    const s = toPrimaryStats(d(), "metric");
    expect(s.map((t) => t.label)).toEqual([
      "DISTANCE", "MOVING TIME", "ELEV GAIN", "AVG POWER", "AVG SPEED", "WORK",
    ]);
    expect(s[0]).toEqual({ label: "DISTANCE", value: "84.3", unit: "km" });
    expect(s[2]).toEqual({ label: "ELEV GAIN", value: "1,284", unit: "m" });
    expect(s[3]).toEqual({ label: "AVG POWER", value: "198", unit: "W" });
    expect(s[5]).toEqual({ label: "WORK", value: "2,342", unit: "kJ" });
  });
  it("shows em dash when power is missing", () => {
    const s = toPrimaryStats(d({ avg_power_w: null, work_kj: null }), "metric");
    expect(s[3].value).toBe("—");
    expect(s[5].value).toBe("—");
  });
  it("converts distance for imperial", () => {
    expect(toPrimaryStats(d(), "imperial")[0].unit).toBe("mi");
  });
});

describe("metaLabel", () => {
  it("formats the local date/time", () => {
    expect(metaLabel(d())).toBe("Sun · Jun 21, 2026 · 7:42 AM");
  });
});
