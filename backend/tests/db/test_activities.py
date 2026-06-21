import httpx
from app.db import activities


def _client(handler) -> httpx.Client:
    return httpx.Client(
        base_url="https://proj.supabase.co/rest/v1",
        headers={"apikey": "svc", "Authorization": "Bearer svc",
                 "Content-Type": "application/json"},
        transport=httpx.MockTransport(handler),
    )


def test_upsert_activities_posts_rows_with_merge():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["prefer"] = request.headers.get("prefer")
        seen["body"] = request.read().decode()
        return httpx.Response(201, json=[])

    rows = [{"id": 1, "athlete_id": 7, "name": "Ride"}]
    activities.upsert_activities(_client(handler), rows)
    assert seen["url"] == "https://proj.supabase.co/rest/v1/activities?on_conflict=id"
    assert seen["prefer"] == "resolution=merge-duplicates"
    assert '"id":1' in seen["body"]


def test_upsert_activities_noop_on_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not POST for empty rows")

    activities.upsert_activities(_client(handler), [])


def test_count_activities_parses_content_range():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["athlete_id"] == "eq.7"
        assert request.headers["prefer"] == "count=exact"
        return httpx.Response(200, json=[], headers={"Content-Range": "0-0/42"})

    assert activities.count_activities(_client(handler), 7) == 42


def test_count_activities_handles_star_range():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[], headers={"Content-Range": "*/0"})

    assert activities.count_activities(_client(handler), 7) == 0
