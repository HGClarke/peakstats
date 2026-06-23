import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PeriodSelector } from "./PeriodSelector";

describe("PeriodSelector", () => {
  it("renders the three periods and marks the active one", () => {
    render(<PeriodSelector value="month" onChange={() => {}} />);
    const active = screen.getByRole("button", { name: "Month" });
    expect(active).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Week" })).toHaveAttribute("aria-pressed", "false");
  });

  it("calls onChange with the chosen period", () => {
    const onChange = vi.fn();
    render(<PeriodSelector value="week" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Year" }));
    expect(onChange).toHaveBeenCalledWith("year");
  });
});
