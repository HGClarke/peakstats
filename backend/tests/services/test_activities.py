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
