from typing import TypedDict

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
