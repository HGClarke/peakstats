import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PrimaryStats } from "./PrimaryStats";

describe("PrimaryStats", () => {
  it("renders each tile's label, value, and unit", () => {
    render(<PrimaryStats stats={[
      { label: "DISTANCE", value: "84.3", unit: "km" },
      { label: "AVG POWER", value: "198", unit: "W" },
    ]} />);
    expect(screen.getByText("DISTANCE")).toBeInTheDocument();
    expect(screen.getByText("84.3")).toBeInTheDocument();
    expect(screen.getByText("km")).toBeInTheDocument();
    expect(screen.getByText("198")).toBeInTheDocument();
  });
});
