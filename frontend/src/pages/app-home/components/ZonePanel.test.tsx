import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import type { ZonesBlockDTO } from "@/types/zones";
import { ZonePanel } from "./ZonePanel";

function renderPanel(block: ZonesBlockDTO, kind: "power" | "hr" = "power") {
  render(
    <MemoryRouter>
      <ZonePanel title="Power zones" caption="THIS WEEK" kind={kind} block={block} />
    </MemoryRouter>,
  );
}

describe("ZonePanel", () => {
  it("renders a row per zone with label, range and percentage", () => {
    renderPanel({
      unset: false, avg: null,
      buckets: [
        { z: "Z1", name: "Active Rec.", range: "< 110 W", seconds: 600, pct: 25 },
        { z: "Z2", name: "Endurance", range: "110–150 W", seconds: 1800, pct: 75 },
      ],
    });
    expect(screen.getByText("Power zones")).toBeInTheDocument();
    expect(screen.getByText("THIS WEEK")).toBeInTheDocument();
    expect(screen.getByText("Z1 · Active Rec.")).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();
  });

  it("shows the FTP prompt when power is unset", () => {
    renderPanel({ unset: true, avg: null, buckets: [] }, "power");
    expect(screen.getByText(/Set your FTP/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /settings/i })).toHaveAttribute("href", "/settings");
  });

  it("shows the Max HR prompt when hr is unset", () => {
    renderPanel({ unset: true, avg: null, buckets: [] }, "hr");
    expect(screen.getByText(/Set your Max HR/i)).toBeInTheDocument();
  });

  it("shows a no-data message when configured but the period has no data", () => {
    renderPanel({
      unset: false, avg: null,
      buckets: [{ z: "Z1", name: "Active Rec.", range: "< 110 W", seconds: 0, pct: 0 }],
    }, "power");
    expect(screen.getByText(/No power data for this period/i)).toBeInTheDocument();
  });
});
