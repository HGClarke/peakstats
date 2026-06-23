import { screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/providers";
import type { ActivityDetailDTO } from "@/types/activity-detail";

vi.mock("react-router", async () => {
  const actual = await vi.importActual<typeof import("react-router")>("react-router");
  return { ...actual, useNavigate: () => vi.fn(), useParams: () => ({ id: "5" }) };
});
vi.mock("@/api/auth", () => ({ useAthlete: () => ({ data: { id: 9, name: "Ada", avatar_url: null, settings: {} }, error: null }), logout: vi.fn() }));
vi.mock("@/api/sync", () => ({ useSyncStatus: () => ({ data: { status: "idle" } }) }));
vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TileLayer: () => null, Polyline: () => null, CircleMarker: () => null, ZoomControl: () => null, useMap: () => ({ fitBounds: vi.fn() }),
}));
const useActivityDetail = vi.fn();
const useActivityStreams = vi.fn();
vi.mock("@/api/activity-detail", async () => {
  const actual = await vi.importActual<typeof import("@/api/activity-detail")>("@/api/activity-detail");
  return { ...actual, useActivityDetail: (id: number) => useActivityDetail(id), useActivityStreams: (id: number) => useActivityStreams(id) };
});

import ActivityDetailPage from "./ActivityDetailPage";

const detail: ActivityDetailDTO = {
  id: 5, name: "Saturday Gravel Loop", type: "Ride",
  start_date: "2026-06-21T14:42:00Z", start_date_local: "2026-06-21T07:42:00",
  location: null, distance_m: 84300, moving_time_s: 11820, elev_gain_m: 1284,
  avg_speed_ms: 7.13, avg_power_w: 198, normalized_power_w: 221, work_kj: 2342,
  avg_hr: 148, summary_polyline: "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
  power_zones: { unset: true, avg: null, buckets: [] },
  hr_zones: { unset: true, avg: null, buckets: [] },
  climbs: [],
};

beforeEach(() => {
  useActivityDetail.mockReturnValue({ data: detail, isLoading: false, error: null });
  useActivityStreams.mockReturnValue({ data: undefined, isLoading: true });
});
afterEach(() => vi.clearAllMocks());

describe("ActivityDetailPage", () => {
  it("renders the title and primary stats", () => {
    renderWithProviders(<MemoryRouter><ActivityDetailPage /></MemoryRouter>);
    expect(screen.getByText("Saturday Gravel Loop")).toBeInTheDocument();
    expect(screen.getByText("84.3")).toBeInTheDocument();
    expect(screen.getByText("DISTANCE")).toBeInTheDocument();
  });
});
