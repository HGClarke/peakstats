import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Topbar } from "./Topbar";

const navigate = vi.fn();
vi.mock("react-router", async () => {
  const actual = await vi.importActual<typeof import("react-router")>("react-router");
  return { ...actual, useNavigate: () => navigate };
});
vi.mock("@/components/ThemeToggle", () => ({ ThemeToggle: () => <div /> }));

function setHistoryIdx(idx: number | null) {
  window.history.replaceState(idx === null ? null : { idx }, "");
}

function renderBar() {
  render(
    <MemoryRouter>
      <Topbar title="Activity" backTo="/activities" />
    </MemoryRouter>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("Topbar back button", () => {
  it("goes back in history when there is a previous entry", () => {
    setHistoryIdx(2);
    renderBar();
    fireEvent.click(screen.getByRole("button", { name: /back/i }));
    expect(navigate).toHaveBeenCalledWith(-1);
  });

  it("falls back to backTo when there is no history to go back to", () => {
    setHistoryIdx(0);
    renderBar();
    fireEvent.click(screen.getByRole("button", { name: /back/i }));
    expect(navigate).toHaveBeenCalledWith("/activities");
  });
});
