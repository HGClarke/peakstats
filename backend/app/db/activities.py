from typing import Any, NotRequired, TypedDict, cast

from postgrest.types import CountMethod
from supabase import Client


class ActivityRow(TypedDict):
    id: int
    athlete_id: int
    name: str
    type: str
    start_date: str
    start_date_local: str | None
    distance_m: float
    moving_time_s: int
    elapsed_time_s: int
    elev_gain_m: float
    avg_speed_ms: float | None
    avg_hr: int | None
    summary_polyline: str | None
    created_at: NotRequired[str]


def upsert_activities(client: Client, rows: list[ActivityRow]) -> None:
    if not rows:
        return
    client.table("activities").upsert(
        cast(list[dict[str, Any]], rows), on_conflict="id"
    ).execute()


def list_activities_since(
    client: Client, athlete_id: int, since_iso: str
) -> list[ActivityRow]:
    resp = (
        client.table("activities")
        .select("*")
        .eq("athlete_id", athlete_id)
        .gte("start_date", since_iso)
        .order("start_date", desc=False)
        .execute()
    )
    return cast(list[ActivityRow], resp.data)


def list_recent_activities(
    client: Client, athlete_id: int, limit: int
) -> list[ActivityRow]:
    resp = (
        client.table("activities")
        .select("*")
        .eq("athlete_id", athlete_id)
        .order("start_date", desc=True)
        .limit(limit)
        .execute()
    )
    return cast(list[ActivityRow], resp.data)


def count_activities(client: Client, athlete_id: int) -> int:
    resp = (
        client.table("activities")
        .select("id", count=CountMethod.exact)
        .eq("athlete_id", athlete_id)
        .limit(1)
        .execute()
    )
    return resp.count or 0


def list_activities_filtered(
    client: Client,
    athlete_id: int,
    *,
    q: str | None,
    min_dist: float | None,
    min_time: int | None,
    min_elev: float | None,
    order: str,
    as_of: str,
    offset: int,
    limit: int,
) -> tuple[list[ActivityRow], int]:
    # `query: Any` sidesteps the differing builder subtypes returned by each
    # chained filter (select -> filter -> ...), which mypy would otherwise reject
    # on reassignment.
    query: Any = (
        client.table("activities")
        .select("*", count=CountMethod.exact)
        .eq("athlete_id", athlete_id)
        .lte("created_at", as_of)
    )
    if q:
        query = query.ilike("name", f"%{q}%")
    if min_dist is not None:
        query = query.gte("distance_m", min_dist)
    if min_time is not None:
        query = query.gte("moving_time_s", min_time)
    if min_elev is not None:
        query = query.gte("elev_gain_m", min_elev)
    # `order` is a PostgREST order string the service builds, e.g.
    # "avg_speed_ms.desc.nullslast,id.desc"; replay each clause as an .order() call
    # so the emitted query matches the previous behavior exactly.
    for part in order.split(","):
        column, _, rest = part.partition(".")
        tokens = rest.split(".") if rest else []
        desc = "desc" in tokens
        nullsfirst: bool | None = None
        if "nullslast" in tokens:
            nullsfirst = False
        elif "nullsfirst" in tokens:
            nullsfirst = True
        query = query.order(column, desc=desc, nullsfirst=nullsfirst)
    resp = query.range(offset, offset + limit - 1).execute()
    return cast(list[ActivityRow], resp.data), (resp.count or 0)


def get_activity(client: Client, athlete_id: int, activity_id: int) -> ActivityRow | None:
    resp = (
        client.table("activities").select("*")
        .eq("id", activity_id).eq("athlete_id", athlete_id).execute()
    )
    return cast(ActivityRow, resp.data[0]) if resp.data else None


def delete_activity(client: Client, athlete_id: int, activity_id: int) -> None:
    client.table("activities").delete().eq("id", activity_id).eq(
        "athlete_id", athlete_id
    ).execute()


def list_activities_needing_detail(
    client: Client, athlete_id: int, limit: int
) -> list[ActivityRow]:
    resp = (
        client.table("activities")
        .select("*")
        .eq("athlete_id", athlete_id)
        .is_("detail_fetched_at", "null")
        .order("start_date", desc=False)
        .limit(limit)
        .execute()
    )
    return cast(list[ActivityRow], resp.data)


def mark_detail_fetched(
    client: Client, activity_id: int, splits_metric: Any, fetched_at: str
) -> None:
    client.table("activities").update(
        {"splits_metric": splits_metric, "detail_fetched_at": fetched_at}
    ).eq("id", activity_id).execute()
