import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ThemeProvider } from "@/app/providers/ThemeProvider";

const mockNavigate = vi.fn();
vi.mock("react-router", async () => {
  const actual = await vi.importActual<typeof import("react-router")>("react-router");
  return { ...actual, useNavigate: () => mockNavigate };
});

const useAthlete = vi.fn();
vi.mock("@/api/auth", () => ({
  useAthlete: () => useAthlete(),
  logout: vi.fn(),
  disconnect: vi.fn(),
}));

import AppHome from "./AppHome";

function renderPage() {
  render(
    <ThemeProvider>
      <MemoryRouter>
        <AppHome />
      </MemoryRouter>
    </ThemeProvider>
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("AppHome", () => {
  it("shows the athlete name once loaded", () => {
    useAthlete.mockReturnValue({
      data: {
        id: 99, name: "Ada Lovelace", avatar_url: "http://img/a.png",
        settings: { units: "metric", theme: "dark", default_period: "week" },
      },
      isLoading: false, error: null,
    });
    renderPage();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
  });

  it("redirects to landing when unauthenticated", async () => {
    useAthlete.mockReturnValue({ data: null, isLoading: false, error: new Error("401") });
    renderPage();
    await waitFor(() =>
      expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true })
    );
  });
});


import { fireEvent } from "@testing-library/react";
import { logout, disconnect } from "@/api/auth";

describe("AppHome actions", () => {
  const loaded = {
    data: {
      id: 99, name: "Ada Lovelace", avatar_url: null,
      settings: { units: "metric", theme: "dark", default_period: "week" },
    },
    isLoading: false, error: null,
  };

  it("logs out then returns to landing", async () => {
    (logout as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    useAthlete.mockReturnValue(loaded);
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /log out/i }));
    await waitFor(() => expect(logout).toHaveBeenCalled());
    await waitFor(() =>
      expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true })
    );
  });

  it("disconnects then returns to landing", async () => {
    (disconnect as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    useAthlete.mockReturnValue(loaded);
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /disconnect/i }));
    await waitFor(() => expect(disconnect).toHaveBeenCalled());
    await waitFor(() =>
      expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true })
    );
  });
});
