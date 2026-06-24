from datetime import UTC, datetime

from app.services import activities as activities_service

NOW = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)  # Wednesday; week of Mon 2026-06-15


# ---------------------------------------------------------------------------
# RPC mock helpers
# ---------------------------------------------------------------------------

def _week_trend(values: dict[str, float] | None = None) -> list[dict]:
    """7-element week trend, optionally overriding specific day values."""
    labels = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    v = values or {}
    return [{"label": lbl, "value": v.get(lbl, 0.0)} for lbl in labels]


def _month_trend(n_days: int = 30, values: dict[int, float] | None = None) -> list[dict]:
    v = values or {}
    return [
        {"label": f"W{i // 7 + 1}" if i % 7 == 0 else "", "value": v.get(i, 0.0)}
        for i in range(n_days)
    ]


def _year_trend(values: dict[int, float] | None = None) -> list[dict]:
    labels = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    v = values or {}
    return [{"label": lbl, "value": v.get(i, 0.0)} for i, lbl in enumerate(labels)]


def _make_row(**overrides: object) -> dict:
    """Minimal valid RPC row (all zero/empty defaults)."""
    row: dict = {
        "this_dist_m": 0.0, "this_elev_m": 0.0, "this_time_s": 0, "this_speed_ms": None,
        "last_dist_m": 0.0, "last_elev_m": 0.0, "last_time_s": 0, "last_speed_ms": None,
        "rides": 0, "prs": 0, "top_speed_ms": None, "top_avg_power_w": None,
        "longest_ride_m": 0.0, "max_elev_m": 0.0,
        "week_dist_m": 0.0, "heatmap_year": 2026,
        "ride_types": [], "recent_rides": [], "heatmap_days": [],
        "trend": _week_trend(),
        "this_activity_ids": [],
    }
    row.update(overrides)
    return row


def _patch(monkeypatch, rpc_row: dict, *, settings=None, metrics=None):
    monkeypatch.setattr(activities_service.activities_db, "get_overview_rpc",
                        lambda *a, **kw: rpc_row)
    monkeypatch.setattr(activities_service.athletes_db, "get_athlete",
                        lambda supabase, athlete_id: {"settings": settings or {}})
    monkeypatch.setattr(activities_service.metrics_db, "list_metrics_for_activities",
                        lambda supabase, athlete_id, ids: metrics or [])


# ---------------------------------------------------------------------------
# Period totals
# ---------------------------------------------------------------------------

def test_week_totals_and_deltas(monkeypatch):
    row = _make_row(
        this_dist_m=30000.0, this_elev_m=150.0, this_time_s=3000, this_speed_ms=10.0,
        last_dist_m=5000.0,
    )
    _patch(monkeypatch, row)
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.period == "week"
    assert ov.this_period.distance_m == 30000.0
    assert ov.this_period.elev_gain_m == 150.0
    assert ov.this_period.moving_time_s == 3000
    assert ov.this_period.avg_speed_ms == 10.0
    assert ov.last_period.distance_m == 5000.0


# ---------------------------------------------------------------------------
# Trend
# ---------------------------------------------------------------------------

def test_week_trend_buckets_by_weekday(monkeypatch):
    row = _make_row(trend=_week_trend({"TUE": 10000.0, "WED": 20000.0}))
    _patch(monkeypatch, row)
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert [p.label for p in ov.trend] == ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    by_label = {p.label: p.value for p in ov.trend}
    assert by_label["TUE"] == 10000.0
    assert by_label["WED"] == 20000.0
    assert by_label["MON"] == 0.0


