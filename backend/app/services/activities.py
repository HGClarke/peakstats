from datetime import UTC, datetime, timedelta
from math import ceil

import httpx

from app.db import activities as activities_db
from app.db.activities import ActivityRow
from app.models.activities import (
    ActivityListItem,
    ActivityListResponse,
    OverviewResponse,
    RecentRideItem,
    SortDir,
    SortField,
    WeekDay,
    WeekTotals,
)

RECENT_LIMIT = 5
PAGE_SIZE = 9

_SORT_COLUMNS: dict[SortField, str] = {
    "date": "start_date",
    "distance": "distance_m",
    "time": "moving_time_s",
    "elevation": "elev_gain_m",
    "speed": "avg_speed_ms",
}
_WEEKDAY_LABELS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def _parse(start_date: str) -> datetime:
    return datetime.fromisoformat(start_date).astimezone(UTC)


def _totals(rows: list[ActivityRow]) -> WeekTotals:
    distance_m = sum(r["distance_m"] for r in rows)
    moving_time_s = sum(r["moving_time_s"] for r in rows)
    return WeekTotals(
        distance_m=distance_m,
        elev_gain_m=sum(r["elev_gain_m"] for r in rows),
        moving_time_s=moving_time_s,
        avg_speed_ms=distance_m / moving_time_s if moving_time_s > 0 else None,
    )


def get_overview(
    supabase: httpx.Client, athlete_id: int, now: datetime | None = None
) -> OverviewResponse:
    now = (now or datetime.now(UTC)).astimezone(UTC)
    this_monday = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    last_monday = this_monday - timedelta(days=7)

    rows = activities_db.list_activities_since(
        supabase, athlete_id, last_monday.isoformat()
    )

    this_week = [r for r in rows if _parse(r["start_date"]) >= this_monday]
    last_week = [
        r
        for r in rows
        if last_monday <= _parse(r["start_date"]) < this_monday
    ]

    km_by_day = [0.0] * 7
    for r in this_week:
        km_by_day[_parse(r["start_date"]).weekday()] += r["distance_m"] / 1000
    week = [
        WeekDay(day=label, km=round(km_by_day[i], 1))
        for i, label in enumerate(_WEEKDAY_LABELS)
    ]

    recent = activities_db.list_recent_activities(supabase, athlete_id, RECENT_LIMIT)
    recent_rides = [
        RecentRideItem(
            id=r["id"],
            name=r["name"],
            type=r["type"],
            start_date=r["start_date"],
            distance_m=r["distance_m"],
            moving_time_s=r["moving_time_s"],
        )
        for r in recent
    ]

    return OverviewResponse(
        this_week=_totals(this_week),
        last_week=_totals(last_week),
        week=week,
        recent_rides=recent_rides,
    )


def list_activities(
    supabase: httpx.Client,
    athlete_id: int,
    *,
    q: str | None,
    min_dist: float | None,
    min_time: int | None,
    min_elev: float | None,
    sort: SortField,
    direction: SortDir,
    page: int,
    as_of: datetime | None = None,
) -> ActivityListResponse:
    snapshot = as_of or datetime.now(UTC)
    column = _SORT_COLUMNS[sort]
    primary = (
        f"{column}.{direction}.nullslast" if sort == "speed"
        else f"{column}.{direction}"
    )
    order = f"{primary},id.{direction}"
    offset = (page - 1) * PAGE_SIZE

    rows, total = activities_db.list_activities_filtered(
        supabase, athlete_id,
        q=q, min_dist=min_dist, min_time=min_time, min_elev=min_elev,
        order=order, as_of=snapshot.isoformat(), offset=offset, limit=PAGE_SIZE,
    )
    items = [
        ActivityListItem(
            id=r["id"], name=r["name"], type=r["type"], start_date=r["start_date"],
            distance_m=r["distance_m"], moving_time_s=r["moving_time_s"],
            elev_gain_m=r["elev_gain_m"], avg_speed_ms=r["avg_speed_ms"],
        )
        for r in rows
    ]
    return ActivityListResponse(
        activities=items,
        page=page,
        page_size=PAGE_SIZE,
        total=total,
        total_pages=max(1, ceil(total / PAGE_SIZE)),
        as_of=snapshot,
    )
