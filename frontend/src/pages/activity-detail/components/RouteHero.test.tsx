import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ActivityDetailDTO } from "@/types/activity-detail";

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="map">{children}</div>,
  TileLayer: ({ url }: { url: string }) => <div data-testid="tiles" data-url={url} />,
  Polyline: () => <div data-testid="route" />,
  CircleMarker: () => <div data-testid="marker" />,
  useMap: () => ({ fitBounds: vi.fn() }),
}));
vi.mock("@/app/providers/settings-context", () => ({ useSettings: () => ({ isDark: true }) }));

import RouteHero from "./RouteHero";

const detail: ActivityDetailDTO = {
  id: 5, name: "Saturday Gravel Loop", type: "Ride",
  start_date: "2026-06-21T14:42:00Z", start_date_local: "2026-06-21T07:42:00",
  location: "Marin Headlands", distance_m: 84300, moving_time_s: 11820, elev_gain_m: 1284,
  avg_speed_ms: 7.13, avg_power_w: 198, normalized_power_w: 221, work_kj: 2342,
  avg_hr: 148, summary_polyline: "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
  power_zones: { unset: true, avg: null, buckets: [] },
  hr_zones: { unset: true, avg: null, buckets: [] },
  climbs: [],
};

describe("RouteHero", () => {
  it("renders the dark tiles, route, and caption", () => {
    render(<RouteHero detail={detail} />);
    expect(screen.getByTestId("tiles").getAttribute("data-url")).toContain("dark_all");
    expect(screen.getByTestId("route")).toBeInTheDocument();
    expect(screen.getByText("Saturday Gravel Loop")).toBeInTheDocument();
    // CSS uppercase doesn't change textContent in jsdom — assert raw value "Ride"
    expect(screen.getByText("Ride")).toBeInTheDocument();
  });

  it("shows the caption over a panel when there is no polyline", () => {
    render(<RouteHero detail={{ ...detail, summary_polyline: null }} />);
    expect(screen.queryByTestId("map")).not.toBeInTheDocument();
    expect(screen.getByText("Saturday Gravel Loop")).toBeInTheDocument();
  });
});
