from typing import TypedDict, cast

import httpx

_MERGE = {"Prefer": "resolution=merge-duplicates"}


class ActivityRow(TypedDict):
    id: int
    athlete_id: int
    name: str
    type: str
    start_date: str
    distance_m: float
    moving_time_s: int
    elapsed_time_s: int
    elev_gain_m: float
    avg_speed_ms: float | None
    avg_hr: int | None
    summary_polyline: str | None


def upsert_activities(client: httpx.Client, rows: list[ActivityRow]) -> None:
    if not rows:
        return
    response = client.post(
        "/activities",
        params={"on_conflict": "id"},
        headers=_MERGE,
        json=rows,
    )
    response.raise_for_status()


def list_activities_since(
    client: httpx.Client, athlete_id: int, since_iso: str
) -> list[ActivityRow]:
    response = client.get(
        "/activities",
        params={
            "athlete_id": f"eq.{athlete_id}",
            "start_date": f"gte.{since_iso}",
            "order": "start_date.asc",
            "select": "*",
        },
    )
    response.raise_for_status()
    return cast(list[ActivityRow], response.json())


def list_recent_activities(
    client: httpx.Client, athlete_id: int, limit: int
) -> list[ActivityRow]:
    response = client.get(
        "/activities",
        params={
            "athlete_id": f"eq.{athlete_id}",
            "order": "start_date.desc",
            "limit": str(limit),
            "select": "*",
        },
    )
    response.raise_for_status()
    return cast(list[ActivityRow], response.json())


def count_activities(client: httpx.Client, athlete_id: int) -> int:
    response = client.get(
        "/activities",
        params={"athlete_id": f"eq.{athlete_id}", "select": "id"},
        headers={"Prefer": "count=exact", "Range": "0-0"},
    )
    response.raise_for_status()
    content_range = response.headers.get("Content-Range", "")
    total = content_range.split("/")[-1]
    return int(total) if total.isdigit() else 0


def delete_activity(client: httpx.Client, athlete_id: int, activity_id: int) -> None:
    response = client.request(
        "DELETE",
        "/activities",
        params={"id": f"eq.{activity_id}", "athlete_id": f"eq.{athlete_id}"},
    )
    response.raise_for_status()
