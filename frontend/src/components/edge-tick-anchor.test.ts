import { describe, it, expect } from "vitest";
import { edgeTickAnchor } from "./edge-tick-anchor";

describe("edgeTickAnchor", () => {
  it("anchors the first tick to the start so it doesn't clip off the left edge", () => {
    expect(edgeTickAnchor(0, 7)).toBe("start");
  });

  it("anchors the last tick to the end so it doesn't clip off the right edge", () => {
    expect(edgeTickAnchor(6, 7)).toBe("end");
  });

  it("centers interior ticks", () => {
    expect(edgeTickAnchor(1, 7)).toBe("middle");
    expect(edgeTickAnchor(3, 7)).toBe("middle");
  });

  it("anchors a lone tick to the start", () => {
    expect(edgeTickAnchor(0, 1)).toBe("start");
  });
});