def test_month_trend_is_daily_with_week_labels(monkeypatch):
    # June 2026 has 30 days; verify the service passes trend through faithfully
    trend = _month_trend(30, {0: 5000.0})  # June 1 (W1) has 5 000 m
    row = _make_row(trend=trend, this_dist_m=5000.0, last_dist_m=9000.0)
    _patch(monkeypatch, row)
    ov = activities_service.get_overview(object(), 7, period="month", now=NOW)
    assert len(ov.trend) == 30
    assert ov.trend[0].value == 5000.0
    assert ov.trend[0].label == "W1"
    assert ov.trend[1].label == ""
    assert [ov.trend[i].label for i in (0, 7, 14, 21, 28)] == ["W1", "W2", "W3", "W4", "W5"]
    assert ov.this_period.distance_m == 5000.0
    assert ov.last_period.distance_m == 9000.0


def test_year_trend_is_twelve_months(monkeypatch):
    trend = _year_trend({5: 10000.0})  # June bucket
    row = _make_row(trend=trend, this_dist_m=10000.0, last_dist_m=3000.0)
    _patch(monkeypatch, row)
    ov = activities_service.get_overview(object(), 7, period="year", now=NOW)
    assert [p.label for p in ov.trend] == ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                                            "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    assert ov.trend[5].value == 10000.0
    assert ov.this_period.distance_m == 10000.0
    assert ov.last_period.distance_m == 3000.0


# ---------------------------------------------------------------------------
# Summary and ride types
# ---------------------------------------------------------------------------

def test_summary_and_ride_types(monkeypatch):
    row = _make_row(
        rides=2, prs=1, top_speed_ms=10.0, longest_ride_m=20000.0, max_elev_m=100.0,
        ride_types=[{"type": "Ride", "count": 1}, {"type": "VirtualRide", "count": 1}],
    )
    _patch(monkeypatch, row)
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.summary.rides == 2
    assert ov.summary.prs == 1
    assert ov.summary.top_speed_ms == 10.0
    assert ov.summary.longest_ride_m == 20000.0
    assert ov.summary.max_elev_m == 100.0
    assert {rt.type: rt.count for rt in ov.ride_types} == {"Ride": 1, "VirtualRide": 1}


def test_top_avg_power_is_max_over_period(monkeypatch):
    _patch(monkeypatch, _make_row(top_avg_power_w=245.0))
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.summary.top_avg_power_w == 245.0


def test_top_avg_power_none_when_no_power(monkeypatch):
    _patch(monkeypatch, _make_row(top_avg_power_w=None))
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.summary.top_avg_power_w is None


# ---------------------------------------------------------------------------
# Recent rides
# ---------------------------------------------------------------------------

def test_recent_rides_include_pr_flag(monkeypatch):
    rides = [
        {"id": 2, "name": "Ride 2", "type": "VirtualRide",
         "start_date": "2026-06-17T09:00:00Z", "start_date_local": "2026-06-17T09:00:00",
         "distance_m": 20000.0, "moving_time_s": 2000, "is_pr": True},
        {"id": 1, "name": "Ride 1", "type": "Ride",
         "start_date": "2026-06-16T10:00:00Z", "start_date_local": "2026-06-16T10:00:00",
         "distance_m": 10000.0, "moving_time_s": 1000, "is_pr": False},
    ]
    _patch(monkeypatch, _make_row(recent_rides=rides))
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert [r.id for r in ov.recent_rides] == [2, 1]
    assert ov.recent_rides[0].is_pr is True
    assert ov.recent_rides[1].is_pr is False


def test_overview_recent_ride_exposes_start_date_local(monkeypatch):
    rides = [{"id": 70, "name": "Has local", "type": "Ride",
              "start_date": "2026-06-21T06:00:00Z",
              "start_date_local": "2026-06-20T23:00:00Z",
              "distance_m": 1000.0, "moving_time_s": 100, "is_pr": False}]
    _patch(monkeypatch, _make_row(recent_rides=rides))
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.recent_rides[0].start_date_local == "2026-06-20T23:00:00Z"


# ---------------------------------------------------------------------------
# Heatmap and week distance
# ---------------------------------------------------------------------------

