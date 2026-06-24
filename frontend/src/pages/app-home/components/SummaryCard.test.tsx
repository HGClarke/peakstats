import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SummaryView } from "@/types/overview";
import { SummaryCard } from "./SummaryCard";

const summary: SummaryView = {
  rides: "12", prs: "2", topSpeed: "42.0 km/h", topAvgPower: "287 W",
  longestRide: "64.0 km", maxElev: "980 m",
};

describe("SummaryCard", () => {
  it("renders the Top avg power stat", () => {
    render(<SummaryCard summary={summary} />);
    expect(screen.getByText("TOP AVG POWER")).toBeInTheDocument();
    expect(screen.getByText("287 W")).toBeInTheDocument();
  });
});
