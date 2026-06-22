// frontend/src/pages/segments/SegmentDetailPage.test.tsx
import { fireEvent, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/providers";
import type { SegmentDetailDTO } from "@/types/segments";

const mockNavigate = vi.fn();
vi.mock("react-router", async () => {
  const actual = await vi.importActual<typeof import("react-router")>("react-router");
  return { ...actual, useNavigate: () => mockNavigate, useParams: () => ({ id: "5" }) };
});
const useAthlete = vi.fn();
vi.mock("@/api/auth", () => ({ useAthlete: () => useAthlete(), logout: vi.fn(), disconnect: vi.fn() }));
const useSyncStatus = vi.fn();
vi.mock("@/api/sync", () => ({ useSyncStatus: () => useSyncStatus() }));
const useSegment = vi.fn();
vi.mock("@/api/segments", async () => {
  const actual = await vi.importActual<typeof import("@/api/segments")>("@/api/segments");
  return { ...actual, useSegment: (id: number) => useSegment(id) };
});

import SegmentDetailPage from "./SegmentDetailPage";

const detail: SegmentDetailDTO = {
  id: 5, name: "Riverside Sprint", distance_m: 1200, avg_grade: 1.2, pr_time_s: 118, attempts: 3,
  efforts: [
    { id: 1, activity_id: 2, activity_name: "River loop", start_date: "2026-06-21T08:00:00Z",
      elapsed_time_s: 118, avg_watts: 240, avg_hr: 158, avg_speed_ms: 10.2, is_best: true },
    { id: 2, activity_id: 3, activity_name: "Hill repeats", start_date: "2026-06-10T08:00:00Z",
      elapsed_time_s: 132, avg_watts: null, avg_hr: null, avg_speed_ms: 9.1, is_best: false },
  ],
};
const athlete = { id: 99, name: "Ada", avatar_url: null,
  settings: { units: "metric", theme: "dark", default_period: "week" } };

function renderPage() { renderWithProviders(<MemoryRouter><SegmentDetailPage /></MemoryRouter>); }

beforeEach(() => {
  useAthlete.mockReturnValue({ data: athlete, error: null });
  useSyncStatus.mockReturnValue({ data: { status: "idle" } });
  useSegment.mockReturnValue({ data: detail, isLoading: false });
});
afterEach(() => vi.clearAllMocks());

describe("SegmentDetailPage", () => {
  it("shows meta cards and the PR time", () => {
    renderPage();
    expect(screen.getByText("Riverside Sprint")).toBeInTheDocument();
    expect(screen.getAllByText("1:58").length).toBeGreaterThan(0);  // PR time + best card
    expect(screen.getByText("1.2 km")).toBeInTheDocument();
  });

  it("defaults the compare to the most recent non-best attempt and shows the delta", () => {
    renderPage();
    expect(screen.getByText("+14 slower")).toBeInTheDocument();  // 132 vs 118
  });

  it("lists attempts with PR tag and em-dash for missing power", () => {
    renderPage();
    expect(screen.getByText("PR")).toBeInTheDocument();
    expect(screen.getByText("Hill repeats")).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("selecting the best attempt row updates the compare to Personal best", () => {
    renderPage();
    fireEvent.click(screen.getByText("River loop"));
    expect(screen.getAllByText("Personal best").length).toBeGreaterThan(0);
  });
});
