from datetime import UTC, datetime, timedelta

import httpx

from app.db import activities as activities_db
from app.db.activities import ActivityRow
from app.models.activities import (
    OverviewResponse,
    RecentRideItem,
    WeekDay,
    WeekTotals,
)

RECENT_LIMIT = 5
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
