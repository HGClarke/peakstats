import { describe, expect, it } from "vitest";
import { boundsOf, decodePolyline } from "./polyline";

describe("decodePolyline", () => {
  it("decodes the canonical Google example", () => {
    // "_p~iF~ps|U_ulLnnqC_mqNvxq`@" -> known reference points
    const pts = decodePolyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@");
    expect(pts.length).toBe(3);
    expect(pts[0][0]).toBeCloseTo(38.5, 5);
    expect(pts[0][1]).toBeCloseTo(-120.2, 5);
    expect(pts[1][0]).toBeCloseTo(40.7, 5);
    expect(pts[2][1]).toBeCloseTo(-126.453, 3);
  });
  it("returns [] for empty input", () => {
    expect(decodePolyline("")).toEqual([]);
  });
});

describe("boundsOf", () => {
  it("computes the bounding box", () => {
    expect(boundsOf([[1, 2], [3, -1], [-2, 5]])).toEqual({
      south: -2, west: -1, north: 3, east: 5,
    });
  });
  it("returns null for no points", () => {
    expect(boundsOf([])).toBeNull();
  });
});
