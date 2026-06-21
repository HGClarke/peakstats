import { describe, expect, it } from "vitest";
import { fmtDate, fmtDuration } from "./format";

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
