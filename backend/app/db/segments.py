from typing import Any, NotRequired, TypedDict, cast

from supabase import Client

# PostgREST caps each response at its default max-rows; loop in pages of this
# size until a short page returns so the athlete's full effort history is read.
EFFORTS_PAGE_SIZE = 1000


class SegmentRow(TypedDict):
    id: int
    name: str
    distance_m: float
    avg_grade: float


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


def list_athlete_efforts(client: Client, athlete_id: int, as_of: str) -> list[dict]:
    """All of an athlete's efforts ingested at/before ``as_of`` (the snapshot
    boundary), embedding each segment's name/distance/grade. Pages past the
    PostgREST max-rows cap so the list is never silently truncated."""
    rows: list[dict] = []
    start = 0
    while True:
        resp = (
            client.table("segment_efforts")
            .select(
                "id, segment_id, elapsed_time_s, start_date, "
                "segments(name, distance_m, avg_grade)"
            )
            .eq("athlete_id", athlete_id)
            .lte("created_at", as_of)
            .range(start, start + EFFORTS_PAGE_SIZE - 1)
            .execute()
        )
        page = cast(list[dict], resp.data)
        rows.extend(page)
        if len(page) < EFFORTS_PAGE_SIZE:
            return rows
        start += EFFORTS_PAGE_SIZE


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
