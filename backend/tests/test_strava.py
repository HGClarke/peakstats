from datetime import UTC

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
    assert token.expires_at.tzinfo == UTC
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


def test_list_activities_sends_bearer_and_params():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/athlete/activities"
        assert request.headers["authorization"] == "Bearer AT"
        assert request.url.params["page"] == "2"
        assert request.url.params["per_page"] == "200"
        assert request.url.params["after"] == "1700000000"
        return httpx.Response(200, json=[{"id": 1}, {"id": 2}])

    acts = _client(handler).list_activities("AT", page=2, per_page=200, after=1_700_000_000)
    assert acts == [{"id": 1}, {"id": 2}]


def test_list_activities_omits_after_when_none():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "after" not in request.url.params
        return httpx.Response(200, json=[])

    assert _client(handler).list_activities("AT", page=1) == []


def test_get_activity_sends_bearer_and_path():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/activities/12345"
        assert request.headers["authorization"] == "Bearer AT"
        return httpx.Response(200, json={"id": 12345, "name": "Evening ride"})

    activity = _client(handler).get_activity("AT", 12345)
    assert activity["id"] == 12345
    assert activity["name"] == "Evening ride"


def test_create_push_subscription_posts_app_credentials():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = dict(httpx.QueryParams(request.content.decode()))
        return httpx.Response(201, json={"id": 42})

    sub_id = _client(handler).create_push_subscription(
        "https://api.example.com/webhooks/strava", "VT"
    )
    assert sub_id == 42
    assert seen["path"] == "/api/v3/push_subscriptions"
    assert seen["body"]["client_id"] == "cid"
    assert seen["body"]["client_secret"] == "secret"
    assert seen["body"]["callback_url"] == "https://api.example.com/webhooks/strava"
    assert seen["body"]["verify_token"] == "VT"


def test_list_push_subscriptions_sends_app_credentials():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/push_subscriptions"
        assert request.url.params["client_id"] == "cid"
        assert request.url.params["client_secret"] == "secret"
        return httpx.Response(200, json=[{"id": 42}])

    assert _client(handler).list_push_subscriptions() == [{"id": 42}]


def test_delete_push_subscription_targets_id_with_credentials():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["params"] = dict(request.url.params)
        return httpx.Response(204)

    _client(handler).delete_push_subscription(42)
    assert seen["method"] == "DELETE"
    assert seen["path"] == "/api/v3/push_subscriptions/42"
    assert seen["params"]["client_id"] == "cid"
    assert seen["params"]["client_secret"] == "secret"
