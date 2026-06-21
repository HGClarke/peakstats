from datetime import UTC, datetime

from app.services import activities as activities_service

NOW = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)  # Wednesday; week of Mon 2026-06-15

THIS_WEEK = [
    {"id": 1, "athlete_id": 7, "name": "Tue ride", "type": "Ride",
     "start_date": "2026-06-16T10:00:00Z", "distance_m": 10000.0,
     "moving_time_s": 1000, "elapsed_time_s": 1000, "elev_gain_m": 100.0,
     "avg_speed_ms": 10.0, "avg_hr": None, "summary_polyline": None},
    {"id": 2, "athlete_id": 7, "name": "Wed ride", "type": "Ride",
     "start_date": "2026-06-17T09:00:00Z", "distance_m": 20000.0,
     "moving_time_s": 2000, "elapsed_time_s": 2000, "elev_gain_m": 50.0,
     "avg_speed_ms": 10.0, "avg_hr": None, "summary_polyline": None},
]
LAST_WEEK = [
    {"id": 3, "athlete_id": 7, "name": "Last week", "type": "Ride",
     "start_date": "2026-06-10T10:00:00Z", "distance_m": 5000.0,
     "moving_time_s": 500, "elapsed_time_s": 500, "elev_gain_m": 10.0,
     "avg_speed_ms": 10.0, "avg_hr": None, "summary_polyline": None},
]


def _patch(monkeypatch, since_rows, recent_rows):
    monkeypatch.setattr(activities_service.activities_db, "list_activities_since",
                        lambda supabase, athlete_id, since_iso: since_rows)
    monkeypatch.setattr(activities_service.activities_db, "list_recent_activities",
                        lambda supabase, athlete_id, limit: recent_rows)


def test_overview_aggregates_this_and_last_week(monkeypatch):
    _patch(monkeypatch, THIS_WEEK + LAST_WEEK, THIS_WEEK)
    ov = activities_service.get_overview(object(), 7, now=NOW)
    assert ov.this_week.distance_m == 30000.0
    assert ov.this_week.elev_gain_m == 150.0
    assert ov.this_week.moving_time_s == 3000
    assert ov.this_week.avg_speed_ms == 10.0
    assert ov.last_week.distance_m == 5000.0
    assert ov.last_week.elev_gain_m == 10.0
    assert ov.last_week.moving_time_s == 500
    assert ov.last_week.avg_speed_ms == 10.0


def test_overview_week_buckets_by_weekday(monkeypatch):
    _patch(monkeypatch, THIS_WEEK + LAST_WEEK, [])
    ov = activities_service.get_overview(object(), 7, now=NOW)
    assert [w.day for w in ov.week] == ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    km = {w.day: w.km for w in ov.week}
    assert km["TUE"] == 10.0
    assert km["WED"] == 20.0
    assert km["MON"] == 0.0
    assert km["SUN"] == 0.0


def test_overview_recent_rides_mapped(monkeypatch):
    _patch(monkeypatch, [], THIS_WEEK)
    ov = activities_service.get_overview(object(), 7, now=NOW)
    assert [r.id for r in ov.recent_rides] == [1, 2]
    assert ov.recent_rides[0].name == "Tue ride"
    assert ov.recent_rides[0].distance_m == 10000.0
    assert ov.recent_rides[0].moving_time_s == 1000
    assert ov.recent_rides[0].type == "Ride"


def test_overview_empty_is_safe(monkeypatch):
    _patch(monkeypatch, [], [])
    ov = activities_service.get_overview(object(), 7, now=NOW)
    assert ov.this_week.distance_m == 0.0
    assert ov.this_week.avg_speed_ms is None
    assert ov.recent_rides == []
    assert all(w.km == 0.0 for w in ov.week)


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
        object(), 7, tz="America/Los_Angeles", now=NOW
    )
    km = {w.day: w.km for w in ov.week}
    assert km["SAT"] == 12.0
    assert km["SUN"] == 0.0


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
        object(), 7, tz="America/Los_Angeles", now=NOW
    )
    assert ov.this_week.distance_m == 0.0
    assert ov.last_week.distance_m == 5000.0


def test_overview_invalid_tz_falls_back_to_utc(monkeypatch):
    _patch(monkeypatch, THIS_WEEK + LAST_WEEK, [])
    ov = activities_service.get_overview(object(), 7, tz="Not/AZone", now=NOW)
    # Same result as the existing UTC-default aggregation test.
    assert ov.this_week.distance_m == 30000.0
    assert ov.last_week.distance_m == 5000.0


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
    ov = activities_service.get_overview(object(), 7, now=NOW)
    assert ov.recent_rides[0].start_date_local == "2026-06-20T23:00:00Z"
