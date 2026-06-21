import { render, screen, fireEvent, renderHook } from "@testing-library/react";
import { ThemeProvider } from "./ThemeProvider";
import { useTheme } from "./theme-context";

beforeEach(() => {
  document.documentElement.classList.remove("dark", "light");
  localStorage.clear();
});

function ThemeProbe() {
  const { theme, isDark, toggleTheme } = useTheme();
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <span data-testid="isDark">{String(isDark)}</span>
      <button onClick={toggleTheme}>toggle</button>
    </div>
  );
}

it("defaults to dark and applies the dark class on mount", () => {
  render(
    <ThemeProvider>
      <ThemeProbe />
    </ThemeProvider>
  );
  expect(screen.getByTestId("theme")).toHaveTextContent("dark");
  expect(screen.getByTestId("isDark")).toHaveTextContent("true");
  expect(document.documentElement.classList.contains("dark")).toBe(true);
});

it("toggles to light and removes the dark class", () => {
  render(
    <ThemeProvider>
      <ThemeProbe />
    </ThemeProvider>
  );
  fireEvent.click(screen.getByText("toggle"));
  expect(screen.getByTestId("theme")).toHaveTextContent("light");
  expect(document.documentElement.classList.contains("dark")).toBe(false);
});

it("persists the chosen theme to localStorage", () => {
  render(
    <ThemeProvider>
      <ThemeProbe />
    </ThemeProvider>
  );
  fireEvent.click(screen.getByText("toggle"));
  expect(localStorage.getItem("peakstats-theme")).toBe("light");
});

it("restores a persisted theme on mount", () => {
  localStorage.setItem("peakstats-theme", "light");
  render(
    <ThemeProvider>
      <ThemeProbe />
    </ThemeProvider>
  );
  expect(screen.getByTestId("theme")).toHaveTextContent("light");
  expect(document.documentElement.classList.contains("dark")).toBe(false);
});

it("throws when useTheme is used outside a ThemeProvider", () => {
  const spy = vi.spyOn(console, "error").mockImplementation(() => {});
  expect(() => renderHook(() => useTheme())).toThrow(
    /useTheme must be used within a ThemeProvider/
  );
  spy.mockRestore();
});
