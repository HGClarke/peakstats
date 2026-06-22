import { describe, expect, it } from "vitest";
import type { SegmentEffortDTO, SegmentListItemDTO } from "@/types/segments";
import {
  barWidth, buildSegmentsQuery, compareDelta, gradeBadge, prepareAttempts, toEffortRow,
  toSegmentRow,
} from "./segments";

const seg = (over: Partial<SegmentListItemDTO> = {}): SegmentListItemDTO => ({
  id: 5, name: "Hill", distance_m: 1200, avg_grade: 4.8, best_time_s: 118,
  attempts: 8, pr: true, latest_rank: 1, improvement_s: 4, recent_times_s: [130, 125, 118], ...over,
});

describe("gradeBadge", () => {
  it("labels the grade to one decimal", () => {
    expect(gradeBadge(4.8).label).toBe("4.8%");
    expect(gradeBadge(-1.2).label).toBe("-1.2%");
  });
  it("color-codes by steepness", () => {
    expect(gradeBadge(-2).color).toBe("var(--muted2)"); // descent
    expect(gradeBadge(2).color).toBe("#34d399");         // gentle
    expect(gradeBadge(6).color).toBe("#eab308");         // moderate
    expect(gradeBadge(10).color).toBe("#f59e0b");        // steep
    expect(gradeBadge(14).color).toBe("#ef4444");        // very steep
  });
  it("fills with the same color at low alpha, or --track for the var grey", () => {
    expect(gradeBadge(6).bg).toBe("#eab3081f");
    expect(gradeBadge(-2).bg).toBe("var(--track)");
  });
});

describe("toSegmentRow", () => {
  it("formats meta (distance), time, attempts, grade badge and trend", () => {
    expect(toSegmentRow(seg(), "metric")).toMatchObject({
      id: 5, name: "Hill", meta: "1.2 km",
      bestTime: "1:58", attemptsLabel: "8×",
      grade: { label: "4.8%", color: "#eab308", bg: "#eab3081f" },
      trend: [{ i: 0, t: 130 }, { i: 1, t: 125 }, { i: 2, t: 118 }],
    });
  });
  it("formats a segment row in imperial", () => {
    const row = toSegmentRow(seg(), "imperial"); // distance_m = 1200
    expect(row.meta).toMatch(/ mi$/);
  });
});

const eff = (over: Partial<SegmentEffortDTO> = {}): SegmentEffortDTO => ({
  id: 10, activity_id: 2, activity_name: "River loop", start_date: "2026-06-16T07:42:00Z",
  elapsed_time_s: 118, avg_watts: 240, avg_hr: 158, avg_speed_ms: 10.2, is_best: true, ...over,
});

describe("toEffortRow", () => {
  it("formats an effort row", () => {
    expect(toEffortRow(eff(), "metric")).toMatchObject({
      id: 10, date: "Jun 16", activity: "River loop", time: "1:58",
      power: "240 W", speed: "36.7 km/h", hr: "158 bpm", isBest: true,
    });
  });
  it("uses an em dash for missing power/hr", () => {
    const r = toEffortRow(eff({ avg_watts: null, avg_hr: null }), "metric");
    expect(r.power).toBe("—");
    expect(r.hr).toBe("—");
  });
  it("formats an effort speed per units", () => {
    expect(toEffortRow(eff(), "metric").speed).toMatch(/ km\/h$/);
    expect(toEffortRow(eff(), "imperial").speed).toMatch(/ mph$/);
  });
});

describe("compareDelta", () => {
  it("labels equal times as personal best", () => {
    expect(compareDelta(118, 118)).toEqual({ text: "Personal best", isBest: true });
  });
  it("labels a slower selection with the gap", () => {
    expect(compareDelta(118, 132)).toEqual({ text: "+14 slower", isBest: false });
    expect(compareDelta(118, 200)).toEqual({ text: "+1:22 slower", isBest: false });
  });
});

describe("barWidth", () => {
  it("returns a percentage of the max", () => {
    expect(barWidth(118, 236)).toBe("50.0%");
    expect(barWidth(0, 0)).toBe("0.0%");
  });
});

describe("buildSegmentsQuery", () => {
  it("includes page and as_of alongside q/sort/direction", () => {
    const p = new URLSearchParams(
      buildSegmentsQuery({ q: " river ", sort: "attempts", direction: "asc", page: 2,
        asOf: "2026-06-21T12:00:00Z" }),
    );
    expect(p.get("q")).toBe("river");          // trimmed
    expect(p.get("sort")).toBe("attempts");
    expect(p.get("direction")).toBe("asc");
    expect(p.get("page")).toBe("2");
    expect(p.get("as_of")).toBe("2026-06-21T12:00:00Z");
  });
  it("omits q when blank and as_of when null", () => {
    const p = new URLSearchParams(
      buildSegmentsQuery({ q: "", sort: "attempts", direction: "desc", page: 1, asOf: null }),
    );
    expect(p.has("q")).toBe(false);
    expect(p.has("as_of")).toBe(false);
    expect(p.get("page")).toBe("1");
  });
});

describe("prepareAttempts", () => {
  const efforts = [
    eff({ id: 1, activity_name: "River loop", elapsed_time_s: 118, start_date: "2026-06-21T00:00:00Z" }),
    eff({ id: 2, activity_name: "Hill repeats", elapsed_time_s: 130, start_date: "2026-06-10T00:00:00Z" }),
    eff({ id: 3, activity_name: "Club ride", elapsed_time_s: 125, start_date: "2026-06-15T00:00:00Z" }),
  ];
  it("filters by activity name", () => {
    const out = prepareAttempts(efforts, { query: "hill", sortKey: "date", sortDir: "desc", page: 1, pageSize: 10, units: "metric" });
    expect(out.total).toBe(1);
    expect(out.rows[0].activity).toBe("Hill repeats");
  });
  it("sorts by time ascending", () => {
    const out = prepareAttempts(efforts, { query: "", sortKey: "time", sortDir: "asc", page: 1, pageSize: 10, units: "metric" });
    expect(out.rows.map((r) => r.id)).toEqual([1, 3, 2]);
  });
  it("paginates", () => {
    const out = prepareAttempts(efforts, { query: "", sortKey: "time", sortDir: "asc", page: 2, pageSize: 2, units: "metric" });
    expect(out.totalPages).toBe(2);
    expect(out.rows.map((r) => r.id)).toEqual([2]);
  });
});
