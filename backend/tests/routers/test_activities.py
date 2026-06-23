from datetime import UTC, datetime

from app.models.activities import (
    ActivityDetailResponse,
    ActivityListItem,
    ActivityListResponse,
    ActivityStreamsResponse,
    HeatmapData,
    OverviewResponse,
    OverviewSummary,
    PeriodTotals,
    RecentRideItem,
    TrendPoint,
)
from app.services import activities as activities_service
from app.session import SESSION_COOKIE, sign_session


def _auth(client):
    client.cookies.set(SESSION_COOKIE, sign_session(99, "test-secret"))


def _overview() -> OverviewResponse:
    return OverviewResponse(
        period="week",
        this_period=PeriodTotals(distance_m=30000.0, elev_gain_m=150.0,
                                 moving_time_s=3000, avg_speed_ms=10.0),
        last_period=PeriodTotals(distance_m=5000.0, elev_gain_m=10.0,
                                 moving_time_s=500, avg_speed_ms=10.0),
        trend=[TrendPoint(label=d, value=0.0) for d in
               ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")],
        summary=OverviewSummary(rides=1, prs=0, top_speed_ms=10.0,
                                longest_ride_m=10000.0, max_elev_m=100.0),
        ride_types=[],
        recent_rides=[RecentRideItem(id=1, name="Tue ride", type="Ride",
                                     start_date="2026-06-16T10:00:00Z",
                                     distance_m=10000.0, moving_time_s=1000)],
        heatmap=HeatmapData(year=2026, days=[]),
        week_distance_m=30000.0,
    )


def test_overview_requires_session(client):
    assert client.get("/activities/overview").status_code == 401


def test_overview_returns_body(client, monkeypatch):
    monkeypatch.setattr(activities_service, "get_overview",
                        lambda supabase, athlete_id, tz="UTC", period="week": _overview())
    _auth(client)
    response = client.get("/activities/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["this_period"]["distance_m"] == 30000.0
    assert len(body["trend"]) == 7
    assert body["recent_rides"][0]["name"] == "Tue ride"


def test_overview_forwards_tz(client, monkeypatch):
    seen = {}

    def fake(supabase, athlete_id, tz="UTC", period="week"):
        seen["tz"] = tz
        return _overview()

    monkeypatch.setattr(activities_service, "get_overview", fake)
    _auth(client)
    response = client.get("/activities/overview?tz=America/Los_Angeles")
    assert response.status_code == 200
    assert seen["tz"] == "America/Los_Angeles"


def test_overview_passes_period(client, monkeypatch):
    captured = {}

    def fake_overview(supabase, athlete_id, *, tz="UTC", period="week", now=None):
        captured["tz"] = tz
        captured["period"] = period
        from app.models.activities import (
            HeatmapData,
            OverviewResponse,
            OverviewSummary,
            PeriodTotals,
        )
        zero = PeriodTotals(distance_m=0, elev_gain_m=0, moving_time_s=0, avg_speed_ms=None)
        return OverviewResponse(
            period=period, this_period=zero, last_period=zero, trend=[],
            summary=OverviewSummary(rides=0, prs=0, top_speed_ms=None,
                                    longest_ride_m=0, max_elev_m=0),
            ride_types=[], recent_rides=[],
            heatmap=HeatmapData(year=2026, days=[]), week_distance_m=0.0,
        )

    monkeypatch.setattr("app.routers.activities.activities_service.get_overview", fake_overview)
    _auth(client)
    resp = client.get("/activities/overview?tz=UTC&period=month")
    assert resp.status_code == 200
    assert captured["period"] == "month"
    assert resp.json()["period"] == "month"


def test_overview_defaults_to_week(client, monkeypatch):
    captured = {}

    def fake_overview(supabase, athlete_id, *, tz="UTC", period="week", now=None):
        captured["period"] = period
        from app.models.activities import (
            HeatmapData,
            OverviewResponse,
            OverviewSummary,
            PeriodTotals,
        )
        zero = PeriodTotals(distance_m=0, elev_gain_m=0, moving_time_s=0, avg_speed_ms=None)
        return OverviewResponse(
            period=period, this_period=zero, last_period=zero, trend=[],
            summary=OverviewSummary(rides=0, prs=0, top_speed_ms=None,
                                    longest_ride_m=0, max_elev_m=0),
            ride_types=[], recent_rides=[],
            heatmap=HeatmapData(year=2026, days=[]), week_distance_m=0.0,
        )

    monkeypatch.setattr("app.routers.activities.activities_service.get_overview", fake_overview)
    _auth(client)
    resp = client.get("/activities/overview")
    assert resp.status_code == 200
    assert captured["period"] == "week"


def _list_response() -> ActivityListResponse:
    return ActivityListResponse(
        activities=[ActivityListItem(
            id=2, name="Wed ride", type="Ride", start_date="2026-06-17T09:00:00Z",
            distance_m=20000.0, moving_time_s=2000, elev_gain_m=50.0, avg_speed_ms=10.0,
        )],
        page=1, page_size=9, total=1, total_pages=1,
        as_of=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
    )


def test_list_requires_session(client):
    assert client.get("/activities").status_code == 401


def test_list_returns_body(client, monkeypatch):
    captured: dict = {}

    def fake(supabase, athlete_id, **kwargs: object) -> ActivityListResponse:
        captured.update(kwargs)
        return _list_response()

    monkeypatch.setattr(activities_service, "list_activities", fake)
    _auth(client)
    response = client.get("/activities?sort=distance&direction=asc&page=1&min_dist=1000")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["activities"][0]["name"] == "Wed ride"
    assert captured["sort"] == "distance"
    assert captured["direction"] == "asc"
    assert captured["min_dist"] == 1000.0


def test_list_rejects_bad_sort(client):
    _auth(client)
    assert client.get("/activities?sort=bogus").status_code == 422


def test_list_rejects_bad_as_of(client):
    _auth(client)
    assert client.get("/activities?as_of=not-a-date").status_code == 422


def test_streams_requires_session(client):
    assert client.get("/activities/5/streams").status_code == 401


def test_streams_returns_body(client, monkeypatch):
    monkeypatch.setattr(activities_service, "get_streams_payload",
        lambda supabase, strava, athlete_id, activity_id:
            ActivityStreamsResponse(point_count=2, time=[0, 1], distance=[0.0, 5.0],
                                    watts=[100, 200]))
    _auth(client)
    body = client.get("/activities/5/streams").json()
    assert body["point_count"] == 2 and body["watts"] == [100, 200]
    assert body["altitude"] is None


def _detail() -> ActivityDetailResponse:
    return ActivityDetailResponse(
        id=5, name="Gravel", type="Ride", start_date="2026-06-21T14:42:00Z",
        distance_m=84300.0, moving_time_s=11820, elev_gain_m=1284.0,
        avg_speed_ms=7.13, avg_power_w=198.0, normalized_power_w=221.0,
        work_kj=2342.0, avg_hr=148, summary_polyline="abc")


def test_detail_requires_session(client):
    assert client.get("/activities/5").status_code == 401


def test_detail_returns_body(client, monkeypatch):
    monkeypatch.setattr(activities_service, "get_detail",
        lambda supabase, strava, athlete_id, activity_id: _detail())
    _auth(client)
    body = client.get("/activities/5").json()
    assert body["name"] == "Gravel" and body["avg_hr"] == 148


def test_detail_404_when_missing(client, monkeypatch):
    def boom(*a: object, **k: object) -> None:
        raise activities_service.ActivityNotFoundError("nope")
    monkeypatch.setattr(activities_service, "get_detail", boom)
    _auth(client)
    assert client.get("/activities/5").status_code == 404
