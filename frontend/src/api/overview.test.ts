import { describe, expect, it } from "vitest";
import type { OverviewDTO } from "@/types/overview";
import { toOverview } from "./overview";

const DTO: OverviewDTO = {
  period: "week",
  this_period: { distance_m: 30000, elev_gain_m: 1240, moving_time_s: 22320, avg_speed_ms: 6.889 },
  last_period: { distance_m: 25000, elev_gain_m: 1200, moving_time_s: 20000, avg_speed_ms: 6.0 },
  trend: [
    { label: "MON", value: 14800 },
    { label: "SUN", value: 38700 },
  ],
  summary: { rides: 6, prs: 2, top_speed_ms: 11.0, top_avg_power_w: 287, longest_ride_m: 64000, max_elev_m: 980 },
  ride_types: [
    { type: "Ride", count: 4 },
    { type: "VirtualRide", count: 1 },
  ],
  recent_rides: [
    { id: 1, name: "River loop", type: "Ride", start_date: "2026-06-16T07:42:00Z",
      start_date_local: "2026-06-16T07:42:00Z", distance_m: 38700, moving_time_s: 5662, is_pr: true },
  ],
  heatmap: { year: 2026, days: [{ date: "2026-06-16", distance_m: 38700 }] },
  week_distance_m: 38700,
  power_zones: {
    unset: false, avg: 210,
    buckets: [
      { z: "Z1", name: "Active Rec.", range: "< 110 W", seconds: 600, pct: 25 },
      { z: "Z2", name: "Endurance", range: "110–150 W", seconds: 1800, pct: 75 },
    ],
  },
  hr_zones: { unset: true, avg: null, buckets: [] },
};

describe("toOverview", () => {
  it("builds the headline KPI with period-aware labels and delta", () => {
    const { headline } = toOverview(DTO, "metric");
    expect(headline).toMatchObject({
      label: "DISTANCE", periodLabel: "THIS WEEK", value: "30.0", unit: "km",
      delta: "+20%", deltaPositive: true, deltaCaption: "vs last week",
    });
  });

  it("builds three secondary KPIs", () => {
    const { secondary } = toOverview(DTO, "metric");
    expect(secondary.map((k) => k.label)).toEqual(["MOVING TIME", "ELEVATION", "AVG SPEED"]);
    expect(secondary[2]).toMatchObject({ value: "24.8", unit: "km/h" });
  });

  it("converts trend values to display distance units", () => {
    const { trend, trendUnit } = toOverview(DTO, "metric");
    expect(trendUnit).toBe("km");
    expect(trend).toEqual([{ label: "MON", value: 14.8 }, { label: "SUN", value: 38.7 }]);
  });

  it("formats summary records", () => {
    const { summary } = toOverview(DTO, "metric");
    expect(summary).toMatchObject({
      rides: "6", prs: "2", topSpeed: "39.6 km/h",
      longestRide: "64.0 km", maxElev: "980 m",
    });
  });

  it("assigns percentages and colors to ride types", () => {
    const { rideTypes } = toOverview(DTO, "metric");
    expect(rideTypes.total).toBe(5);
    expect(rideTypes.items[0]).toMatchObject({ type: "Ride", pct: "80%" });
    expect(rideTypes.items[0].color).not.toEqual(rideTypes.items[1].color);
  });

  it("maps recent rides with PR flag and a dot color", () => {
    const { recentRides } = toOverview(DTO, "metric");
    expect(recentRides[0]).toMatchObject({ id: 1, name: "River loop", isPr: true });
    expect(recentRides[0].distLabel).toBe("38.7 km");
    expect(typeof recentRides[0].dotColor).toBe("string");
  });

  it("imperial summary uses miles", () => {
    const { summary } = toOverview(DTO, "imperial");
    expect(summary.longestRide).toBe("39.8 mi");
    expect(summary.topSpeed).toBe("24.6 mph");
  });

  it("builds a full-year heatmap with distance levels and range sentinels", () => {
    const dto: OverviewDTO = {
      ...DTO,
      heatmap: {
        year: 2026,
        days: [
          { date: "2026-03-10", distance_m: 9000 },   // <10k → level 1
          { date: "2026-03-11", distance_m: 10000 },  // <25k → level 2
          { date: "2026-03-12", distance_m: 25000 },  // <50k → level 3
          { date: "2026-03-13", distance_m: 50000 },  // ≥50k → level 4
        ],
      },
    };
    const { heatmap } = toOverview(dto, "metric", 100000);
    expect(heatmap.year).toBe(2026);
    expect(heatmap.activeDays).toBe(4);
    const lvl = Object.fromEntries(heatmap.data.map((d) => [d.date, d.level]));
    expect(lvl["2026-03-10"]).toBe(1);
    expect(lvl["2026-03-11"]).toBe(2);
    expect(lvl["2026-03-12"]).toBe(3);
    expect(lvl["2026-03-13"]).toBe(4);
    expect(lvl["2026-01-01"]).toBe(0); // range forced
    expect(lvl["2026-12-31"]).toBe(0);
  });

  it("builds the goal view with pct, labels, and remaining", () => {
    const { goal } = toOverview({ ...DTO, week_distance_m: 64000 }, "metric", 100000);
    expect(goal).toMatchObject({
      pct: 64, pctLabel: "64%", doneLabel: "64.0",
      targetLabel: "100.0", unit: "km", remainingLabel: "36.0",
    });
  });

  it("caps goal pct at 100 and floors remaining at 0", () => {
    const { goal } = toOverview({ ...DTO, week_distance_m: 120000 }, "metric", 100000);
    expect(goal.pct).toBe(100);
    expect(goal.remainingLabel).toBe("0.0");
  });

  it("falls back to the default goal when none is set", () => {
    const { goal } = toOverview({ ...DTO, week_distance_m: 50000 }, "metric", undefined);
    expect(goal.targetLabel).toBe("100.0"); // DEFAULT_WEEKLY_GOAL_M
  });

  it("imperial goal uses miles", () => {
    const { goal } = toOverview({ ...DTO, week_distance_m: 0 }, "imperial", 100000);
    expect(goal).toMatchObject({ unit: "mi", targetLabel: "62.1" });
  });

  it("formats top avg power in watts (no unit conversion)", () => {
    expect(toOverview(DTO, "metric").summary.topAvgPower).toBe("287 W");
    expect(toOverview(DTO, "imperial").summary.topAvgPower).toBe("287 W");
  });

  it("renders an em dash when no ride has power", () => {
    const dto = { ...DTO, summary: { ...DTO.summary, top_avg_power_w: null } };
    expect(toOverview(dto, "metric").summary.topAvgPower).toBe("—");
  });

  it("passes the power/HR zone blocks through unchanged", () => {
    const ov = toOverview(DTO, "metric");
    expect(ov.powerZones.buckets).toHaveLength(2);
    expect(ov.powerZones.unset).toBe(false);
    expect(ov.hrZones.unset).toBe(true);
  });
});
