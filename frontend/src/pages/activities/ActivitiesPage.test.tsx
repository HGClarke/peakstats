import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/providers";
import type { ActivitiesQuery } from "@/api/activities";
import type { ActivityListDTO } from "@/types/activities";

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
vi.mock("@/api/sync", () => ({ useSyncStatus: () => useSyncStatus() }));

const useActivities = vi.fn();
vi.mock("@/api/activities", async () => {
  const actual = await vi.importActual<typeof import("@/api/activities")>("@/api/activities");
  return { ...actual, useActivities: (query: ActivitiesQuery) => useActivities(query) };
});

import ActivitiesPage from "./ActivitiesPage";

const athlete = {
  id: 99, name: "Ada Lovelace", avatar_url: null,
  settings: { units: "metric", theme: "dark", default_period: "week" },
};
const synced = { status: "idle", progress: 100, synced: 200,
  last_backfill_at: "T", last_sync_at: "T" };

function dto(over: Partial<ActivityListDTO> = {}): ActivityListDTO {
  return {
    activities: [{
      id: 1, name: "River loop", type: "Ride", start_date: "2026-06-16T07:42:00Z",
      distance_m: 38700, moving_time_s: 5662, elev_gain_m: 1240, avg_speed_ms: 6.889,
    }],
    page: 1, page_size: 9, total: 1, total_pages: 1, as_of: "2026-06-21T12:00:00Z",
    ...over,
  };
}

function lastQuery(): ActivitiesQuery {
  return useActivities.mock.calls.at(-1)![0] as ActivitiesQuery;
}

function renderPage() {
  renderWithProviders(<MemoryRouter><ActivitiesPage /></MemoryRouter>);
}

beforeEach(() => {
  useAthlete.mockReturnValue({ data: athlete, isLoading: false, error: null });
  useSyncStatus.mockReturnValue({ data: synced });
  useActivities.mockReturnValue({ data: dto(), isLoading: false });
});
afterEach(() => vi.clearAllMocks());

describe("ActivitiesPage", () => {
  it("renders rows from the hook", () => {
    renderPage();
    expect(screen.getByText("River loop")).toBeInTheDocument();
    expect(screen.getByText("38.7 km")).toBeInTheDocument();
  });

  it("shows the skeleton while loading the first page", () => {
    useActivities.mockReturnValue({ data: undefined, isLoading: true });
    renderPage();
    expect(screen.getByLabelText(/loading activities/i)).toBeInTheDocument();
    expect(screen.queryByText("River loop")).not.toBeInTheDocument();
  });

  it("shows the no-rides empty state", () => {
    useActivities.mockReturnValue({ data: dto({ activities: [], total: 0 }), isLoading: false });
    renderPage();
    expect(screen.getByText("No activities yet.")).toBeInTheDocument();
  });

  it("shows the no-match empty state when a filter is set", () => {
    useActivities.mockReturnValue({ data: dto({ activities: [], total: 0 }), isLoading: false });
    renderPage();
    fireEvent.change(screen.getByLabelText(/search activities/i), { target: { value: "zzz" } });
    expect(screen.getByText("No activities match your filters.")).toBeInTheDocument();
  });

  it("toggles sort field and direction via headers", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /distance/i }));
    expect(lastQuery()).toMatchObject({ sort: "distance", direction: "desc" });
    fireEvent.click(screen.getByRole("button", { name: /distance/i }));
    expect(lastQuery()).toMatchObject({ sort: "distance", direction: "asc" });
  });

  it("requests the next page from the pager", () => {
    useActivities.mockReturnValue({ data: dto({ total: 20, total_pages: 3 }), isLoading: false });
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(lastQuery()).toMatchObject({ page: 2 });
  });

  it("captures the snapshot from the first response and reuses it", async () => {
    renderPage();
    await waitFor(() =>
      expect(lastQuery()).toMatchObject({ asOf: "2026-06-21T12:00:00Z" }));
  });

  it("redirects to /sync when never synced", async () => {
    useSyncStatus.mockReturnValue({ data: { status: "never_synced", progress: 0, synced: 0,
      last_backfill_at: null, last_sync_at: null } });
    renderPage();
    await waitFor(() =>
      expect(mockNavigate).toHaveBeenCalledWith("/sync", { replace: true }));
  });
});
