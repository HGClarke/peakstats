from pydantic import BaseModel


class SyncStatusResponse(BaseModel):
    status: str
    progress: int
    synced: int
    last_backfill_at: str | None = None
    last_sync_at: str | None = None


class RefreshResponse(BaseModel):
    synced: int
