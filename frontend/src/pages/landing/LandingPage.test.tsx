import { render, screen, fireEvent } from "@testing-library/react";
import { stravaLoginUrl } from "@/api/auth";
import { ThemeProvider } from "@/app/providers/ThemeProvider";
import LandingPage from "./LandingPage";

function renderLandingPage() {
  return render(
    <ThemeProvider>
      <LandingPage />
    </ThemeProvider>
  );
}

beforeEach(() => {
  document.documentElement.classList.remove("dark", "light");
  localStorage.clear();
});

it("renders the logo wordmark", () => {
  renderLandingPage();
  expect(screen.getByText("peakstats")).toBeInTheDocument();
});

it("renders the headline", () => {
  renderLandingPage();
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
    "Make sense of"
  );
});

it("renders the CTA link pointing to the Strava login URL", () => {
  renderLandingPage();
  const cta = screen.getByRole("link", { name: /connect with strava/i });
  expect(cta).toHaveAttribute("href", stravaLoginUrl);
});

it("adds dark class to documentElement on mount", () => {
  renderLandingPage();
  expect(document.documentElement.classList.contains("dark")).toBe(true);
});

it("removes dark class when theme is toggled to light", () => {
  renderLandingPage();
  fireEvent.click(screen.getByTitle("Toggle theme"));
  expect(document.documentElement.classList.contains("dark")).toBe(false);
});

it("re-adds dark class when toggled back", () => {
  renderLandingPage();
  fireEvent.click(screen.getByTitle("Toggle theme"));
  fireEvent.click(screen.getByTitle("Toggle theme"));
  expect(document.documentElement.classList.contains("dark")).toBe(true);
});

it("renders the weekly distance stat once data loads", async () => {
  renderLandingPage();
  expect(await screen.findByText("142.6")).toBeInTheDocument();
});

it("renders both recent ride names once data loads", async () => {
  renderLandingPage();
  expect(await screen.findByText("Morning commute")).toBeInTheDocument();
  expect(screen.getByText("River loop")).toBeInTheDocument();
});
