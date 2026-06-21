from typing import TypedDict, cast

import httpx

_MERGE = {"Prefer": "resolution=merge-duplicates"}


class SyncStateRow(TypedDict):
    athlete_id: int
    status: str
    progress: int
    last_backfill_at: str | None
    last_sync_at: str | None
    last_webhook_event_id: int | None


def get_sync_state(client: httpx.Client, athlete_id: int) -> SyncStateRow | None:
    response = client.get(
        "/sync_state", params={"athlete_id": f"eq.{athlete_id}", "select": "*"}
    )
    response.raise_for_status()
    rows = response.json()
    return cast(SyncStateRow, rows[0]) if rows else None


def upsert_sync_state(
    client: httpx.Client, athlete_id: int, fields: dict
) -> None:
    response = client.post(
        "/sync_state",
        params={"on_conflict": "athlete_id"},
        headers=_MERGE,
        json=[{"athlete_id": athlete_id, **fields}],
    )
    response.raise_for_status()
