from typing import Any, TypedDict, cast

from supabase import Client


class StreamRow(TypedDict):
    activity_id: int
    athlete_id: int
    data: dict
    resolution: str
    point_count: int


def get_streams(client: Client, activity_id: int) -> StreamRow | None:
    resp = (
        client.table("activity_streams")
        .select("activity_id, athlete_id, data, resolution, point_count")
        .eq("activity_id", activity_id)
        .execute()
    )
    return cast(StreamRow, resp.data[0]) if resp.data else None


def upsert_streams(client: Client, row: StreamRow) -> None:
    client.table("activity_streams").upsert(
        cast(dict[str, Any], row), on_conflict="activity_id"
    ).execute()
