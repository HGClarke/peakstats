import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
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

const refreshMutate = vi.fn();
const useSyncStatus = vi.fn();
vi.mock("@/api/sync", () => ({
  useSyncStatus: () => useSyncStatus(),
  useRefreshSync: () => ({ mutate: refreshMutate, isPending: false }),
}));

import { disconnect, logout } from "@/api/auth";
import AppHome from "./AppHome";

const athlete = {
  id: 99, name: "Ada Lovelace", avatar_url: null,
  settings: { units: "metric", theme: "dark", default_period: "week" },
};

function renderPage() {
  renderWithProviders(<MemoryRouter><AppHome /></MemoryRouter>);
}

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

describe("AppHome refresh", () => {
  it("refreshes from Strava", () => {
    useAthlete.mockReturnValue({ data: athlete, isLoading: false, error: null });
    useSyncStatus.mockReturnValue({ data: { status: "idle", progress: 100, synced: 200,
      last_backfill_at: "T", last_sync_at: "T" } });
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /refresh from strava/i }));
    expect(refreshMutate).toHaveBeenCalled();
  });
});
