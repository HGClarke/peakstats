export type SyncStatusValue = "never_synced" | "backfilling" | "idle" | "error";

export type SyncStatus = {
  status: SyncStatusValue;
  progress: number;
  synced: number;
  last_backfill_at: string | null;
  last_sync_at: string | null;
};
