import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { ZonesPanel } from "./ZonesPanel";

describe("ZonesPanel", () => {
  it("renders zone rows when set", () => {
    render(<MemoryRouter><ZonesPanel title="Power zones" meta="TIME IN ZONE" block={{
      unset: false, avg: 150, buckets: [
        { z: "Z2", name: "Endurance", range: "154–210 W", seconds: 1200, pct: 40 },
      ],
    }} /></MemoryRouter>);
    expect(screen.getByText("Power zones")).toBeInTheDocument();
    expect(screen.getByText(/Z2 · Endurance/)).toBeInTheDocument();
    expect(screen.getByText("20m")).toBeInTheDocument();
  });

  it("renders an unset prompt linking to settings", () => {
    render(<MemoryRouter><ZonesPanel title="Power zones" meta="" block={{ unset: true, avg: null, buckets: [] }} /></MemoryRouter>);
    const link = screen.getByRole("link", { name: /settings/i });
    expect(link).toHaveAttribute("href", "/settings");
  });
});
