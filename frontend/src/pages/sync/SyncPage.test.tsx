import { fireEvent, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/providers";

const mockNavigate = vi.fn();
vi.mock("react-router", async () => {
  const actual = await vi.importActual<typeof import("react-router")>("react-router");
  return { ...actual, useNavigate: () => mockNavigate };
});

const startMutate = vi.fn();
const useSyncStatus = vi.fn();
vi.mock("@/api/sync", () => ({
  useSyncStatus: () => useSyncStatus(),
  useStartSync: () => ({ mutate: startMutate }),
}));

vi.mock("@/api/auth", () => ({
  useAthlete: () => ({ data: { id: 1, name: "Ada", avatar_url: null,
    settings: { units: "metric", theme: "dark", default_period: "week" } },
    isLoading: false, error: null }),
  logout: vi.fn(),
}));

import SyncPage from "./SyncPage";

function renderPage() {
  renderWithProviders(<MemoryRouter><SyncPage /></MemoryRouter>);
}

afterEach(() => vi.clearAllMocks());

describe("SyncPage", () => {
  it("starts the backfill on mount", () => {
    useSyncStatus.mockReturnValue({ data: { status: "never_synced", progress: 0, synced: 0,
      last_backfill_at: null, last_sync_at: null } });
    renderPage();
    expect(startMutate).toHaveBeenCalled();
  });

  it("shows progress while backfilling", () => {
    useSyncStatus.mockReturnValue({ data: { status: "backfilling", progress: 40, synced: 88,
      last_backfill_at: null, last_sync_at: null } });
    renderPage();
    expect(screen.getByText("40")).toBeInTheDocument();
    expect(screen.getByText(/importing your rides/i)).toBeInTheDocument();
  });

  it("shows Go to dashboard when done and navigates home", () => {
    useSyncStatus.mockReturnValue({ data: { status: "idle", progress: 100, synced: 218,
      last_backfill_at: "T", last_sync_at: "T" } });
    renderPage();
    const cta = screen.getByRole("button", { name: /go to dashboard/i });
    fireEvent.click(cta);
    expect(mockNavigate).toHaveBeenCalledWith("/home");
  });

  it("shows the empty state when no rides were found", () => {
    useSyncStatus.mockReturnValue({ data: { status: "idle", progress: 100, synced: 0,
      last_backfill_at: "T", last_sync_at: "T" } });
    renderPage();
    expect(screen.getByText(/no rides found/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /refresh from strava/i })).toBeInTheDocument();
  });
});
