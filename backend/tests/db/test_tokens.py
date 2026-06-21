from datetime import UTC, datetime

import respx
from app.db import tokens
from httpx import Response
from supabase import create_client

CLIENT = create_client("https://proj.supabase.co", "svc")


@respx.mock
def test_upsert_tokens_merges_on_athlete_id():
    route = respx.route(method="POST", path="/rest/v1/strava_tokens").mock(
        return_value=Response(201, json=[])
    )
    tokens.upsert_tokens(
        CLIENT, 7, "AT", "RT", datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
    )
    req = route.calls.last.request
    assert req.url.params["on_conflict"] == "athlete_id"
    assert b'"access_token": "AT"' in req.content or b'"access_token":"AT"' in req.content
    assert b'"expires_at": "2026-06-21T12:00:00+00:00"' in req.content or \
        b'"expires_at":"2026-06-21T12:00:00+00:00"' in req.content
    assert "merge-duplicates" in req.headers.get("prefer", "")


@respx.mock
def test_get_tokens_returns_row():
    respx.route(method="GET", path="/rest/v1/strava_tokens").mock(
        return_value=Response(
            200,
            json=[{"athlete_id": 7, "access_token": "AT", "refresh_token": "RT",
                   "expires_at": "2026-06-21T12:00:00+00:00"}],
        )
    )
    row = tokens.get_tokens(CLIENT, 7)
    assert row is not None and row["access_token"] == "AT"


@respx.mock
def test_get_tokens_none_when_empty():
    respx.route(method="GET", path="/rest/v1/strava_tokens").mock(
        return_value=Response(200, json=[])
    )
    assert tokens.get_tokens(CLIENT, 7) is None
