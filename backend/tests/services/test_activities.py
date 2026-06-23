from datetime import UTC, datetime

from app.services import activities as activities_service

NOW = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)  # Wednesday; week of Mon 2026-06-15


def _row(id, date_local, dist, time, elev, speed, type="Ride", is_pr=False):
    return {
        "id": id, "athlete_id": 7, "name": f"Ride {id}", "type": type,
        "start_date": date_local + "Z", "start_date_local": date_local,
        "distance_m": dist, "moving_time_s": time, "elapsed_time_s": time,
        "elev_gain_m": elev, "avg_speed_ms": speed, "avg_hr": None,
        "summary_polyline": None, "is_pr": is_pr,
    }


THIS_WEEK = [
    _row(1, "2026-06-16T10:00:00", 10000.0, 1000, 100.0, 10.0),
    _row(2, "2026-06-17T09:00:00", 20000.0, 2000, 50.0, 8.0, type="VirtualRide", is_pr=True),
]
LAST_WEEK = [_row(3, "2026-06-10T10:00:00", 5000.0, 500, 10.0, 6.0)]


def _patch(monkeypatch, since_rows, recent_rows):
    monkeypatch.setattr(activities_service.activities_db, "list_activities_since",
                        lambda supabase, athlete_id, since_iso: since_rows)
    monkeypatch.setattr(activities_service.activities_db, "list_recent_activities",
                        lambda supabase, athlete_id, limit: recent_rows)


def test_week_totals_and_deltas(monkeypatch):
    _patch(monkeypatch, THIS_WEEK + LAST_WEEK, THIS_WEEK)
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.period == "week"
    assert ov.this_period.distance_m == 30000.0
    assert ov.this_period.elev_gain_m == 150.0
    assert ov.this_period.moving_time_s == 3000
    assert ov.this_period.avg_speed_ms == 10.0  # 30000m / 3000s
    assert ov.last_period.distance_m == 5000.0


def test_week_trend_buckets_by_weekday(monkeypatch):
    _patch(monkeypatch, THIS_WEEK + LAST_WEEK, [])
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert [p.label for p in ov.trend] == ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    by_label = {p.label: p.value for p in ov.trend}
    assert by_label["TUE"] == 10000.0
    assert by_label["WED"] == 20000.0
    assert by_label["MON"] == 0.0


def test_summary_and_ride_types(monkeypatch):
    _patch(monkeypatch, THIS_WEEK + LAST_WEEK, [])
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.summary.rides == 2
    assert ov.summary.prs == 1
    assert ov.summary.top_speed_ms == 10.0
    assert ov.summary.longest_ride_m == 20000.0
    assert ov.summary.max_elev_m == 100.0
    assert {rt.type: rt.count for rt in ov.ride_types} == {"Ride": 1, "VirtualRide": 1}


def test_recent_rides_include_pr_flag(monkeypatch):
    _patch(monkeypatch, [], THIS_WEEK)
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert [r.id for r in ov.recent_rides] == [1, 2]
    assert ov.recent_rides[1].is_pr is True
    assert ov.recent_rides[0].is_pr is False


def test_month_trend_is_daily_for_calendar_month(monkeypatch):
    rows = [_row(1, "2026-06-01T10:00:00", 5000.0, 600, 0.0, 8.0),
            _row(2, "2026-05-31T10:00:00", 9000.0, 600, 0.0, 8.0)]  # last month
    _patch(monkeypatch, rows, [])
    ov = activities_service.get_overview(object(), 7, period="month", now=NOW)
    assert len(ov.trend) == 30          # June has 30 days
    assert ov.trend[0].label == "1"
    assert ov.trend[0].value == 5000.0
    assert ov.this_period.distance_m == 5000.0
    assert ov.last_period.distance_m == 9000.0


def test_year_trend_is_twelve_months(monkeypatch):
    rows = [_row(1, "2026-06-16T10:00:00", 10000.0, 1000, 0.0, 8.0),
            _row(2, "2025-06-16T10:00:00", 3000.0, 1000, 0.0, 8.0)]  # last year
    _patch(monkeypatch, rows, [])
    ov = activities_service.get_overview(object(), 7, period="year", now=NOW)
    assert [p.label for p in ov.trend] == ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                                           "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    assert ov.trend[5].value == 10000.0  # JUN
    assert ov.this_period.distance_m == 10000.0
    assert ov.last_period.distance_m == 3000.0


def test_empty_is_safe(monkeypatch):
    _patch(monkeypatch, [], [])
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.this_period.distance_m == 0.0
    assert ov.this_period.avg_speed_ms is None
    assert ov.summary.rides == 0
    assert ov.summary.top_speed_ms is None
    assert ov.summary.longest_ride_m == 0.0
    assert ov.ride_types == []


LIST_ROWS = [
    {"id": 2, "athlete_id": 7, "name": "Wed ride", "type": "Ride",
     "start_date": "2026-06-17T09:00:00Z", "distance_m": 20000.0,
     "moving_time_s": 2000, "elapsed_time_s": 2000, "elev_gain_m": 50.0,
     "avg_speed_ms": 10.0, "avg_hr": None, "summary_polyline": None},
]