def test_heatmap_buckets_current_year_active_days(monkeypatch):
    days = [{"date": "2026-01-02", "distance_m": 20000.0}]
    _patch(monkeypatch, _make_row(heatmap_year=2026, heatmap_days=days))
    ov = activities_service.get_overview(object(), 7, period="year", now=NOW)
    assert ov.heatmap.year == 2026
    assert {d.date: d.distance_m for d in ov.heatmap.days} == {"2026-01-02": 20000.0}


def test_week_distance_is_current_week_regardless_of_period(monkeypatch):
    for period in ("week", "month", "year"):
        _patch(monkeypatch, _make_row(week_dist_m=30000.0))
        ov = activities_service.get_overview(object(), 7, period=period, now=NOW)
        assert ov.week_distance_m == 30000.0


def test_heatmap_and_week_distance_empty_safe(monkeypatch):
    _patch(monkeypatch, _make_row())
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.heatmap.days == []
    assert ov.heatmap.year == 2026
    assert ov.week_distance_m == 0.0


# ---------------------------------------------------------------------------
# Empty / zero state
# ---------------------------------------------------------------------------

def test_empty_is_safe(monkeypatch):
    _patch(monkeypatch, _make_row())
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.this_period.distance_m == 0.0
    assert ov.this_period.avg_speed_ms is None
    assert ov.summary.rides == 0
    assert ov.summary.top_speed_ms is None
    assert ov.summary.longest_ride_m == 0.0
    assert ov.ride_types == []


# ---------------------------------------------------------------------------
# Invalid timezone falls back to UTC (validated before reaching the RPC)
# ---------------------------------------------------------------------------

def test_overview_invalid_tz_falls_back_to_utc(monkeypatch):
    called_with = {}
    def fake_rpc(supabase, athlete_id, period, now_utc, timezone):
        called_with["timezone"] = timezone
        return _make_row()
    monkeypatch.setattr(activities_service.activities_db, "get_overview_rpc", fake_rpc)
    monkeypatch.setattr(activities_service.athletes_db, "get_athlete",
                        lambda *a: {"settings": {}})
    monkeypatch.setattr(activities_service.metrics_db, "list_metrics_for_activities",
                        lambda *a, **kw: [])
    activities_service.get_overview(object(), 7, tz="Not/AZone", period="week", now=NOW)
    assert called_with["timezone"] == "UTC"


# ---------------------------------------------------------------------------
# list_activities (unchanged — kept to detect regressions)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Power / HR zones (still computed in Python from activity_metrics)
# ---------------------------------------------------------------------------

def test_period_zones_unset_without_ftp_or_hr_max(monkeypatch):
    _patch(monkeypatch, _make_row())
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.power_zones.unset is True
    assert ov.hr_zones.unset is True


def test_period_zones_buckets_from_summed_histograms(monkeypatch):
    # ftp=200 → Z1 [0,110); midpoint of bin 5 = 55 W → Z1. 9 weighted seconds.
    phist = [0.0] * 150
    phist[5] = 9.0
    met = [{"activity_id": 20, "athlete_id": 7, "avg_power_w": 100.0, "np_w": None,
            "work_kj": None, "power_hist": phist, "hr_hist": None,
            "has_power": True, "has_hr": False}]
    _patch(monkeypatch, _make_row(this_activity_ids=[20]),
           settings={"ftp_w": 200}, metrics=met)
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.power_zones.unset is False
    by_z = {b.z: b for b in ov.power_zones.buckets}
    assert by_z["Z1"].seconds == 9 and by_z["Z1"].pct == 100.0
    assert ov.hr_zones.unset is True   # hr_max still missing


def test_period_zones_configured_but_no_data_is_zeroed(monkeypatch):
    _patch(monkeypatch, _make_row(),
           settings={"ftp_w": 200, "hr_max": 190}, metrics=[])
    ov = activities_service.get_overview(object(), 7, period="week", now=NOW)
    assert ov.power_zones.unset is False
    assert all(b.seconds == 0 for b in ov.power_zones.buckets)
    assert ov.hr_zones.unset is False
    assert len(ov.hr_zones.buckets) == 5
