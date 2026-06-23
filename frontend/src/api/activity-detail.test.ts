import { describe, expect, it } from "vitest";
import type { ActivityDetailDTO } from "@/types/activity-detail";
import { metaLabel, toPrimaryStats } from "./activity-detail";

const d = (o: Partial<ActivityDetailDTO> = {}): ActivityDetailDTO => ({
  id: 5, name: "Gravel", type: "Ride",
  start_date: "2026-06-21T14:42:00Z", start_date_local: "2026-06-21T07:42:00",
  location: null, distance_m: 84300, moving_time_s: 11820, elev_gain_m: 1284,
  avg_speed_ms: 7.13, avg_power_w: 198, normalized_power_w: 221, work_kj: 2342,
  avg_hr: 148, summary_polyline: "abc",
  power_zones: { unset: true, avg: null, buckets: [] },
  hr_zones: { unset: true, avg: null, buckets: [] },
  climbs: [],
  ...o,
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

import { toChartPoints, xAxisLabels } from "./activity-detail";

describe("toChartPoints", () => {
  it("converts distance to km and pairs with the series", () => {
    const pts = toChartPoints([0, 1000, 2000], [100, 150, 200], "metric");
    expect(pts).toEqual([{ x: 0, y: 100 }, { x: 1, y: 150 }, { x: 2, y: 200 }]);
  });
  it("downsamples to maxPoints", () => {
    const d = Array.from({ length: 1000 }, (_, i) => i);
    const s = Array.from({ length: 1000 }, () => 200);
    expect(toChartPoints(d, s, "metric", { maxPoints: 100 }).length).toBeLessThanOrEqual(100);
  });
  it("is empty when a channel is null", () => {
    expect(toChartPoints(null, [1, 2], "metric")).toEqual([]);
    expect(toChartPoints([0, 1], null, "metric")).toEqual([]);
  });
});

describe("xAxisLabels", () => {
  it("returns 5 quarter labels", () => {
    expect(xAxisLabels(84300, "metric")).toEqual(["0.0", "21.1", "42.1", "63.2", "84.3"]); // 42.15 → "42.1" (IEEE754 toFixed)
  });
});

import { toZoneRows } from "./activity-detail";

describe("toZoneRows", () => {
  it("colors by index and scales bars to the max bucket", () => {
    const rows = toZoneRows({ unset: false, avg: 150, buckets: [
      { z: "Z1", name: "Active Rec.", range: "< 154 W", seconds: 600, pct: 20 },
      { z: "Z2", name: "Endurance", range: "154–210 W", seconds: 1200, pct: 40 },
    ]});
    expect(rows[0].color).toBe("var(--zone-1)");
    expect(rows[1].color).toBe("var(--zone-2)");
    expect(rows[0].barW).toBe("20.0%");   // absolute share of total time
    expect(rows[1].barW).toBe("40.0%");
    expect(rows[0].pctLabel).toBe("20%");
    expect(rows[0].dur).toBe("10m");      // 600s
  });
});

import { toClimbRows } from "./activity-detail";

describe("toClimbRows", () => {
  it("labels category (Strava: climb_category 2 → Cat 3), length, grade and gain", () => {
    const rows = toClimbRows([{ name: "Marincello", climb_category: 2, distance_m: 4300,
      avg_grade: 7.2, elev_gain_m: 310, time_s: 1089, vam: 1025 }], "metric");
    expect(rows[0]).toMatchObject({
      name: "Marincello", catLabel: "CAT 3", length: "4.3 km",
      grade: "7.2%", gain: "+310 m", vam: "1,025 m/h", time: "18:09",
    });
    expect(rows[0].catColor).toBe("var(--color-cat-3)");
  });
  it("colors the grade text by band, theme-aware via tokens (no background)", () => {
    const grade = (g: number) => toClimbRows([{ name: "X", climb_category: 1, distance_m: 1000,
      avg_grade: g, elev_gain_m: 100, time_s: 600, vam: 600 }], "metric")[0].gradeColor;
    expect(grade(-2)).toBe("var(--color-grade-descent)");
    expect(grade(2)).toBe("var(--color-grade-green)");
    expect(grade(6)).toBe("var(--color-grade-yellow)");
    expect(grade(10)).toBe("var(--color-grade-orange)");
    expect(grade(14)).toBe("var(--color-grade-red)");
  });
  it("labels HC for climb_category 5", () => {
    expect(toClimbRows([{ name: "X", climb_category: 5, distance_m: 1000, avg_grade: 10,
      elev_gain_m: 100, time_s: 600, vam: 600 }], "metric")[0].catLabel).toBe("HC");
  });
});
