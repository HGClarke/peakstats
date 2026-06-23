import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ActivityHeatmap } from "./ActivityHeatmap";

vi.mock("react-activity-calendar", () => ({
  ActivityCalendar: (props: { data: unknown[] }) => (
    <div data-testid="calendar" data-len={props.data.length} />
  ),
}));

const view = {
  year: 2026,
  activeDays: 3,
  data: [
    { date: "2026-01-01", count: 0, level: 0 },
    { date: "2026-03-10", count: 12000, level: 2 },
    { date: "2026-12-31", count: 0, level: 0 },
  ],
};

describe("ActivityHeatmap", () => {
  it("renders the active-days header and passes data to the calendar", () => {
    render(<ActivityHeatmap view={view} isDark units="metric" />);
    expect(screen.getByText("2026 · 3 ACTIVE DAYS")).toBeInTheDocument();
    expect(screen.getByTestId("calendar")).toHaveAttribute("data-len", "3");
  });
});