def _patch_list(monkeypatch, rows, total):
    captured = {}

    def fake(supabase, athlete_id, **kwargs: object) -> tuple:
        captured.update(kwargs)
        captured["athlete_id"] = athlete_id
        return rows, total

    monkeypatch.setattr(activities_service.activities_db,
                        "list_activities_filtered", fake)
    return captured


def test_list_builds_order_and_offset(monkeypatch):
    cap = _patch_list(monkeypatch, LIST_ROWS, 42)
    resp = activities_service.list_activities(
        object(), 7, q="loop", min_dist=1000.0, min_time=600, min_elev=50.0,
        sort="distance", direction="asc", page=3, as_of=NOW,
    )
    assert cap["order"] == "distance_m.asc,id.asc"
    assert cap["offset"] == 18  # (3 - 1) * 9
    assert cap["limit"] == 9
    assert cap["q"] == "loop"
    assert cap["as_of"] == NOW.isoformat()
    assert resp.page == 3
    assert resp.page_size == 9
    assert resp.total == 42
    assert resp.total_pages == 5  # ceil(42 / 9)
    assert resp.as_of == NOW
    assert resp.activities[0].id == 2
    assert resp.activities[0].avg_speed_ms == 10.0


def test_list_speed_sort_is_nullslast(monkeypatch):
    cap = _patch_list(monkeypatch, [], 0)
    activities_service.list_activities(
        object(), 7, q=None, min_dist=None, min_time=None, min_elev=None,
        sort="speed", direction="desc", page=1, as_of=NOW,
    )
    assert cap["order"] == "avg_speed_ms.desc.nullslast,id.desc"


def test_list_defaults_as_of_to_now(monkeypatch):
    cap = _patch_list(monkeypatch, [], 0)
    resp = activities_service.list_activities(
        object(), 7, q=None, min_dist=None, min_time=None, min_elev=None,
        sort="date", direction="desc", page=1,
    )
    assert cap["as_of"]  # an ISO timestamp was passed through
    assert resp.total_pages == 1  # max(1, ceil(0 / 9))
    assert resp.as_of is not None


def test_overview_buckets_by_local_day_not_utc(monkeypatch):
    # 11pm Sat 2026-06-20 in LA == 2026-06-21T06:00:00Z (Sun UTC).
    # Local time must place it on Saturday, not Sunday.
    ride = {
        "id": 50, "athlete_id": 7, "name": "Late ride", "type": "Ride",
        "start_date": "2026-06-21T06:00:00Z",
        "start_date_local": "2026-06-20T23:00:00Z",
        "distance_m": 12000.0, "moving_time_s": 1200, "elapsed_time_s": 1200,
        "elev_gain_m": 0.0, "avg_speed_ms": 10.0, "avg_hr": None,
        "summary_polyline": None,
    }
    _patch(monkeypatch, [ride], [])
    ov = activities_service.get_overview(
        object(), 7, tz="America/Los_Angeles", period="week", now=NOW
    )
    vals = {p.label: p.value for p in ov.trend}
    assert vals["SAT"] == 12000.0
    assert vals["SUN"] == 0.0


def test_overview_window_uses_tz(monkeypatch):
    # A ride at 2026-06-15T02:00:00Z is Mon 02:00 UTC, but Sun 19:00 in LA —
    # i.e. last week in LA, this week in UTC.
    ride = {
        "id": 60, "athlete_id": 7, "name": "Boundary", "type": "Ride",
        "start_date": "2026-06-15T02:00:00Z",
        "start_date_local": "2026-06-14T19:00:00Z",
        "distance_m": 5000.0, "moving_time_s": 500, "elapsed_time_s": 500,
        "elev_gain_m": 0.0, "avg_speed_ms": 10.0, "avg_hr": None,
        "summary_polyline": None,
    }
    _patch(monkeypatch, [ride], [])
    ov = activities_service.get_overview(
        object(), 7, tz="America/Los_Angeles", period="week", now=NOW
    )
    assert ov.this_period.distance_m == 0.0
    assert ov.last_period.distance_m == 5000.0


def test_overview_invalid_tz_falls_back_to_utc(monkeypatch):
    _patch(monkeypatch, THIS_WEEK + LAST_WEEK, [])
    ov = activities_service.get_overview(
        object(), 7, tz="Not/AZone", period="week", now=NOW
    )
    # Same result as the existing UTC-default aggregation test.
    assert ov.this_period.distance_m == 30000.0
    assert ov.last_period.distance_m == 5000.0


def test_overview_recent_ride_exposes_start_date_local(monkeypatch):
    ride = {
        "id": 70, "athlete_id": 7, "name": "Has local", "type": "Ride",
        "start_date": "2026-06-21T06:00:00Z",
        "start_date_local": "2026-06-20T23:00:00Z",
        "distance_m": 1000.0, "moving_time_s": 100, "elapsed_time_s": 100,
        "elev_gain_m": 0.0, "avg_speed_ms": 10.0, "avg_hr": None,
        "summary_polyline": None,
    }
    _patch(monkeypatch, [], [ride])
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.recent_rides[0].start_date_local == "2026-06-20T23:00:00Z"
