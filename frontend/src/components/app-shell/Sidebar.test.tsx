import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { Sidebar } from "./Sidebar";

const athlete = {
  id: 1, name: "Ada Lovelace", avatar_url: null,
  settings: { units: "metric", theme: "dark", default_period: "week" },
};

function renderSidebar() {
  render(
    <MemoryRouter>
      <Sidebar navActive="Activities" athlete={athlete} syncLabel="Up to date"
        onLogout={() => {}} />
    </MemoryRouter>,
  );
}

describe("Sidebar", () => {
  it("links built routes and leaves unbuilt ones inert", () => {
    renderSidebar();
    expect(screen.getByRole("link", { name: /activities/i }))
      .toHaveAttribute("href", "/activities");
    expect(screen.getByRole("link", { name: /overview/i }))
      .toHaveAttribute("href", "/home");
    expect(screen.getByRole("link", { name: /segments/i }))
      .toHaveAttribute("href", "/segments");
    expect(screen.queryByRole("link", { name: /goals/i })).toBeNull();
  });
});
