// frontend/src/pages/segments/SegmentsPage.test.tsx
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/providers";
import type { SegmentsQuery } from "@/api/segments";
import type { SegmentListDTO } from "@/types/segments";

const mockNavigate = vi.fn();
vi.mock("react-router", async () => {
  const actual = await vi.importActual<typeof import("react-router")>("react-router");
  return { ...actual, useNavigate: () => mockNavigate };
});

const useAthlete = vi.fn();
vi.mock("@/api/auth", () => ({ useAthlete: () => useAthlete(), logout: vi.fn(), disconnect: vi.fn() }));
const useSyncStatus = vi.fn();
vi.mock("@/api/sync", () => ({ useSyncStatus: () => useSyncStatus() }));
const useSegments = vi.fn();
vi.mock("@/api/segments", async () => {
  const actual = await vi.importActual<typeof import("@/api/segments")>("@/api/segments");
  return { ...actual, useSegments: (q: SegmentsQuery) => useSegments(q) };
});

import SegmentsPage from "./SegmentsPage";

const athlete = { id: 99, name: "Ada Lovelace", avatar_url: null,
  settings: { units: "metric", theme: "dark", default_period: "week" } };
const synced = { status: "idle", progress: 100, synced: 10, last_backfill_at: "T", last_sync_at: "T" };

function dto(over: Partial<SegmentListDTO> = {}): SegmentListDTO {
  return {
    segments: [{ id: 5, name: "Riverside Sprint", distance_m: 1200, avg_grade: 1.2,
      best_time_s: 118, attempts: 8, pr: true, latest_rank: 1, improvement_s: 4,
      recent_times_s: [130, 125, 118] }],
    page: 1, page_size: 10, total: 1, total_pages: 1, as_of: "2026-06-21T12:00:00Z",
    ...over,
  };
}
function lastQuery(): SegmentsQuery { return useSegments.mock.calls.at(-1)![0] as SegmentsQuery; }
function renderPage() { renderWithProviders(<MemoryRouter><SegmentsPage /></MemoryRouter>); }

beforeEach(() => {
  useAthlete.mockReturnValue({ data: athlete, error: null });
  useSyncStatus.mockReturnValue({ data: synced });
  useSegments.mockReturnValue({ data: dto(), isLoading: false });
});
afterEach(() => vi.clearAllMocks());

describe("SegmentsPage", () => {
  it("renders segment rows from the hook", () => {
    renderPage();
    expect(screen.getByText("Riverside Sprint")).toBeInTheDocument();
    expect(screen.getByText("1:58")).toBeInTheDocument();
    expect(screen.getByText("8×")).toBeInTheDocument();
  });

  it("forwards the debounced search query", async () => {
    renderPage();
    fireEvent.change(screen.getByLabelText(/search segments/i), { target: { value: "river" } });
    await waitFor(() => expect(lastQuery().q).toBe("river"));
  });

  it("toggles attempts sort direction", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /attempts/i }));
    expect(lastQuery().direction).toBe("asc");
  });

  it("navigates to the segment on row click", () => {
    renderPage();
    fireEvent.click(screen.getByText("Riverside Sprint"));
    expect(mockNavigate).toHaveBeenCalledWith("/segments/5");
  });

  it("shows the empty state", () => {
    useSegments.mockReturnValue({ data: dto({ segments: [] }), isLoading: false });
    renderPage();
    expect(screen.getByText("No segments match your search.")).toBeInTheDocument();
  });

  it("shows the total segment count in the subtitle", () => {
    useSegments.mockReturnValue({ data: dto({ total: 25, total_pages: 3 }), isLoading: false });
    renderPage();
    expect(screen.getByText("25 SEGMENTS")).toBeInTheDocument();
  });

  it("requests the next page from the pager", () => {
    useSegments.mockReturnValue({ data: dto({ total: 25, total_pages: 3 }), isLoading: false });
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(lastQuery().page).toBe(2);
  });

  it("captures the snapshot from the first response and reuses it", async () => {
    renderPage();
    await waitFor(() => expect(useSegments.mock.calls[0][0]).toMatchObject({ asOf: null }));
    await waitFor(() => expect(lastQuery().asOf).toBe("2026-06-21T12:00:00Z"));
  });

  it("resets to page 1 when the sort toggles", () => {
    useSegments.mockReturnValue({ data: dto({ total: 25, total_pages: 3 }), isLoading: false });
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(lastQuery().page).toBe(2);
    fireEvent.click(screen.getByRole("button", { name: /attempts/i }));
    expect(lastQuery().page).toBe(1);
  });
});
