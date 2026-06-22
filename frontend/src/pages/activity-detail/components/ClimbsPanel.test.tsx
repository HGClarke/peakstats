import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ClimbsPanel } from "./ClimbsPanel";

describe("ClimbsPanel", () => {
  it("renders climb rows", () => {
    render(<ClimbsPanel climbs={[{ name: "Marincello", climb_category: 2, distance_m: 4300,
      avg_grade: 7.2, elev_gain_m: 310, time_s: 1089, vam: 1025 }]} units="metric" />);
    expect(screen.getByText("Marincello")).toBeInTheDocument();
    expect(screen.getByText("CAT 3")).toBeInTheDocument();
    expect(screen.getByText("18:09")).toBeInTheDocument();
  });
  it("renders empty state when no climbs", () => {
    render(<ClimbsPanel climbs={[]} units="metric" />);
    expect(screen.getByText(/No categorized climbs/i)).toBeInTheDocument();
  });
});
