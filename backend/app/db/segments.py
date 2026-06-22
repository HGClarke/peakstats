from typing import Any, NotRequired, TypedDict, cast

from supabase import Client


class SegmentRow(TypedDict):
    id: int
    name: str
    distance_m: float
    avg_grade: float
    climb_category: int
    elev_gain_m: float


class SegmentEffortRow(TypedDict):
    id: int
    segment_id: int
    athlete_id: int
    activity_id: int
    elapsed_time_s: int
    avg_watts: float | None
    avg_hr: int | None
    avg_speed_ms: float | None
    start_date: str
    is_best: bool
    created_at: NotRequired[str]


def upsert_segments(client: Client, rows: list[SegmentRow]) -> None:
    if not rows:
        return
    client.table("segments").upsert(
        cast(list[dict[str, Any]], rows), on_conflict="id"
    ).execute()


def upsert_segment_efforts(client: Client, rows: list[SegmentEffortRow]) -> None:
    if not rows:
        return
    client.table("segment_efforts").upsert(
        cast(list[dict[str, Any]], rows), on_conflict="id"
    ).execute()


def get_effort_keys(client: Client, athlete_id: int, segment_id: int) -> list[dict]:
    resp = (
        client.table("segment_efforts")
        .select("id, elapsed_time_s, start_date")
        .eq("athlete_id", athlete_id)
        .eq("segment_id", segment_id)
        .execute()
    )
    return cast(list[dict], resp.data)


def set_is_best(client: Client, athlete_id: int, segment_id: int, best_id: int) -> None:
    client.table("segment_efforts").update({"is_best": False}).eq(
        "athlete_id", athlete_id
    ).eq("segment_id", segment_id).execute()
    client.table("segment_efforts").update({"is_best": True}).eq("id", best_id).execute()


def list_segment_summaries(
    client: Client, athlete_id: int, *,
    as_of: str, q: str | None, direction: str, limit: int, offset: int,
) -> list[dict]:
    """One page of per-segment summaries for the athlete, aggregated and
    paginated in Postgres by the ``list_segment_summaries`` RPC. Each row carries
    a ``total_count`` (the full filtered count, before limit/offset). Only the
    requested page crosses the wire, so the cost is flat as efforts grow."""
    resp = client.rpc(
        "list_segment_summaries",
        {
            "p_athlete_id": athlete_id,
            "p_as_of": as_of,
            "p_q": q,
            "p_dir": direction,
            "p_limit": limit,
            "p_offset": offset,
        },
    ).execute()
    return cast(list[dict], resp.data)


def get_segment(client: Client, segment_id: int) -> SegmentRow | None:
    resp = client.table("segments").select("*").eq("id", segment_id).execute()
    return cast(SegmentRow, resp.data[0]) if resp.data else None


def list_segment_efforts(client: Client, athlete_id: int, segment_id: int) -> list[dict]:
    resp = (
        client.table("segment_efforts")
        .select(
            "id, activity_id, start_date, elapsed_time_s, avg_watts, avg_hr, "
            "avg_speed_ms, is_best, activities(name)"
        )
        .eq("athlete_id", athlete_id)
        .eq("segment_id", segment_id)
        .order("start_date", desc=True)
        .execute()
    )
    return cast(list[dict], resp.data)
