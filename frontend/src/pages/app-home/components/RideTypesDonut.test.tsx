import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RideTypesDonut, donutSegments } from "./RideTypesDonut";

const DATA = {
  total: 5,
  items: [
    { type: "Ride", label: "Ride", pct: "80%", fraction: 0.8, color: "var(--color-strava)" },
    { type: "VirtualRide", label: "VirtualRide", pct: "20%", fraction: 0.2, color: "var(--color-cat-2)" },
  ],
};

describe("donutSegments", () => {
  it("produces cumulative dash offsets that don't overlap", () => {
    const segs = donutSegments(DATA.items);
    expect(segs).toHaveLength(2);
    expect(segs[0].dashOffset).toBe(0);
    // second segment starts where the first ends (negative offset = clockwise)
    expect(segs[1].dashOffset).toBeCloseTo(-0.8 * segs[0].circumference, 3);
  });
});

describe("RideTypesDonut", () => {
  it("renders the legend with labels and percentages", () => {
    render(<RideTypesDonut data={DATA} />);
    expect(screen.getByText("Ride")).toBeInTheDocument();
    expect(screen.getByText("80%")).toBeInTheDocument();
    expect(screen.getByText("5 TOTAL")).toBeInTheDocument();
  });
});
