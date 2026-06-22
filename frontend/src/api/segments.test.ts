import { describe, expect, it } from "vitest";
import type { SegmentEffortDTO, SegmentListItemDTO } from "@/types/segments";
import {
  barWidth, compareDelta, prepareAttempts, statusNote, toEffortRow, toSegmentRow,
} from "./segments";

const seg = (over: Partial<SegmentListItemDTO> = {}): SegmentListItemDTO => ({
  id: 5, name: "Hill", distance_m: 1200, avg_grade: 4.8, best_time_s: 118,
  attempts: 8, pr: true, latest_rank: 1, improvement_s: 4, ...over,
});

describe("statusNote", () => {
  it("shows New PR with improvement when pr", () => {
    expect(statusNote(seg())).toEqual({ text: "New PR · −4s", isPr: true });
  });
  it("shows New PR without improvement when pr and no gap", () => {
    expect(statusNote(seg({ improvement_s: null }))).toEqual({ text: "New PR", isPr: true });
  });
  it("shows the ordinal rank when not a pr", () => {
    expect(statusNote(seg({ pr: false, latest_rank: 2 }))).toEqual({ text: "2nd best", isPr: false });
    expect(statusNote(seg({ pr: false, latest_rank: 3 }))).toEqual({ text: "3rd best", isPr: false });
    expect(statusNote(seg({ pr: false, latest_rank: 11 }))).toEqual({ text: "11th best", isPr: false });
  });
});

describe("toSegmentRow", () => {
  it("formats meta, time and attempts", () => {
    expect(toSegmentRow(seg())).toMatchObject({
      id: 5, name: "Hill", meta: "1.2 km · 4.8% avg",
      bestTime: "1:58", statusText: "New PR · −4s", isPr: true, attemptsLabel: "8×",
    });
  });
});

const eff = (over: Partial<SegmentEffortDTO> = {}): SegmentEffortDTO => ({
  id: 10, activity_id: 2, activity_name: "River loop", start_date: "2026-06-16T07:42:00Z",
  elapsed_time_s: 118, avg_watts: 240, avg_hr: 158, avg_speed_ms: 10.2, is_best: true, ...over,
});

describe("toEffortRow", () => {
  it("formats an effort row", () => {
    expect(toEffortRow(eff())).toMatchObject({
      id: 10, date: "Jun 16", activity: "River loop", time: "1:58",
      power: "240 W", speed: "36.7 km/h", hr: "158 bpm", isBest: true,
    });
  });
  it("uses an em dash for missing power/hr", () => {
    const r = toEffortRow(eff({ avg_watts: null, avg_hr: null }));
    expect(r.power).toBe("—");
    expect(r.hr).toBe("—");
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

describe("prepareAttempts", () => {
  const efforts = [
    eff({ id: 1, activity_name: "River loop", elapsed_time_s: 118, start_date: "2026-06-21T00:00:00Z" }),
    eff({ id: 2, activity_name: "Hill repeats", elapsed_time_s: 130, start_date: "2026-06-10T00:00:00Z" }),
    eff({ id: 3, activity_name: "Club ride", elapsed_time_s: 125, start_date: "2026-06-15T00:00:00Z" }),
  ];
  it("filters by activity name", () => {
    const out = prepareAttempts(efforts, { query: "hill", sortKey: "date", sortDir: "desc", page: 1, pageSize: 10 });
    expect(out.total).toBe(1);
    expect(out.rows[0].activity).toBe("Hill repeats");
  });
  it("sorts by time ascending", () => {
    const out = prepareAttempts(efforts, { query: "", sortKey: "time", sortDir: "asc", page: 1, pageSize: 10 });
    expect(out.rows.map((r) => r.id)).toEqual([1, 3, 2]);
  });
  it("paginates", () => {
    const out = prepareAttempts(efforts, { query: "", sortKey: "time", sortDir: "asc", page: 2, pageSize: 2 });
    expect(out.totalPages).toBe(2);
    expect(out.rows.map((r) => r.id)).toEqual([2]);
  });
});
