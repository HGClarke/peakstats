import { describe, expect, it } from "vitest";
import type { ActivitiesQuery } from "./activities";
import { buildActivitiesQuery, toActivityRow } from "./activities";

const base: ActivitiesQuery = {
  q: "", minDist: "", minTime: "", minElev: "",
  sort: "date", direction: "desc", page: 1, asOf: null,
};

describe("buildActivitiesQuery", () => {
  it("omits empty filters and a null asOf", () => {
    const qs = new URLSearchParams(buildActivitiesQuery(base));
    expect(qs.get("q")).toBeNull();
    expect(qs.get("min_dist")).toBeNull();
    expect(qs.get("as_of")).toBeNull();
    expect(qs.get("sort")).toBe("date");
    expect(qs.get("direction")).toBe("desc");
    expect(qs.get("page")).toBe("1");
  });
  it("trims search and converts km->m, min->s, m->m", () => {
    const qs = new URLSearchParams(buildActivitiesQuery({
      ...base, q: "  loop ", minDist: "10", minTime: "30", minElev: "500",
    }));
    expect(qs.get("q")).toBe("loop");
    expect(qs.get("min_dist")).toBe("10000");
    expect(qs.get("min_time")).toBe("1800");
    expect(qs.get("min_elev")).toBe("500");
  });
  it("includes asOf when set", () => {
    const qs = new URLSearchParams(
      buildActivitiesQuery({ ...base, asOf: "2026-06-21T12:00:00Z" }),
    );
    expect(qs.get("as_of")).toBe("2026-06-21T12:00:00Z");
  });
});

describe("toActivityRow", () => {
  it("formats a ride row", () => {
    expect(toActivityRow({
      id: 1, name: "River loop", type: "Ride",
      start_date: "2026-06-16T07:42:00Z",
      distance_m: 38700, moving_time_s: 5662, elev_gain_m: 1240, avg_speed_ms: 6.889,
    })).toEqual({
      id: 1, name: "River loop", meta: "Tue · Jun 16 · Ride",
      distLabel: "38.7 km", durLabel: "1h 34m", elevLabel: "1,240 m",
      speedLabel: "24.8 km/h",
    });
  });
  it("shows an em dash for missing speed", () => {
    expect(toActivityRow({
      id: 2, name: "No GPS", type: "Ride", start_date: "2026-06-16T07:42:00Z",
      distance_m: 1000, moving_time_s: 600, elev_gain_m: 0, avg_speed_ms: null,
    }).speedLabel).toBe("—");
  });
});
