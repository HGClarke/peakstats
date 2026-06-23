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
  summary: { rides: 6, prs: 2, top_speed_ms: 11.0, longest_ride_m: 64000, max_elev_m: 980 },
  ride_types: [
    { type: "Ride", count: 4 },
    { type: "VirtualRide", count: 1 },
  ],
  recent_rides: [
    { id: 1, name: "River loop", type: "Ride", start_date: "2026-06-16T07:42:00Z",
      start_date_local: "2026-06-16T07:42:00Z", distance_m: 38700, moving_time_s: 5662, is_pr: true },
  ],
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
});
