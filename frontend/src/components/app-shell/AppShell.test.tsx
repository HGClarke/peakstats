import { fireEvent, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/providers";
import { AppShell } from "./AppShell";

const athlete = {
  id: 99, name: "Ada Lovelace", avatar_url: null,
  settings: { units: "metric", theme: "dark", default_period: "week" },
};

describe("AppShell", () => {
  it("renders nav, title, and the athlete name", () => {
    renderWithProviders(
      <MemoryRouter>
        <AppShell navActive="Overview" athlete={athlete} syncLabel="Up to date"
          onLogout={() => {}} title="Home">
          <div>body</div>
        </AppShell>
      </MemoryRouter>,
    );
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Activities")).toBeInTheDocument();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("body")).toBeInTheDocument();
  });

  it("calls onLogout when the logout button is clicked", () => {
    const onLogout = vi.fn();
    renderWithProviders(
      <MemoryRouter>
        <AppShell navActive="Overview" athlete={athlete} syncLabel="Up to date"
          onLogout={onLogout} title="Overview">
          <div>body</div>
        </AppShell>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: /log out/i }));
    expect(onLogout).toHaveBeenCalled();
  });
});
