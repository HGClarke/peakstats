from typing import Any, TypedDict, cast

from supabase import Client

_COLS = (
    "activity_id, athlete_id, avg_power_w, np_w, work_kj, power_hist, hr_hist, has_power, has_hr"
)


class MetricsRow(TypedDict):
    activity_id: int
    athlete_id: int
    avg_power_w: float | None
    np_w: float | None
    work_kj: float | None
    power_hist: list[float] | None
    hr_hist: list[float] | None
    has_power: bool
    has_hr: bool


def get_metrics(client: Client, activity_id: int) -> MetricsRow | None:
    resp = (
        client.table("activity_metrics")
        .select(_COLS)
        .eq("activity_id", activity_id)
        .execute()
    )
    return cast(MetricsRow, resp.data[0]) if resp.data else None


def upsert_metrics(client: Client, row: MetricsRow) -> None:
    client.table("activity_metrics").upsert(
        cast(dict[str, Any], row), on_conflict="activity_id"
    ).execute()


def list_metrics_for_activities(
    client: Client, athlete_id: int, activity_ids: list[int]
) -> list[MetricsRow]:
    if not activity_ids:
        return []
    resp = (
        client.table("activity_metrics")
        .select(_COLS)
        .eq("athlete_id", athlete_id)
        .in_("activity_id", activity_ids)
        .execute()
    )
    return cast(list[MetricsRow], resp.data)


def list_activity_ids_needing_metrics(client: Client, athlete_id: int) -> list[int]:
    """Activity ids with no activity_metrics row yet (ascending), by id-diff.

    Resumable backfill marker: a metrics row's existence means 'done'. ~hundreds
    of ids is trivial. NOTE: relies on PostgREST's default page size covering the
    athlete's activity count (same characteristic as list_activities_since)."""
    acts = client.table("activities").select("id").eq("athlete_id", athlete_id).execute()
    mets = (
        client.table("activity_metrics")
        .select("activity_id")
        .eq("athlete_id", athlete_id)
        .execute()
    )
    act_rows = cast(list[dict[str, Any]], acts.data)
    met_rows = cast(list[dict[str, Any]], mets.data)
    have = {r["activity_id"] for r in met_rows}
    return sorted(r["id"] for r in act_rows if r["id"] not in have)
