from datetime import datetime, timezone

from app.services import auth
from app.strava import StravaToken


class FakeStrava:
    def __init__(self) -> None:
        self.token = StravaToken("AT", "RT", datetime(2099, 1, 1, tzinfo=timezone.utc),
                                 {"id": 99, "firstname": "Ada", "lastname": "Lovelace",
                                  "profile": "http://img/a.png"})

    def authorize_url(self, state: str) -> str:
        return f"https://www.strava.com/oauth/authorize?state={state}"

    def exchange_code(self, code: str) -> StravaToken:
        return self.token


def test_start_login_returns_url_and_matching_state():
    url, state = auth.start_login(FakeStrava())
    assert state
    assert f"state={state}" in url


def test_handle_callback_upserts_and_returns_athlete_id(monkeypatch):
    calls = {}
    monkeypatch.setattr(
        auth.athletes_db, "upsert_athlete",
        lambda client, athlete_id, name, avatar_url: calls.update(
            athlete=(athlete_id, name, avatar_url)),
    )
    monkeypatch.setattr(
        auth.tokens_db, "upsert_tokens",
        lambda client, athlete_id, access_token, refresh_token, expires_at: calls.update(
            tokens=(athlete_id, access_token, refresh_token)),
    )

    athlete_id = auth.handle_callback("abc", supabase=object(), strava=FakeStrava())

    assert athlete_id == 99
    assert calls["athlete"] == (99, "Ada Lovelace", "http://img/a.png")
    assert calls["tokens"] == (99, "AT", "RT")
