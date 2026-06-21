from app.models.activities import (
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
                        lambda supabase, athlete_id: _overview())
    _auth(client)
    response = client.get("/activities/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["this_week"]["distance_m"] == 30000.0
    assert len(body["week"]) == 7
    assert body["recent_rides"][0]["name"] == "Tue ride"
