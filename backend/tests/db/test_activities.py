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


def test_list_activities_since_filters_and_orders():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=[{"id": 1, "athlete_id": 7, "name": "Ride"}])

    rows = activities.list_activities_since(
        _client(handler), 7, "2026-06-08T00:00:00+00:00"
    )
    assert seen["params"]["athlete_id"] == "eq.7"
    assert seen["params"]["start_date"] == "gte.2026-06-08T00:00:00+00:00"
    assert seen["params"]["order"] == "start_date.asc"
    assert rows == [{"id": 1, "athlete_id": 7, "name": "Ride"}]


def test_list_recent_activities_orders_desc_and_limits():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=[{"id": 9, "athlete_id": 7, "name": "Ride"}])

    rows = activities.list_recent_activities(_client(handler), 7, limit=5)
    assert seen["params"]["athlete_id"] == "eq.7"
    assert seen["params"]["order"] == "start_date.desc"
    assert seen["params"]["limit"] == "5"
    assert rows == [{"id": 9, "athlete_id": 7, "name": "Ride"}]


def test_delete_activity_scopes_by_athlete_and_id():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["params"] = dict(request.url.params)
        return httpx.Response(204)

    activities.delete_activity(_client(handler), athlete_id=7, activity_id=123)
    assert seen["method"] == "DELETE"
    assert seen["params"]["id"] == "eq.123"
    assert seen["params"]["athlete_id"] == "eq.7"
