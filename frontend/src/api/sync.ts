import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { SyncStatus } from "@/types/sync";
import { apiFetch } from "./client";

export const SYNC_POLL_MS = 1500;

export function fetchSyncStatus(): Promise<SyncStatus> {
  return apiFetch<SyncStatus>("/sync/status");
}

export function startSync(): Promise<SyncStatus> {
  return apiFetch<SyncStatus>("/sync/start", { method: "POST" });
}

export function refreshSync(): Promise<{ synced: number }> {
  return apiFetch<{ synced: number }>("/sync/refresh", { method: "POST" });
}

/** Poll every SYNC_POLL_MS while a backfill is running; otherwise stop. */
export function syncRefetchInterval(status?: SyncStatus): number | false {
  return status?.status === "backfilling" ? SYNC_POLL_MS : false;
}

export function useSyncStatus() {
  return useQuery({
    queryKey: ["sync", "status"],
    queryFn: fetchSyncStatus,
    refetchInterval: (query) => syncRefetchInterval(query.state.data),
  });
}

export function useStartSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: startSync,
    onSuccess: (data) => {
      queryClient.setQueryData(["sync", "status"], data);
    },
  });
}

export function useRefreshSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: refreshSync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sync", "status"] });
    },
  });
}
