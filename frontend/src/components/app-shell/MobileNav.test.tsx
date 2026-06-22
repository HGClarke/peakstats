import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { MobileNav } from "./MobileNav";

const athlete = {
  id: 1, name: "Ada Lovelace", avatar_url: null,
  settings: { units: "metric", theme: "dark", default_period: "week" },
};

function renderNav(open: boolean, onClose: () => void = () => {}) {
  return render(
    <MemoryRouter>
      <MobileNav open={open} onClose={onClose} navActive="Overview"
        athlete={athlete} syncLabel="Up to date" onLogout={() => {}} />
    </MemoryRouter>,
  );
}

describe("MobileNav", () => {
  it("renders nothing when closed", () => {
    renderNav(false);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByText("Activities")).toBeNull();
  });

  it("renders the nav when open", () => {
    renderNav(true);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /activities/i })).toBeInTheDocument();
  });

  it("calls onClose when Escape is pressed", () => {
    const onClose = vi.fn();
    renderNav(true, onClose);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose when the backdrop is clicked", () => {
    const onClose = vi.fn();
    const { container } = renderNav(true, onClose);
    const backdrop = container.querySelector("#mobile-nav-drawer > [aria-hidden]");
    expect(backdrop).not.toBeNull();
    fireEvent.click(backdrop as Element);
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose when a nav link is clicked", () => {
    const onClose = vi.fn();
    renderNav(true, onClose);
    fireEvent.click(screen.getByRole("link", { name: /activities/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose when the close button is clicked", () => {
    const onClose = vi.fn();
    renderNav(true, onClose);
    fireEvent.click(screen.getByRole("button", { name: /close navigation/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it("moves focus to the close button when opened", () => {
    renderNav(true);
    expect(screen.getByRole("button", { name: /close navigation/i })).toHaveFocus();
  });
});
