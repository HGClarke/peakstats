import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
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
  render(<SettingsProvider><Probe /></SettingsProvider>);
  await waitFor(() => expect(screen.getByTestId("units")).toHaveTextContent("imperial"));
  expect(screen.getByTestId("theme")).toHaveTextContent("light");
});

it("setUnits optimistically updates and PATCHes", async () => {
  render(<SettingsProvider><Probe /></SettingsProvider>);
  fireEvent.click(screen.getByText("imperial"));
  expect(screen.getByTestId("units")).toHaveTextContent("imperial");
  await waitFor(() =>
    expect(patchSettings).toHaveBeenCalledWith({ units: "imperial" }));
});

it("reverts units when the PATCH fails", async () => {
  (patchSettings as unknown as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("nope"));
  render(<SettingsProvider><Probe /></SettingsProvider>);
  fireEvent.click(screen.getByText("imperial"));
  await waitFor(() => expect(screen.getByTestId("units")).toHaveTextContent("metric"));
});

it("toggleTheme flips the dark class and mirrors to localStorage", async () => {
  render(<SettingsProvider><Probe /></SettingsProvider>);
  fireEvent.click(screen.getByText("toggle"));
  expect(document.documentElement.classList.contains("dark")).toBe(false);
  expect(localStorage.getItem("peakstats-theme")).toBe("light");
  await waitFor(() => expect(patchSettings).toHaveBeenCalledWith({ theme: "light" }));
});
