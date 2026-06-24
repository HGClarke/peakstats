import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/providers";

const mockNavigate = vi.fn();
vi.mock("react-router", async () => {
  const actual = await vi.importActual<typeof import("react-router")>("react-router");
  return { ...actual, useNavigate: () => mockNavigate };
});

const useAthlete = vi.fn();
vi.mock("@/api/auth", () => ({
  useAthlete: () => useAthlete(),
  logout: vi.fn(),
  disconnect: vi.fn(),
}));

const useSyncStatus = vi.fn();
vi.mock("@/api/sync", () => ({
  useSyncStatus: () => useSyncStatus(),
}));

const useOverview = vi.fn();
vi.mock("@/api/overview", () => ({
  useOverview: () => useOverview(),
}));

vi.mock("react-activity-calendar", () => ({
  ActivityCalendar: () => <div data-testid="calendar" />,
}));

import { disconnect, logout } from "@/api/auth";
import type { DashboardOverview } from "@/types/overview";
import AppHome from "./AppHome";

const overview: DashboardOverview = {
  period: "week",
  headline: {
    label: "DISTANCE",
    periodLabel: "THIS WEEK",
    value: "30.0",
    unit: "km",
    delta: "+20%",
    deltaPositive: true,
    deltaCaption: "vs last week",
  },
  secondary: [
    { label: "MOVING TIME", value: "6h 12m", unit: "", delta: "+12%", deltaPositive: true },
    { label: "ELEVATION", value: "1,240", unit: "m", delta: "+3%", deltaPositive: true },
    { label: "AVG SPEED", value: "24.8", unit: "km/h", delta: "+15%", deltaPositive: true },
  ],
  trend: [{ label: "Mon", value: 14.8 }],
  trendUnit: "km",
  summary: {
    rides: "12",
    prs: "2",
    topSpeed: "42.0 km/h",
    topAvgPower: "287 W",
    longestRide: "64.0 km",
    maxElev: "980 m",
  },
  rideTypes: {
    total: 12,
    items: [
      { type: "Ride", label: "Ride", pct: "100%", fraction: 1, color: "var(--color-strava)" },
    ],
  },
  recentRides: [
    {
      id: 1,
      name: "River loop",
      meta: "Tue · Jun 16 · Ride",
      distLabel: "38.7 km",
      durLabel: "1h 34m",
      isPr: false,
      dotColor: "var(--color-strava)",
    },
  ],
  heatmap: {
    year: 2026,
    activeDays: 3,
    data: [
      { date: "2026-01-01", count: 0, level: 0 },
      { date: "2026-06-16", count: 38700, level: 3 },
      { date: "2026-12-31", count: 0, level: 0 },
    ],
  },
  goal: {
    pct: 64, pctLabel: "64%", doneLabel: "64.0",
    targetLabel: "100.0", unit: "km", remainingLabel: "36.0",
  },
  powerZones: {
    unset: false, avg: 210,
    buckets: [{ z: "Z1", name: "Active Rec.", range: "< 110 W", seconds: 600, pct: 100 }],
  },
  hrZones: { unset: true, avg: null, buckets: [] },
};

const syncedStatus = {
  status: "idle", progress: 100, synced: 200,
  last_backfill_at: "T", last_sync_at: "T",
};

const athlete = {
  id: 99, name: "Ada Lovelace", avatar_url: null,
  settings: { units: "metric", theme: "dark", default_period: "week" },
};

function renderPage() {
  renderWithProviders(<MemoryRouter><AppHome /></MemoryRouter>);
}

beforeEach(() => {
  useOverview.mockReturnValue({ data: overview, isLoading: false, error: null });
});
afterEach(() => vi.clearAllMocks());

describe("AppHome", () => {
  it("shows the athlete name once synced", () => {
    useAthlete.mockReturnValue({ data: athlete, isLoading: false, error: null });
    useSyncStatus.mockReturnValue({ data: { status: "idle", progress: 100, synced: 200,
      last_backfill_at: "T", last_sync_at: "T" } });
    renderPage();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
  });

  it("redirects to /sync when never synced", async () => {
    useAthlete.mockReturnValue({ data: athlete, isLoading: false, error: null });
    useSyncStatus.mockReturnValue({ data: { status: "never_synced", progress: 0, synced: 0,
      last_backfill_at: null, last_sync_at: null } });
    renderPage();
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/sync", { replace: true }));
  });

  it("redirects to landing when unauthenticated", async () => {
    useAthlete.mockReturnValue({ data: null, isLoading: false, error: new Error("401") });
    useSyncStatus.mockReturnValue({ data: undefined });
    renderPage();
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true }));
  });

  it("logs out from the sidebar", async () => {
    (logout as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    useAthlete.mockReturnValue({ data: athlete, isLoading: false, error: null });
    useSyncStatus.mockReturnValue({ data: { status: "idle", progress: 100, synced: 200,
      last_backfill_at: "T", last_sync_at: "T" } });
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /log out/i }));
    await waitFor(() => expect(logout).toHaveBeenCalled());
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true }));
  });

  it("disconnects from the overview", async () => {
    (disconnect as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    useAthlete.mockReturnValue({ data: athlete, isLoading: false, error: null });
    useSyncStatus.mockReturnValue({ data: { status: "idle", progress: 100, synced: 200,
      last_backfill_at: "T", last_sync_at: "T" } });
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /disconnect/i }));
    await waitFor(() => expect(disconnect).toHaveBeenCalled());
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true }));
  });
});

describe("AppHome overview", () => {
  it("renders the headline, secondary KPIs, summary, and recent rides when loaded", () => {
    useAthlete.mockReturnValue({ data: athlete, isLoading: false, error: null });
    useSyncStatus.mockReturnValue({ data: syncedStatus });
    renderPage();
    expect(screen.getByText("DISTANCE · THIS WEEK")).toBeInTheDocument();
    expect(screen.getByText("MOVING TIME")).toBeInTheDocument();
    expect(screen.getByText("RIDES")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Week" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Refresh from Strava/ })).toBeNull();
    expect(screen.getByText("River loop")).toBeInTheDocument();
    expect(screen.getByText("Weekly goal")).toBeInTheDocument();
    expect(screen.getByText("2026 · 3 ACTIVE DAYS")).toBeInTheDocument();
    expect(screen.getByText("Power zones")).toBeInTheDocument();
    expect(screen.getByText("Heart-rate zones")).toBeInTheDocument();
  });

  it("shows skeletons while the overview is loading", () => {
    useAthlete.mockReturnValue({ data: athlete, isLoading: false, error: null });
    useSyncStatus.mockReturnValue({ data: syncedStatus });
    useOverview.mockReturnValue({ data: undefined, isLoading: true, error: null });
    renderPage();
    expect(screen.queryByText("DISTANCE · THIS WEEK")).not.toBeInTheDocument();
    expect(screen.getByLabelText(/loading overview/i)).toBeInTheDocument();
  });
});
