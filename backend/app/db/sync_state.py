from typing import TypedDict, cast

from supabase import Client


class SyncStateRow(TypedDict):
    athlete_id: int
    status: str
    progress: int
    last_backfill_at: str | None
    last_sync_at: str | None
    last_webhook_event_id: int | None


def get_sync_state(client: Client, athlete_id: int) -> SyncStateRow | None:
    resp = (
        client.table("sync_state").select("*").eq("athlete_id", athlete_id).execute()
    )
    return cast(SyncStateRow, resp.data[0]) if resp.data else None


def upsert_sync_state(client: Client, athlete_id: int, fields: dict) -> None:
    client.table("sync_state").upsert(
        {"athlete_id": athlete_id, **fields}, on_conflict="athlete_id"
    ).execute()
