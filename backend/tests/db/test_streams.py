import respx
from app.db import streams
from httpx import Response
from supabase import create_client

CLIENT = create_client("https://proj.supabase.co", "svc")


@respx.mock
def test_get_streams_returns_row_or_none():
    respx.route(method="GET", path="/rest/v1/activity_streams").mock(
        return_value=Response(200, json=[{"activity_id": 5, "athlete_id": 7,
                                          "data": {"watts": [1, 2]},
                                          "resolution": "high", "point_count": 2}])
    )
    row = streams.get_streams(CLIENT, 5)
    assert row is not None and row["point_count"] == 2 and row["data"] == {"watts": [1, 2]}


@respx.mock
def test_get_streams_none_when_missing():
    respx.route(method="GET", path="/rest/v1/activity_streams").mock(
        return_value=Response(200, json=[])
    )
    assert streams.get_streams(CLIENT, 5) is None


@respx.mock
def test_upsert_streams_posts_with_merge():
    route = respx.route(method="POST", path="/rest/v1/activity_streams").mock(
        return_value=Response(201, json=[])
    )
    streams.upsert_streams(CLIENT, {"activity_id": 5, "athlete_id": 7,
                                    "data": {}, "resolution": "high", "point_count": 0})
    req = route.calls.last.request
    assert req.url.params["on_conflict"] == "activity_id"
    assert "merge-duplicates" in req.headers.get("prefer", "")
