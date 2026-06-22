from datetime import UTC, datetime

from app.models.activities import (
    ActivityListItem,
    ActivityListResponse,
    ActivityStreamsResponse,
    OverviewResponse,
    RecentRideItem,
    WeekDay,
    WeekTotals,
)
from app.services import activities as activities_service
from app.session import SESSION_COOKIE, sign_session


def _auth(client):
    client.cookies.set(SESSION_COOKIE, sign_session(99, "test-secret"))


def _overview() -> OverviewResponse:
    return OverviewResponse(
        this_week=WeekTotals(distance_m=30000.0, elev_gain_m=150.0,
                             moving_time_s=3000, avg_speed_ms=10.0),
        last_week=WeekTotals(distance_m=5000.0, elev_gain_m=10.0,
                             moving_time_s=500, avg_speed_ms=10.0),
        week=[WeekDay(day=d, km=0.0) for d in
              ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")],
        recent_rides=[RecentRideItem(id=1, name="Tue ride", type="Ride",
                                     start_date="2026-06-16T10:00:00Z",
                                     distance_m=10000.0, moving_time_s=1000)],
    )


def test_overview_requires_session(client):
    assert client.get("/activities/overview").status_code == 401


def test_overview_returns_body(client, monkeypatch):
    monkeypatch.setattr(activities_service, "get_overview",
                        lambda supabase, athlete_id, tz="UTC": _overview())
    _auth(client)
    response = client.get("/activities/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["this_week"]["distance_m"] == 30000.0
    assert len(body["week"]) == 7
    assert body["recent_rides"][0]["name"] == "Tue ride"


def test_overview_forwards_tz(client, monkeypatch):
    seen = {}

    def fake(supabase, athlete_id, tz="UTC"):
        seen["tz"] = tz
        return _overview()

    monkeypatch.setattr(activities_service, "get_overview", fake)
    _auth(client)
    response = client.get("/activities/overview?tz=America/Los_Angeles")
    assert response.status_code == 200
    assert seen["tz"] == "America/Los_Angeles"


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
