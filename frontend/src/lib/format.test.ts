import { describe, expect, it } from "vitest";
import { fmtClock, fmtDate, fmtDuration } from "./format";

describe("fmtDuration", () => {
  it("formats hours with zero-padded minutes", () => {
    expect(fmtDuration(5662)).toBe("1h 34m");
    expect(fmtDuration(22320)).toBe("6h 12m");
  });
  it("pads single-digit minutes after an hour", () => {
    expect(fmtDuration(3660)).toBe("1h 01m");
  });
  it("omits the hour under an hour", () => {
    expect(fmtDuration(600)).toBe("10m");
  });
});

describe("fmtDate", () => {
  it("formats weekday, month and day in UTC", () => {
    expect(fmtDate("2026-06-16T07:42:00Z")).toBe("Tue · Jun 16");
  });
});

describe("fmtClock", () => {
  it("formats sub-minute and minute times as m:ss", () => {
    expect(fmtClock(118)).toBe("1:58");
    expect(fmtClock(706)).toBe("11:46");
    expect(fmtClock(9)).toBe("0:09");
  });
  it("formats hour-plus times as h:mm:ss", () => {
    expect(fmtClock(3661)).toBe("1:01:01");
    expect(fmtClock(3600)).toBe("1:00:00");
  });
  it("rounds fractional seconds", () => {
    expect(fmtClock(118.6)).toBe("1:59");
  });
});
