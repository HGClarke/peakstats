import { render, screen, fireEvent } from "@testing-library/react";
import LandingPage from "./LandingPage";

beforeEach(() => {
  document.documentElement.classList.remove("dark", "light");
});

it("renders the logo wordmark", () => {
  render(<LandingPage />);
  expect(screen.getByText("peakstats")).toBeInTheDocument();
});

it("renders the headline", () => {
  render(<LandingPage />);
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
    "Make sense of"
  );
});

it("renders the CTA link pointing to #", () => {
  render(<LandingPage />);
  const cta = screen.getByRole("link", { name: /connect with strava/i });
  expect(cta).toHaveAttribute("href", "#");
});

it("adds dark class to documentElement on mount", () => {
  render(<LandingPage />);
  expect(document.documentElement.classList.contains("dark")).toBe(true);
});

it("removes dark class when theme is toggled to light", () => {
  render(<LandingPage />);
  fireEvent.click(screen.getByTitle("Toggle theme"));
  expect(document.documentElement.classList.contains("dark")).toBe(false);
});

it("re-adds dark class when toggled back", () => {
  render(<LandingPage />);
  fireEvent.click(screen.getByTitle("Toggle theme"));
  fireEvent.click(screen.getByTitle("Toggle theme"));
  expect(document.documentElement.classList.contains("dark")).toBe(true);
});

it("renders the weekly distance stat", () => {
  render(<LandingPage />);
  expect(screen.getByText("142.6")).toBeInTheDocument();
});

it("renders both recent ride names", () => {
  render(<LandingPage />);
  expect(screen.getByText("Morning commute")).toBeInTheDocument();
  expect(screen.getByText("River loop")).toBeInTheDocument();
});
