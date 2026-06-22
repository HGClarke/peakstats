from datetime import UTC, datetime, timedelta
from math import ceil
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from supabase import Client

from app.db import activities as activities_db
from app.db import athletes as athletes_db
from app.db import streams as streams_db
from app.db.activities import ActivityRow
from app.models.activities import (
    ActivityDetailResponse,
    ActivityListItem,
    ActivityListResponse,
    ActivityStreamsResponse,
    ClimbItem,
    OverviewResponse,
    RecentRideItem,
    SortDir,
    SortField,
    WeekDay,
    WeekTotals,
    ZoneBucket,
    ZonesBlock,
)
from app.services import analysis
from app.services.tokens import get_valid_access_token
from app.strava import StravaClient

RECENT_LIMIT = 5
PAGE_SIZE = 9
STREAM_KEYS = ["time", "distance", "altitude", "heartrate", "watts", "velocity_smooth"]

_SORT_COLUMNS: dict[SortField, str] = {
    "date": "start_date",
    "distance": "distance_m",
    "time": "moving_time_s",
    "elevation": "elev_gain_m",
    "speed": "avg_speed_ms",
}
_WEEKDAY_LABELS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def _resolve_tz(tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _local_naive(row: ActivityRow) -> datetime:
    """Wall-clock datetime used for day bucketing and week membership.

    Uses Strava's per-ride start_date_local; falls back to UTC start_date for
    legacy rows. The value is a wall-clock label — it is intentionally NOT
    timezone-converted (we drop the tzinfo and compare numerals directly).
    """
    raw = row.get("start_date_local") or row["start_date"]
    return datetime.fromisoformat(raw).replace(tzinfo=None)


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
    supabase: Client,
    athlete_id: int,
    tz: str = "UTC",
    now: datetime | None = None,
) -> OverviewResponse:
    zone = _resolve_tz(tz)
    now_local = (now or datetime.now(UTC)).astimezone(zone)
    this_monday = (
        now_local - timedelta(days=now_local.weekday())
    ).replace(hour=0, minute=0, second=0, microsecond=0)
    last_monday = this_monday - timedelta(days=7)

    # Rows are fetched by UTC start_date, which can sit up to ~14h off the local
    # date, so widen the query a day and filter precisely by local time below.
    rows = activities_db.list_activities_since(
        supabase, athlete_id, (last_monday - timedelta(days=1)).isoformat()
    )

    this_monday_naive = this_monday.replace(tzinfo=None)
    last_monday_naive = last_monday.replace(tzinfo=None)

    this_week = [r for r in rows if _local_naive(r) >= this_monday_naive]
    last_week = [
        r for r in rows
        if last_monday_naive <= _local_naive(r) < this_monday_naive
    ]

    km_by_day = [0.0] * 7
    for r in this_week:
        km_by_day[_local_naive(r).weekday()] += r["distance_m"] / 1000
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
            start_date_local=r.get("start_date_local"),
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
    supabase: Client,
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


def ensure_streams(
    supabase: Client,
    strava: StravaClient,
    athlete_id: int,
    activity_id: int,
) -> dict[str, list]:
    """Return cached stream data for the activity, fetching from Strava on miss.

    Stores a sentinel (empty data, point_count 0) when Strava has no streams, so
    we never refetch. `data` is the flat object-of-arrays.
    """
    existing = streams_db.get_streams(supabase, activity_id)
    if existing is not None:
        return existing["data"]
    token = get_valid_access_token(supabase, strava, athlete_id)
    data = strava.get_activity_streams(token, activity_id, STREAM_KEYS)
    point_count = len(data.get("time") or data.get("distance") or [])
    streams_db.upsert_streams(supabase, {
        "activity_id": activity_id, "athlete_id": athlete_id,
        "data": data, "resolution": "high", "point_count": point_count,
    })
    return data


def get_streams_payload(
    supabase: Client,
    strava: StravaClient,
    athlete_id: int,
    activity_id: int,
) -> ActivityStreamsResponse:
    data = ensure_streams(supabase, strava, athlete_id, activity_id)
    return ActivityStreamsResponse(
        point_count=len(data.get("time") or data.get("distance") or []),
        time=data.get("time"),
        distance=data.get("distance"),
        altitude=data.get("altitude"),
        watts=data.get("watts"),
        heartrate=data.get("heartrate"),
        velocity_smooth=data.get("velocity_smooth"),
    )


class ActivityNotFoundError(Exception):
    """Raised when an activity does not exist for the requesting athlete."""


def _zones_block(
    time: list,
    series: list | None,
    zone_defs: list[dict],
    bound: int | None,
) -> ZonesBlock:
    if bound is None or not series:
        return ZonesBlock(unset=True)
    buckets = [ZoneBucket(**b) for b in analysis.time_in_zones(time, series, zone_defs)]
    return ZonesBlock(unset=False, avg=analysis.weighted_mean(time, series), buckets=buckets)


def get_detail(
    supabase: Client,
    strava: StravaClient,
    athlete_id: int,
    activity_id: int,
) -> ActivityDetailResponse:
    row = activities_db.get_activity(supabase, athlete_id, activity_id)
    if row is None:
        raise ActivityNotFoundError(f"activity {activity_id} not found for athlete")
    data = ensure_streams(supabase, strava, athlete_id, activity_id)
    time = data.get("time") or []
    watts = data.get("watts")
    hr = data.get("heartrate")
    athlete_row = athletes_db.get_athlete(supabase, athlete_id)
    settings: dict = athlete_row.get("settings", {}) if athlete_row else {}
    ftp = settings.get("ftp_w")
    hr_max = settings.get("hr_max")
    power_block = (
        _zones_block(time, watts, analysis.power_zones(ftp), ftp)
        if ftp else ZonesBlock(unset=True)
    )
    hr_block = (
        _zones_block(time, hr, analysis.hr_zones(hr_max), hr_max)
        if hr_max else ZonesBlock(unset=True)
    )
    climb_rows = [
        {"name": r["segments"]["name"], "climb_category": r["segments"]["climb_category"],
         "distance_m": r["segments"]["distance_m"], "avg_grade": r["segments"]["avg_grade"],
         "elev_gain_m": r["segments"]["elev_gain_m"], "elapsed_time_s": r["elapsed_time_s"]}
        for r in activities_db.list_activity_climbs(supabase, athlete_id, activity_id)
        if r.get("segments") and r["segments"]["climb_category"] > 0
    ]
    climbs = [
        ClimbItem(name=c["name"], climb_category=c["climb_category"], distance_m=c["distance_m"],
                  avg_grade=c["avg_grade"], elev_gain_m=c["elev_gain_m"],
                  time_s=c["elapsed_time_s"], vam=c["vam"])
        for c in analysis.compute_climbs(climb_rows)
    ]
    return ActivityDetailResponse(
        id=row["id"], name=row["name"], type=row["type"],
        start_date=row["start_date"], start_date_local=row.get("start_date_local"),
        location=None,
        distance_m=row["distance_m"], moving_time_s=row["moving_time_s"],
        elev_gain_m=row["elev_gain_m"], avg_speed_ms=row.get("avg_speed_ms"),
        avg_power_w=analysis.weighted_mean(time, watts) if watts else None,
        normalized_power_w=analysis.normalized_power(time, watts),
        work_kj=analysis.total_work_kj(time, watts),
        avg_hr=row.get("avg_hr"),
        summary_polyline=row.get("summary_polyline"),
        power_zones=power_block,
        hr_zones=hr_block,
        climbs=climbs,
    )
