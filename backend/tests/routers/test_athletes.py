from app.models.athlete import AthleteResponse
from app.services import athletes as athletes_service
from app.session import SESSION_COOKIE, sign_session


def test_athlete_requires_session(client):
    assert client.get("/athlete").status_code == 401


def test_athlete_bad_cookie_is_unauthorized(client):
    client.cookies.set(SESSION_COOKIE, "garbage")
    assert client.get("/athlete").status_code == 401


def test_athlete_returns_profile_for_valid_session(client, monkeypatch):
    monkeypatch.setattr(
        athletes_service, "get_profile",
        lambda supabase, athlete_id: AthleteResponse(
            id=athlete_id, name="Ada Lovelace", avatar_url="http://img/a.png",
            settings={"units": "metric", "theme": "dark", "default_period": "week"}),
    )
    client.cookies.set(SESSION_COOKIE, sign_session(99, "test-secret"))
    response = client.get("/athlete")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 99
    assert body["name"] == "Ada Lovelace"
    assert body["settings"]["units"] == "metric"


def test_athlete_404_when_profile_missing(client, monkeypatch):
    monkeypatch.setattr(athletes_service, "get_profile",
                        lambda supabase, athlete_id: None)
    client.cookies.set(SESSION_COOKIE, sign_session(99, "test-secret"))
    assert client.get("/athlete").status_code == 404


def test_disconnect_requires_session(client):
    assert client.delete("/athlete/connection").status_code == 401


def test_disconnect_calls_service_and_clears_cookie(client, monkeypatch):
    called = {}
    monkeypatch.setattr(athletes_service, "disconnect",
                        lambda supabase, strava, athlete_id: called.update(id=athlete_id))
    client.cookies.set(SESSION_COOKIE, sign_session(99, "test-secret"))
    response = client.delete("/athlete/connection")
    assert response.status_code == 204
    assert called["id"] == 99
    assert "ps_session=" in response.headers.get("set-cookie", "")
