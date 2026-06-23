import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WeeklyGoalRing } from "./WeeklyGoalRing";

const goal = {
  pct: 64, pctLabel: "64%", doneLabel: "64.0",
  targetLabel: "100.0", unit: "km", remainingLabel: "36.0",
};

describe("WeeklyGoalRing", () => {
  it("renders the percentage, progress, and remaining", () => {
    render(<WeeklyGoalRing goal={goal} />);
    expect(screen.getByText("64%")).toBeInTheDocument();
    expect(screen.getByText("64.0")).toBeInTheDocument();
    expect(screen.getByText("/ 100.0 km")).toBeInTheDocument();
    expect(screen.getByText("36.0 km to go")).toBeInTheDocument();
  });
});
