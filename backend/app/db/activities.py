from typing import NotRequired, TypedDict, cast

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
    created_at: NotRequired[str]


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


def _parse_total(response: httpx.Response) -> int:
    total = response.headers.get("Content-Range", "").split("/")[-1]
    return int(total) if total.isdigit() else 0


def count_activities(client: httpx.Client, athlete_id: int) -> int:
    response = client.get(
        "/activities",
        params={"athlete_id": f"eq.{athlete_id}", "select": "id"},
        headers={"Prefer": "count=exact", "Range": "0-0"},
    )
    response.raise_for_status()
    return _parse_total(response)


def list_activities_filtered(
    client: httpx.Client,
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
    params: dict[str, str] = {
        "athlete_id": f"eq.{athlete_id}",
        "created_at": f"lte.{as_of}",
        "order": order,
        "select": "*",
    }
    if q:
        params["name"] = f"ilike.*{q}*"
    if min_dist is not None:
        params["distance_m"] = f"gte.{min_dist}"
    if min_time is not None:
        params["moving_time_s"] = f"gte.{min_time}"
    if min_elev is not None:
        params["elev_gain_m"] = f"gte.{min_elev}"
    response = client.get(
        "/activities",
        params=params,
        headers={"Prefer": "count=exact", "Range": f"{offset}-{offset + limit - 1}"},
    )
    response.raise_for_status()
    return cast(list[ActivityRow], response.json()), _parse_total(response)
