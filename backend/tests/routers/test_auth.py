from app.services import auth as auth_service
from app.session import SESSION_COOKIE, STATE_COOKIE, read_session


def test_login_redirects_to_strava_and_sets_state_cookie(client, monkeypatch):
    monkeypatch.setattr(
        auth_service, "start_login",
        lambda strava: ("https://www.strava.com/oauth/authorize?state=abc", "abc"),
    )
    response = client.get("/auth/strava/login", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].startswith("https://www.strava.com/oauth/authorize")
    assert STATE_COOKIE in response.cookies


def test_callback_valid_state_sets_session_and_redirects(client, monkeypatch):
    monkeypatch.setattr(auth_service, "handle_callback",
                        lambda code, supabase, strava: 99)
    client.cookies.set(STATE_COOKIE, "abc123")
    response = client.get(
        "/auth/strava/callback?code=thecode&state=abc123", follow_redirects=False
    )
    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:5173/app"
    assert read_session(response.cookies[SESSION_COOKIE], "test-secret") == 99


def test_callback_mismatched_state_redirects_to_error(client, monkeypatch):
    called = {"v": False}
    monkeypatch.setattr(auth_service, "handle_callback",
                        lambda *a, **k: called.update(v=True))
    client.cookies.set(STATE_COOKIE, "abc123")
    response = client.get(
        "/auth/strava/callback?code=thecode&state=WRONG", follow_redirects=False
    )
    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:5173/?auth=error"
    assert called["v"] is False


def test_callback_strava_error_redirects_to_error(client):
    response = client.get(
        "/auth/strava/callback?error=access_denied", follow_redirects=False
    )
    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:5173/?auth=error"


def test_logout_clears_session_cookie(client):
    response = client.post("/auth/logout")
    assert response.status_code == 204
    assert "ps_session=" in response.headers.get("set-cookie", "")
