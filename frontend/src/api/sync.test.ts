import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SyncStatus } from "@/types/sync";
import {
  fetchSyncStatus,
  refreshSync,
  startSync,
  syncRefetchInterval,
  SYNC_POLL_MS,
  useRefreshSync,
} from "./sync";

afterEach(() => vi.restoreAllMocks());

const status: SyncStatus = {
  status: "backfilling", progress: 40, synced: 88,
  last_backfill_at: null, last_sync_at: null,
};

describe("sync api", () => {
  it("fetchSyncStatus GETs /sync/status with credentials", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(status), {
        status: 200, headers: { "content-type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(fetchSyncStatus()).resolves.toEqual(status);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/sync/status"),
      expect.objectContaining({ credentials: "include" })
    );
  });

  it("startSync POSTs /sync/start", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(status), {
        status: 200, headers: { "content-type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);
    await startSync();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/sync/start"),
      expect.objectContaining({ method: "POST", credentials: "include" })
    );
  });

  it("refreshSync POSTs /sync/refresh", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ synced: 3 }), {
        status: 200, headers: { "content-type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(refreshSync()).resolves.toEqual({ synced: 3 });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/sync/refresh"),
      expect.objectContaining({ method: "POST", credentials: "include" })
    );
  });

  it("polls only while backfilling", () => {
    expect(syncRefetchInterval(status)).toBe(SYNC_POLL_MS);
    expect(syncRefetchInterval({ ...status, status: "idle" })).toBe(false);
    expect(syncRefetchInterval(undefined)).toBe(false);
  });

  it("useRefreshSync invalidates both sync status and overview on success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ synced: 2 }), {
        status: 200, headers: { "content-type": "application/json" },
      })
    ));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const spy = vi.spyOn(client, "invalidateQueries");
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client }, children);

    const { result } = renderHook(() => useRefreshSync(), { wrapper });
    await result.current.mutateAsync();

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith({ queryKey: ["sync", "status"] });
      expect(spy).toHaveBeenCalledWith({ queryKey: ["activities", "overview"] });
    });
  });
});
