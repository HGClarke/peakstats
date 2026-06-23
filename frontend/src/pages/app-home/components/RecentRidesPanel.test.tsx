import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import { RecentRidesPanel } from "./RecentRidesPanel";
import type { DashRide } from "@/types/overview";

const RIDES: DashRide[] = [
  { id: 7, name: "River loop", meta: "Tue · Jun 16 · Ride", distLabel: "38.7 km",
    durLabel: "1h 34m", isPr: true, dotColor: "var(--color-strava)" },
];

function renderPanel() {
  const router = createMemoryRouter(
    [{ path: "/", element: <RecentRidesPanel rides={RIDES} /> }],
    { initialEntries: ["/"] },
  );
  return render(<RouterProvider router={router} />);
}

describe("RecentRidesPanel", () => {
  it("links each ride to its detail page", () => {
    renderPanel();
    expect(screen.getByRole("link", { name: /River loop/ })).toHaveAttribute("href", "/activities/7");
  });

  it("shows a PR badge and a VIEW ALL link", () => {
    renderPanel();
    expect(screen.getByText("PR")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /VIEW ALL/ })).toHaveAttribute("href", "/activities");
  });
});
