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


def test_list_activities_filtered_builds_params_and_parses_total():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        seen["prefer"] = request.headers.get("prefer")
        seen["range"] = request.headers.get("range")
        return httpx.Response(
            200,
            json=[{"id": 9, "athlete_id": 7, "name": "Ride"}],
            headers={"Content-Range": "0-8/42"},
        )

    rows, total = activities.list_activities_filtered(
        _client(handler), 7,
        q="loop", min_dist=1000.0, min_time=600, min_elev=50.0,
        order="distance_m.desc,id.desc",
        as_of="2026-06-21T12:00:00+00:00",
        offset=0, limit=9,
    )
    p = seen["params"]
    assert p["athlete_id"] == "eq.7"
    assert p["created_at"] == "lte.2026-06-21T12:00:00+00:00"
    assert p["name"] == "ilike.*loop*"
    assert p["distance_m"] == "gte.1000.0"
    assert p["moving_time_s"] == "gte.600"
    assert p["elev_gain_m"] == "gte.50.0"
    assert p["order"] == "distance_m.desc,id.desc"
    assert p["select"] == "*"
    assert seen["prefer"] == "count=exact"
    assert seen["range"] == "0-8"
    assert total == 42
    assert rows == [{"id": 9, "athlete_id": 7, "name": "Ride"}]


def test_list_activities_filtered_omits_empty_filters():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=[], headers={"Content-Range": "*/0"})

    rows, total = activities.list_activities_filtered(
        _client(handler), 7,
        q=None, min_dist=None, min_time=None, min_elev=None,
        order="start_date.desc,id.desc",
        as_of="2026-06-21T12:00:00+00:00",
        offset=0, limit=9,
    )
    p = seen["params"]
    assert "name" not in p
    assert "distance_m" not in p
    assert "moving_time_s" not in p
    assert "elev_gain_m" not in p
    assert total == 0
    assert rows == []
