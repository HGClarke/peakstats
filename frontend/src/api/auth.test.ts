import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { createQueryWrapper } from "@/test/providers";
import { disconnect, fetchAthlete, logout, stravaLoginUrl, useAthlete } from "./auth";

afterEach(() => {
  vi.restoreAllMocks();
});

const athlete = {
  id: 99,
  name: "Ada Lovelace",
  avatar_url: "http://img/a.png",
  settings: { units: "metric", theme: "dark", default_period: "week" },
};

describe("auth api", () => {
  it("exposes the backend login URL", () => {
    expect(stravaLoginUrl).toContain("/auth/strava/login");
  });

  it("fetchAthlete sends credentials and parses the athlete", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(athlete), {
        status: 200,
        headers: { "content-type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchAthlete()).resolves.toEqual(athlete);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/athlete"),
      expect.objectContaining({ credentials: "include" })
    );
  });

  it("logout POSTs and tolerates a 204", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(logout()).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/auth/logout"),
      expect.objectContaining({ method: "POST", credentials: "include" })
    );
  });

  it("disconnect DELETEs the connection", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(disconnect()).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/athlete/connection"),
      expect.objectContaining({ method: "DELETE", credentials: "include" })
    );
  });
});

describe("useAthlete", () => {
  it("loads the athlete via react-query", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(athlete), {
          status: 200,
          headers: { "content-type": "application/json" },
        })
      )
    );
    const { result } = renderHook(() => useAthlete(), {
      wrapper: createQueryWrapper(),
    });
    await waitFor(() => expect(result.current.data).toEqual(athlete));
    expect(result.current.error).toBeNull();
  });
});
