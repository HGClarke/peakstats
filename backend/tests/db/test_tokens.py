import json
from datetime import datetime, timezone

import httpx

from app.db import tokens


def _client(handler) -> httpx.Client:
    return httpx.Client(
        base_url="https://proj.supabase.co/rest/v1",
        headers={"apikey": "svc", "Authorization": "Bearer svc",
                 "Content-Type": "application/json"},
        transport=httpx.MockTransport(handler),
    )


def test_upsert_tokens_serializes_expiry_iso():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.read().decode()
        return httpx.Response(201, json=[])

    tokens.upsert_tokens(_client(handler), 7, "AT", "RT",
                         datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert seen["url"] == "https://proj.supabase.co/rest/v1/strava_tokens?on_conflict=athlete_id"
    body = json.loads(seen["body"])
    assert body[0]["access_token"] == "AT"
    assert body[0]["expires_at"] == "2024-01-01T00:00:00+00:00"


def test_get_tokens_returns_first_row_or_none():
    def found(request: httpx.Request) -> httpx.Response:
        assert request.url.params["athlete_id"] == "eq.7"
        return httpx.Response(200, json=[{"athlete_id": 7, "access_token": "AT"}])

    assert tokens.get_tokens(_client(found), 7) == {"athlete_id": 7, "access_token": "AT"}

    def empty(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    assert tokens.get_tokens(_client(empty), 7) is None
