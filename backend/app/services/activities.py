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
    HeatmapData,
    HeatmapDay,
    OverviewResponse,
    OverviewSummary,
    Period,
    PeriodTotals,
    RecentRideItem,
    RideTypeCount,
    SortDir,
    SortField,
    TrendPoint,
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
_MONTH_LABELS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                 "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


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


def _totals(rows: list[ActivityRow]) -> PeriodTotals:
    distance_m = sum(r["distance_m"] for r in rows)
    moving_time_s = sum(r["moving_time_s"] for r in rows)
    return PeriodTotals(
        distance_m=distance_m,
        elev_gain_m=sum(r["elev_gain_m"] for r in rows),
        moving_time_s=moving_time_s,
        avg_speed_ms=distance_m / moving_time_s if moving_time_s > 0 else None,
    )


def _add_month(d: datetime) -> datetime:
    return d.replace(year=d.year + 1, month=1) if d.month == 12 else d.replace(month=d.month + 1)


def _sub_month(d: datetime) -> datetime:
    return d.replace(year=d.year - 1, month=12) if d.month == 1 else d.replace(month=d.month - 1)


def _period_bounds(base: datetime, period: Period) -> tuple[datetime, datetime, datetime]:
    """Return (this_start, this_end, last_start) for the calendar period containing `base`.

    `base` is midnight of the current local day. Bounds are half-open [start, end).
    """
    if period == "week":
        this_start = base - timedelta(days=base.weekday())
        return this_start, this_start + timedelta(days=7), this_start - timedelta(days=7)
    if period == "month":
        this_start = base.replace(day=1)
        return this_start, _add_month(this_start), _sub_month(this_start)
    this_start = base.replace(month=1, day=1)  # year
    last_start = this_start.replace(year=this_start.year - 1)
    next_start = this_start.replace(year=this_start.year + 1)
    return this_start, next_start, last_start


def _trend(
    rows: list[ActivityRow],
    this_start: datetime,
    this_end: datetime,
    period: Period,
) -> list[TrendPoint]:
    if period == "year":
        totals = [0.0] * 12
        for r in rows:
            totals[_local_naive(r).month - 1] += r["distance_m"]
        return [TrendPoint(label=_MONTH_LABELS[i], value=round(totals[i], 1)) for i in range(12)]

    n_days = (this_end.date() - this_start.date()).days
    totals = [0.0] * n_days
    for r in rows:
        idx = (_local_naive(r).date() - this_start.date()).days
        if 0 <= idx < n_days:
            totals[idx] += r["distance_m"]
    if period == "week":
        labels = _WEEKDAY_LABELS
    else:  # month — day-of-month numbers
        labels = [str((this_start.date() + timedelta(days=i)).day) for i in range(n_days)]
    return [TrendPoint(label=labels[i], value=round(totals[i], 1)) for i in range(n_days)]


def _summary(rows: list[ActivityRow]) -> OverviewSummary:
    speeds = [r["avg_speed_ms"] for r in rows if r["avg_speed_ms"] is not None]
    return OverviewSummary(
        rides=len(rows),
        prs=sum(1 for r in rows if r.get("is_pr")),
        top_speed_ms=max(speeds) if speeds else None,
        longest_ride_m=max((r["distance_m"] for r in rows), default=0.0),
        max_elev_m=max((r["elev_gain_m"] for r in rows), default=0.0),
    )


def _ride_types(rows: list[ActivityRow]) -> list[RideTypeCount]:
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["type"]] = counts.get(r["type"], 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [RideTypeCount(type=t, count=c) for t, c in ordered]


def _heatmap(rows: list[ActivityRow], year: int) -> HeatmapData:
    by_day: dict[str, float] = {}
    for r in rows:
        d = _local_naive(r)
        if d.year != year:
            continue
        key = d.date().isoformat()
        by_day[key] = by_day.get(key, 0.0) + r["distance_m"]
    days = [
        HeatmapDay(date=k, distance_m=round(v, 1))
        for k, v in sorted(by_day.items())
        if v > 0
    ]
    return HeatmapData(year=year, days=days)


def get_overview(
    supabase: Client,
    athlete_id: int,
    *,
    tz: str = "UTC",
    period: Period = "week",
    now: datetime | None = None,
) -> OverviewResponse:
    zone = _resolve_tz(tz)
    now_local = (now or datetime.now(UTC)).astimezone(zone)
    base = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    this_start, this_end, last_start = _period_bounds(base, period)
    year_start = base.replace(month=1, day=1)
    week_start = base - timedelta(days=base.weekday())

    # One widened query feeds the period totals, the current-week distance, and the
    # full-year heatmap. Query by UTC start_date (can sit ~14h off local), so go back
    # an extra day and filter precisely by local time below.
    query_start = min(year_start, last_start) - timedelta(days=1)
    rows = activities_db.list_activities_since(
        supabase, athlete_id, query_start.isoformat()
    )

    ts, te, ls = (
        this_start.replace(tzinfo=None),
        this_end.replace(tzinfo=None),
        last_start.replace(tzinfo=None),
    )
    this_rows = [r for r in rows if ts <= _local_naive(r) < te]
    last_rows = [r for r in rows if ls <= _local_naive(r) < ts]
    ws, we = week_start.replace(tzinfo=None), (week_start + timedelta(days=7)).replace(tzinfo=None)
    week_distance_m = sum(r["distance_m"] for r in rows if ws <= _local_naive(r) < we)

    recent = activities_db.list_recent_activities(supabase, athlete_id, RECENT_LIMIT)
    recent_rides = [
        RecentRideItem(
            id=r["id"], name=r["name"], type=r["type"], start_date=r["start_date"],
            start_date_local=r.get("start_date_local"), distance_m=r["distance_m"],
            moving_time_s=r["moving_time_s"], is_pr=bool(r.get("is_pr")),
        )
        for r in recent
    ]

    return OverviewResponse(
        period=period,
        this_period=_totals(this_rows),
        last_period=_totals(last_rows),
        trend=_trend(this_rows, this_start, this_end, period),
        summary=_summary(this_rows),
        ride_types=_ride_types(this_rows),
        recent_rides=recent_rides,
        heatmap=_heatmap(rows, base.year),
        week_distance_m=week_distance_m,
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
