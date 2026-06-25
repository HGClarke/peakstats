import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from math import ceil
from time import perf_counter
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from supabase import Client

from app.db import activities as activities_db
from app.db import athletes as athletes_db
from app.db import metrics as metrics_db
from app.db import streams as streams_db
from app.db.streams import StreamRow
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

_log = logging.getLogger(__name__)

PAGE_SIZE = 9
STREAM_KEYS = ["time", "distance", "altitude", "heartrate", "watts", "velocity_smooth"]

_SORT_COLUMNS: dict[SortField, str] = {
    "date": "start_date",
    "distance": "distance_m",
    "time": "moving_time_s",
    "elevation": "elev_gain_m",
    "speed": "avg_speed_ms",
}


def _resolve_tz(tz: str) -> str:
    """Return `tz` if it is a valid IANA zone name, otherwise 'UTC'."""
    try:
        ZoneInfo(tz)
        return tz
    except (ZoneInfoNotFoundError, ValueError):
        return "UTC"


def get_overview(
    supabase: Client,
    athlete_id: int,
    *,
    tz: str = "UTC",
    period: Period = "week",
    now: datetime | None = None,
) -> OverviewResponse:
    now_utc = now or datetime.now(UTC)
    validated_tz = _resolve_tz(tz)

    # RPC does all aggregation in Postgres; get_athlete is independent — run in parallel.
    with ThreadPoolExecutor(max_workers=2) as pool:
        future_row = pool.submit(
            activities_db.get_overview_rpc, supabase, athlete_id, period, now_utc, validated_tz
        )
        future_athlete = pool.submit(athletes_db.get_athlete, supabase, athlete_id)
        row = future_row.result()
        athlete_row = future_athlete.result()

    settings: dict = athlete_row.get("settings", {}) if athlete_row else {}
    this_ids = [int(x) for x in (row["this_activity_ids"] or [])]
    power_zones, hr_zones = _period_zones(supabase, athlete_id, this_ids, settings)

    return OverviewResponse(
        period=period,
        this_period=PeriodTotals(
            distance_m=row["this_dist_m"],
            elev_gain_m=row["this_elev_m"],
            moving_time_s=row["this_time_s"],
            avg_speed_ms=row["this_speed_ms"],
        ),
        last_period=PeriodTotals(
            distance_m=row["last_dist_m"],
            elev_gain_m=row["last_elev_m"],
            moving_time_s=row["last_time_s"],
            avg_speed_ms=row["last_speed_ms"],
        ),
        trend=[TrendPoint(**p) for p in row["trend"]],
        summary=OverviewSummary(
            rides=row["rides"],
            prs=row["prs"],
            top_speed_ms=row["top_speed_ms"],
            top_avg_power_w=row["top_avg_power_w"],
            longest_ride_m=row["longest_ride_m"],
            max_elev_m=row["max_elev_m"],
        ),
        ride_types=[RideTypeCount(type=rt["type"], count=rt["count"]) for rt in row["ride_types"]],
        recent_rides=[
            RecentRideItem(
                id=r["id"], name=r["name"], type=r["type"],
                start_date=r["start_date"], start_date_local=r.get("start_date_local"),
                distance_m=r["distance_m"], moving_time_s=r["moving_time_s"],
                is_pr=bool(r.get("is_pr")),
            )
            for r in row["recent_rides"]
        ],
        heatmap=HeatmapData(
            year=row["heatmap_year"],
            days=[HeatmapDay(date=d["date"], distance_m=d["distance_m"])
                  for d in row["heatmap_days"]],
        ),
        week_distance_m=row["week_dist_m"],
        power_zones=power_zones,
        hr_zones=hr_zones,
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
    *,
    existing: StreamRow | None,
) -> dict[str, list]:
    """Return stream data for the activity, fetching from Strava if `existing` is None.

    Callers are responsible for fetching `existing` via `streams_db.get_streams` —
    this lets `get_detail` pipeline that lookup in parallel with other DB reads.
    Stores a sentinel (empty data, point_count 0) on Strava miss so we never refetch.
    Always upserts activity_metrics so metrics stay current and self-heal.
    `data` is the flat object-of-arrays.
    """
    if existing is not None:
        data = existing["data"]
    else:
        token = get_valid_access_token(supabase, strava, athlete_id)
        data = strava.get_activity_streams(token, activity_id, STREAM_KEYS)
        point_count = len(data.get("time") or data.get("distance") or [])
        streams_db.upsert_streams(supabase, {
            "activity_id": activity_id, "athlete_id": athlete_id,
            "data": data, "resolution": "high", "point_count": point_count,
        })
        # Compute and persist metrics on first fetch only — stream data is immutable
        # so recomputing on every cache hit is pure overhead.
        _store_metrics(supabase, athlete_id, activity_id, data)
    return data


