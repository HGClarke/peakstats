import { describe, expect, it, vi } from "vitest";
import type { OverviewDTO } from "@/types/overview";
import { toOverview, fetchOverview, overviewQueryOptions, OVERVIEW_REFETCH_INTERVAL_MS } from "./overview";

const DTO: OverviewDTO = {
  this_week: {
    distance_m: 30000,
    elev_gain_m: 1240,
    moving_time_s: 22320,
    avg_speed_ms: 6.889,
  },
  last_week: {
    distance_m: 25000,
    elev_gain_m: 1200,
    moving_time_s: 20000,
    avg_speed_ms: 6.0,
  },
  week: [
    { day: "MON", km: 14.8 },
    { day: "TUE", km: 12.4 },
    { day: "WED", km: 24.0 },
    { day: "THU", km: 8.0 },
    { day: "FRI", km: 18.2 },
    { day: "SAT", km: 26.5 },
    { day: "SUN", km: 38.7 },
  ],
  recent_rides: [
    {
      id: 1,
      name: "River loop",
      type: "Ride",
      start_date: "2026-06-16T07:42:00Z",
      start_date_local: "2026-06-16T07:42:00Z",
      distance_m: 38700,
      moving_time_s: 5662,
    },
  ],
};

describe("toOverview", () => {
  it("formats the four KPI cards with deltas", () => {
    const { kpis } = toOverview(DTO);
    expect(kpis.map((k) => k.label)).toEqual([
      "DISTANCE",
      "MOVING TIME",
      "ELEVATION",
      "AVG SPEED",
    ]);
    expect(kpis[0]).toMatchObject({ value: "30.0", unit: "km", delta: "+20%", deltaPositive: true });
    expect(kpis[1]).toMatchObject({ value: "6h 12m", unit: "", delta: "+12%" });
    expect(kpis[2]).toMatchObject({ value: "1,240", unit: "m", delta: "+3%" });
    expect(kpis[3]).toMatchObject({ value: "24.8", unit: "km/h", delta: "+15%" });
  });

  it("marks a decline as not positive", () => {
    const dto = { ...DTO, this_week: { ...DTO.this_week, distance_m: 20000 } };
    expect(toOverview(dto).kpis[0]).toMatchObject({ delta: "-20%", deltaPositive: false });
  });

  it("shows an em dash when there is no prior week to compare", () => {
    const dto = {
      ...DTO,
      last_week: { distance_m: 0, elev_gain_m: 0, moving_time_s: 0, avg_speed_ms: null },
    };
    expect(toOverview(dto).kpis[0].delta).toBe("—");
  });

  it("passes the weekly chart points through", () => {
    expect(toOverview(DTO).week).toEqual(DTO.week);
  });

  it("formats recent rides for display", () => {
    const ride = toOverview(DTO).recentRides[0];
    expect(ride).toEqual({
      id: 1,
      name: "River loop",
      meta: "Tue · Jun 16 · Ride",
      distLabel: "38.7 km",
      durLabel: "1h 34m",
    });
  });

  it("labels a recent ride by its local day, not UTC", () => {
    const dto = {
      ...DTO,
      recent_rides: [
        {
          id: 2,
          name: "Late ride",
          type: "Ride",
          start_date: "2026-06-21T06:00:00Z", // Sun UTC
          start_date_local: "2026-06-20T23:00:00Z", // Sat local
          distance_m: 12000,
          moving_time_s: 1200,
        },
      ],
    };
    expect(toOverview(dto).recentRides[0].meta).toBe("Sat · Jun 20 · Ride");
  });

  it("falls back to start_date when start_date_local is null", () => {
    const dto = {
      ...DTO,
      recent_rides: [
        {
          id: 3,
          name: "Legacy",
          type: "Ride",
          start_date: "2026-06-16T07:42:00Z",
          start_date_local: null,
          distance_m: 1000,
          moving_time_s: 100,
        },
      ],
    };
    expect(toOverview(dto).recentRides[0].meta).toBe("Tue · Jun 16 · Ride");
  });
});

describe("overviewQueryOptions", () => {
  it("refetches on window focus and on a 60s interval", () => {
    const opts = overviewQueryOptions();
    expect(opts.refetchOnWindowFocus).toBe(true);
    expect(opts.refetchInterval).toBe(OVERVIEW_REFETCH_INTERVAL_MS);
    expect(OVERVIEW_REFETCH_INTERVAL_MS).toBe(60_000);
  });
});

describe("fetchOverview", () => {
  it("requests the overview with the browser timezone", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(DTO), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await fetchOverview();
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("/activities/overview?tz=");
    vi.unstubAllGlobals();
  });
});
