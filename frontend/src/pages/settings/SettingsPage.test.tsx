import { screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createMemoryRouter, RouterProvider } from "react-router";
import { renderWithProviders } from "@/test/providers";
import { useAthlete, disconnect } from "@/api/auth";
import { patchSettings } from "@/api/settings";
import SettingsPage from "./SettingsPage";

vi.mock("@/api/auth", async (orig) => ({
  ...(await orig<typeof import("@/api/auth")>()),
  useAthlete: vi.fn(),
  disconnect: vi.fn(),
}));
vi.mock("@/api/settings", () => ({ patchSettings: vi.fn() }));
vi.mock("@/api/sync", () => ({ useSyncStatus: () => ({ data: { status: "idle" } }) }));

beforeEach(() => {
  (useAthlete as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
    data: { id: 7, name: "Ada", avatar_url: null, settings: { units: "metric", theme: "dark", default_period: "week" } },
    isLoading: false, error: null,
  });
  (patchSettings as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({});
  (disconnect as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
});
afterEach(() => vi.clearAllMocks());

function renderPage() {
  const router = createMemoryRouter(
    [{ path: "/settings", element: <SettingsPage /> }, { path: "/", element: <div>landing</div> }],
    { initialEntries: ["/settings"] },
  );
  return renderWithProviders(<RouterProvider router={router} />);
}

it("toggling units persists via PATCH", async () => {
  renderPage();
  fireEvent.click(screen.getByRole("button", { name: "Imperial" }));
  await waitFor(() => expect(patchSettings).toHaveBeenCalledWith({ units: "imperial" }));
});

it("disconnect confirms then deletes and redirects", async () => {
  renderPage();
  fireEvent.click(screen.getByRole("button", { name: "Disconnect" }));
  fireEvent.click(screen.getByRole("button", { name: "Yes, disconnect" }));
  await waitFor(() => expect(disconnect).toHaveBeenCalled());
  await waitFor(() => expect(screen.getByText("landing")).toBeInTheDocument());
});

it("typing into FTP watts and blurring calls patchSettings with ftp_w", async () => {
  renderPage();
  const input = screen.getByRole("spinbutton", { name: "FTP watts" });
  fireEvent.change(input, { target: { value: "280" } });
  fireEvent.blur(input);
  await waitFor(() => expect(patchSettings).toHaveBeenCalledWith({ ftp_w: 280 }));
});