def _store_metrics(
    supabase: Client, athlete_id: int, activity_id: int, data: dict
) -> None:
    """Compute and upsert the compact activity_metrics row from a stream dict."""
    row = {"activity_id": activity_id, "athlete_id": athlete_id, **analysis.compute_metrics(data)}
    metrics_db.upsert_metrics(supabase, row)  # type: ignore[arg-type]


def get_streams_payload(
    supabase: Client,
    strava: StravaClient,
    athlete_id: int,
    activity_id: int,
) -> ActivityStreamsResponse:
    t0 = perf_counter()
    existing = streams_db.get_streams(supabase, activity_id)
    t_db = perf_counter()
    data = ensure_streams(supabase, strava, athlete_id, activity_id, existing=existing)
    t_streams = perf_counter()
    print(  # noqa: T201
        f"[TIMING] get_streams_payload {activity_id}: "
        f"get_streams={int((t_db - t0) * 1000)}ms "
        f"ensure={int((t_streams - t_db) * 1000)}ms "
        f"total={int((t_streams - t0) * 1000)}ms "
        f"cached={existing is not None}",
        flush=True,
    )
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


def _zones_from_hists(
    hists: list[list[float]], bin_w: int, zone_defs: list[dict]
) -> ZonesBlock:
    summed = [0.0] * len(hists[0])
    for h in hists:
        for i, s in enumerate(h):
            summed[i] += s
    secs = analysis.zone_seconds_from_histogram(summed, bin_w, zone_defs)
    buckets = [ZoneBucket(**b) for b in analysis.buckets_from_zone_seconds(secs, zone_defs)]
    return ZonesBlock(unset=False, avg=None, buckets=buckets)


def _period_zones(
    supabase: Client, athlete_id: int, this_ids: list[int], settings: dict
) -> tuple[ZonesBlock, ZonesBlock]:
    ftp = settings.get("ftp_w")
    hr_max = settings.get("hr_max")
    rows = (
        metrics_db.list_metrics_for_activities(supabase, athlete_id, this_ids)
        if (ftp or hr_max) else []
    )

    def block(active: int | None, key: str, bin_w: int, zone_defs: list[dict]) -> ZonesBlock:
        if not active:
            return ZonesBlock(unset=True)
        hists = [m[key] for m in rows if m.get(key)]  # type: ignore[literal-required]
        if not hists:
            return _zones_from_hists([[0.0] * 1], bin_w, zone_defs)  # zeroed buckets
        return _zones_from_hists(hists, bin_w, zone_defs)

    power = block(ftp, "power_hist", analysis.POWER_BIN_W,
                  analysis.power_zones(ftp) if ftp else [])
    hr = block(hr_max, "hr_hist", analysis.HR_BIN_BPM,
               analysis.hr_zones(hr_max) if hr_max else [])
    return power, hr


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
    t0 = perf_counter()

    # All four reads are independent — run them in parallel.
    with ThreadPoolExecutor(max_workers=4) as pool:
        future_row = pool.submit(activities_db.get_activity, supabase, athlete_id, activity_id)
        future_streams = pool.submit(streams_db.get_streams, supabase, activity_id)
        future_athlete = pool.submit(athletes_db.get_athlete, supabase, athlete_id)
        future_climbs = pool.submit(
            activities_db.list_activity_climbs, supabase, athlete_id, activity_id
        )
        row = future_row.result()
        existing = future_streams.result()
        athlete_row = future_athlete.result()
        raw_climbs = future_climbs.result()

    t_parallel = perf_counter()

    if row is None:
        raise ActivityNotFoundError(f"activity {activity_id} not found for athlete")
    data = ensure_streams(supabase, strava, athlete_id, activity_id, existing=existing)

    t_streams = perf_counter()
    time = data.get("time") or []
    watts = data.get("watts")
    hr = data.get("heartrate")
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
        for r in raw_climbs
        if r.get("segments") and r["segments"]["climb_category"] > 0
    ]
    climbs = [
        ClimbItem(name=c["name"], climb_category=c["climb_category"], distance_m=c["distance_m"],
                  avg_grade=c["avg_grade"], elev_gain_m=c["elev_gain_m"],
                  time_s=c["elapsed_time_s"], vam=c["vam"])
        for c in analysis.compute_climbs(climb_rows)
    ]
    t_total = perf_counter()
    print(  # noqa: T201
        f"[TIMING] get_detail {activity_id}: "
        f"parallel_reads={int((t_parallel - t0) * 1000)}ms "
        f"ensure_streams={int((t_streams - t_parallel) * 1000)}ms "
        f"total={int((t_total - t0) * 1000)}ms "
        f"streams_cached={existing is not None}",
        flush=True,
    )
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
