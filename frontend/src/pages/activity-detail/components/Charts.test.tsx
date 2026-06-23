import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ActivityDetailDTO, ActivityStreamsDTO } from "@/types/activity-detail";

vi.mock("@/app/providers/settings-context", () => ({ useSettings: () => ({ isDark: true, units: "metric" }) }));

import { PowerChart } from "./PowerChart";
import { ElevationChart } from "./ElevationChart";

const detail = { distance_m: 84300, avg_power_w: 198, normalized_power_w: 221 } as ActivityDetailDTO;
const streams: ActivityStreamsDTO = {
  point_count: 3, time: [0, 1, 2], distance: [0, 1000, 2000],
  altitude: [10, 20, 15], watts: [100, 200, 150], heartrate: null, velocity_smooth: null,
};

describe("charts", () => {
  it("PowerChart shows avg + NP legend", () => {
    render(<PowerChart detail={detail} streams={streams} />);
    expect(screen.getByText(/AVG 198 W/)).toBeInTheDocument();
    expect(screen.getByText(/NP 221 W/)).toBeInTheDocument();
  });
  it("PowerChart shows an empty state without watts", () => {
    render(<PowerChart detail={detail} streams={{ ...streams, watts: null }} />);
    expect(screen.getByText(/No power data/i)).toBeInTheDocument();
  });
  it("ElevationChart renders its title", () => {
    render(<ElevationChart detail={detail} streams={streams} />);
    expect(screen.getByText("Elevation profile")).toBeInTheDocument();
  });
});
