from app.models.athlete import AthleteResponse
from app.services import athletes as athletes_service
from app.session import SESSION_COOKIE, sign_session


def _auth(client):
    client.cookies.set(SESSION_COOKIE, sign_session(99, "test-secret"))


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


def test_patch_settings_requires_session(client):
    assert client.patch("/athlete/settings", json={"units": "imperial"}).status_code == 401


def test_patch_settings_updates_and_returns_profile(client, monkeypatch):
    monkeypatch.setattr(
        athletes_service, "update_settings",
        lambda supabase, athlete_id, patch: AthleteResponse(
            id=athlete_id, name="Ada", avatar_url=None,
            settings={"units": patch.units, "theme": "dark", "default_period": "week"}),
    )
    client.cookies.set(SESSION_COOKIE, sign_session(99, "test-secret"))
    res = client.patch("/athlete/settings", json={"units": "imperial"})
    assert res.status_code == 200
    assert res.json()["settings"]["units"] == "imperial"


def test_patch_settings_404_when_missing(client, monkeypatch):
    monkeypatch.setattr(athletes_service, "update_settings",
                        lambda supabase, athlete_id, patch: None)
    client.cookies.set(SESSION_COOKIE, sign_session(99, "test-secret"))
    assert client.patch("/athlete/settings", json={"theme": "light"}).status_code == 404


def test_patch_settings_rejects_empty_body(client):
    client.cookies.set(SESSION_COOKIE, sign_session(99, "test-secret"))
    assert client.patch("/athlete/settings", json={}).status_code == 422


def test_patch_settings_rejects_bad_enum(client):
    client.cookies.set(SESSION_COOKIE, sign_session(99, "test-secret"))
    assert client.patch("/athlete/settings", json={"units": "furlongs"}).status_code == 422


def test_patch_settings_accepts_ftp_and_hr(client, monkeypatch):
    from app.services import athletes as athletes_service
    captured = {}

    def fake(supabase, athlete_id, patch):
        captured["ftp"] = patch.ftp_w
        captured["hr"] = patch.hr_max
        from app.models.athlete import AthleteResponse
        return AthleteResponse(id=athlete_id, name="A", avatar_url=None,
                               settings={"ftp_w": patch.ftp_w, "hr_max": patch.hr_max})

    monkeypatch.setattr(athletes_service, "update_settings", fake)
    _auth(client)
    r = client.patch("/athlete/settings", json={"ftp_w": 280, "hr_max": 190})
    assert r.status_code == 200 and captured == {"ftp": 280, "hr": 190}


def test_patch_settings_accepts_weekly_goal(client, monkeypatch):
    from app.services import athletes as athletes_service
    captured = {}

    def fake(supabase, athlete_id, patch):
        captured["goal"] = patch.weekly_goal_m
        from app.models.athlete import AthleteResponse
        return AthleteResponse(id=athlete_id, name="A", avatar_url=None,
                               settings={"weekly_goal_m": patch.weekly_goal_m})

    monkeypatch.setattr(athletes_service, "update_settings", fake)
    _auth(client)
    r = client.patch("/athlete/settings", json={"weekly_goal_m": 120000})
    assert r.status_code == 200 and captured == {"goal": 120000}
