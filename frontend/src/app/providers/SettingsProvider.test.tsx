import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAthlete } from "@/api/auth";
import { patchSettings } from "@/api/settings";
import { SettingsProvider } from "./SettingsProvider";
import { useSettings } from "./settings-context";

vi.mock("@/api/auth", () => ({ useAthlete: vi.fn() }));
vi.mock("@/api/settings", () => ({ patchSettings: vi.fn() }));

const mockAthlete = (settings: Record<string, string>) =>
  (useAthlete as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
    data: { id: 7, name: "Ada", avatar_url: null, settings },
    isLoading: false, error: null,
  });

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function renderWithClient(
  ui: React.ReactElement,
  queryClient = makeQueryClient(),
) {
  const result = render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
  return { ...result, queryClient };
}

beforeEach(() => {
  document.documentElement.classList.remove("dark", "light");
  localStorage.clear();
  (patchSettings as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({});
  mockAthlete({ units: "metric", theme: "dark", default_period: "week" });
});
afterEach(() => vi.clearAllMocks());

function Probe() {
  const { units, theme, setUnits, toggleTheme } = useSettings();
  return (
    <div>
      <span data-testid="units">{units}</span>
      <span data-testid="theme">{theme}</span>
      <button onClick={() => setUnits("imperial")}>imperial</button>
      <button onClick={toggleTheme}>toggle</button>
    </div>
  );
}

it("hydrates units + theme from the athlete record", async () => {
  mockAthlete({ units: "imperial", theme: "light", default_period: "week" });
  renderWithClient(<SettingsProvider><Probe /></SettingsProvider>);
  await waitFor(() => expect(screen.getByTestId("units")).toHaveTextContent("imperial"));
  expect(screen.getByTestId("theme")).toHaveTextContent("light");
});

it("setUnits optimistically updates and PATCHes", async () => {
  renderWithClient(<SettingsProvider><Probe /></SettingsProvider>);
  fireEvent.click(screen.getByText("imperial"));
  expect(screen.getByTestId("units")).toHaveTextContent("imperial");
  await waitFor(() =>
    expect(patchSettings).toHaveBeenCalledWith({ units: "imperial" }));
});

it("reverts units when the PATCH fails", async () => {
  (patchSettings as unknown as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("nope"));
  renderWithClient(<SettingsProvider><Probe /></SettingsProvider>);
  fireEvent.click(screen.getByText("imperial"));
  await waitFor(() => expect(screen.getByTestId("units")).toHaveTextContent("metric"));
});

it("toggleTheme flips the dark class and mirrors to localStorage", async () => {
  renderWithClient(<SettingsProvider><Probe /></SettingsProvider>);
  fireEvent.click(screen.getByText("toggle"));
  expect(document.documentElement.classList.contains("dark")).toBe(false);
  expect(localStorage.getItem("peakstats-theme")).toBe("light");
  await waitFor(() => expect(patchSettings).toHaveBeenCalledWith({ theme: "light" }));
});

it("after a failed PATCH with no prior override, clears override so subsequent server value is reflected", async () => {
  (patchSettings as unknown as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("nope"));
  const queryClient = makeQueryClient();
  const { rerender } = render(
    <QueryClientProvider client={queryClient}>
      <SettingsProvider><Probe /></SettingsProvider>
    </QueryClientProvider>
  );

  // Optimistically set imperial; PATCH fails; should revert to server metric
  fireEvent.click(screen.getByText("imperial"));
  await waitFor(() => expect(screen.getByTestId("units")).toHaveTextContent("metric"));

  // Now server returns imperial — override must be null so the new value shows
  mockAthlete({ units: "imperial", theme: "dark", default_period: "week" });
  (patchSettings as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({});
  await act(async () => {
    rerender(
      <QueryClientProvider client={queryClient}>
        <SettingsProvider><Probe /></SettingsProvider>
      </QueryClientProvider>
    );
  });
  await waitFor(() => expect(screen.getByTestId("units")).toHaveTextContent("imperial"));
});

it("on PATCH success, writes the response into the ['athlete'] query cache", async () => {
  const patchResponse = {
    id: 7, name: "Ada", avatar_url: null,
    settings: { units: "imperial", theme: "dark", default_period: "week" },
  };
  (patchSettings as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(patchResponse);
  const queryClient = makeQueryClient();
  renderWithClient(<SettingsProvider><Probe /></SettingsProvider>, queryClient);

  fireEvent.click(screen.getByText("imperial"));
  await waitFor(() => expect(patchSettings).toHaveBeenCalledWith({ units: "imperial" }));
  await waitFor(() =>
    expect(queryClient.getQueryData(["athlete"])).toEqual(patchResponse)
  );
});
