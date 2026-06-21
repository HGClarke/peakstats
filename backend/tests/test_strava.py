from datetime import timezone

import httpx

from app.strava import StravaClient


def _client(handler) -> StravaClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return StravaClient(http, "cid", "secret", "http://localhost:8000/auth/strava/callback")


def test_authorize_url_has_scope_state_and_redirect():
    url = _client(lambda req: httpx.Response(200)).authorize_url("xyz")
    assert url.startswith("https://www.strava.com/oauth/authorize?")
    assert "client_id=cid" in url
    assert "scope=read%2Cactivity%3Aread_all" in url
    assert "state=xyz" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fauth%2Fstrava%2Fcallback" in url
    assert "response_type=code" in url


def test_exchange_code_parses_token_and_athlete():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/oauth/token"
        body = dict(httpx.QueryParams(request.content.decode()))
        assert body["grant_type"] == "authorization_code"
        assert body["code"] == "abc"
        assert body["client_id"] == "cid"
        assert body["client_secret"] == "secret"
        return httpx.Response(
            200,
            json={
                "access_token": "AT", "refresh_token": "RT", "expires_at": 1_700_000_000,
                "athlete": {"id": 99, "firstname": "Ada", "lastname": "Lovelace",
                            "profile": "http://img/a.png"},
            },
        )

    token = _client(handler).exchange_code("abc")
    assert token.access_token == "AT"
    assert token.refresh_token == "RT"
    assert token.expires_at.tzinfo == timezone.utc
    assert int(token.expires_at.timestamp()) == 1_700_000_000
    assert token.athlete["id"] == 99


def test_refresh_parses_token():
    def handler(request: httpx.Request) -> httpx.Response:
        body = dict(httpx.QueryParams(request.content.decode()))
        assert body["grant_type"] == "refresh_token"
        assert body["refresh_token"] == "RT"
        return httpx.Response(200, json={"access_token": "AT2", "refresh_token": "RT2",
                                         "expires_at": 1_700_003_600})

    token = _client(handler).refresh("RT")
    assert token.access_token == "AT2"
    assert token.refresh_token == "RT2"
    assert token.athlete == {}


def test_deauthorize_posts_access_token():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = dict(httpx.QueryParams(request.content.decode()))
        return httpx.Response(200, json={})

    _client(handler).deauthorize("AT")
    assert seen["path"] == "/oauth/deauthorize"
    assert seen["body"]["access_token"] == "AT"
