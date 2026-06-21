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
