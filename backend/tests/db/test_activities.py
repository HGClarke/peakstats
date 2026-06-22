import respx
from app.db import activities
from httpx import Response
from supabase import create_client

CLIENT = create_client("https://proj.supabase.co", "svc")


@respx.mock
def test_upsert_activities_posts_rows_with_merge():
    route = respx.route(method="POST", path="/rest/v1/activities").mock(
        return_value=Response(201, json=[])
    )
    activities.upsert_activities(CLIENT, [{"id": 1, "athlete_id": 7, "name": "Ride"}])
    req = route.calls.last.request
    assert req.url.params["on_conflict"] == "id"
    assert "merge-duplicates" in req.headers.get("prefer", "")
    assert b'"id": 1' in req.content or b'"id":1' in req.content


@respx.mock
def test_upsert_activities_noop_on_empty():
    route = respx.route(method="POST", path="/rest/v1/activities").mock(
        return_value=Response(201, json=[])
    )
    activities.upsert_activities(CLIENT, [])
    assert not route.called


@respx.mock
def test_count_activities_reads_exact_count():
    respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(200, json=[{"id": 1}], headers={"Content-Range": "0-0/42"})
    )
    assert activities.count_activities(CLIENT, 7) == 42


@respx.mock
def test_count_activities_zero_when_empty():
    respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(200, json=[], headers={"Content-Range": "*/0"})
    )
    assert activities.count_activities(CLIENT, 7) == 0


@respx.mock
def test_list_activities_since_filters_and_orders():
    route = respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(200, json=[{"id": 1, "athlete_id": 7, "name": "Ride"}])
    )
    rows = activities.list_activities_since(CLIENT, 7, "2026-06-08T00:00:00+00:00")
    params = route.calls.last.request.url.params
    assert params["athlete_id"] == "eq.7"
    assert params["start_date"] == "gte.2026-06-08T00:00:00+00:00"
    assert params["order"] == "start_date.asc"
    assert rows == [{"id": 1, "athlete_id": 7, "name": "Ride"}]


@respx.mock
def test_list_recent_activities_orders_desc_and_limits():
    route = respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(200, json=[{"id": 9, "athlete_id": 7, "name": "Ride"}])
    )
    rows = activities.list_recent_activities(CLIENT, 7, limit=5)
    params = route.calls.last.request.url.params
    assert params["athlete_id"] == "eq.7"
    assert params["order"] == "start_date.desc"
    assert params["limit"] == "5"
    assert rows == [{"id": 9, "athlete_id": 7, "name": "Ride"}]


@respx.mock
def test_list_activities_filtered_builds_query_and_reads_count():
    route = respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(
            200,
            json=[{"id": 9, "athlete_id": 7, "name": "Ride"}],
            headers={"Content-Range": "0-8/42"},
        )
    )
    rows, total = activities.list_activities_filtered(
        CLIENT, 7,
        q="loop", min_dist=1000.0, min_time=600, min_elev=50.0,
        order="distance_m.desc,id.desc",
        as_of="2026-06-21T12:00:00+00:00",
        offset=0, limit=9,
    )
    req = route.calls.last.request
    params = req.url.params
    assert params["athlete_id"] == "eq.7"
    assert params["created_at"] == "lte.2026-06-21T12:00:00+00:00"
    assert "ilike" in params["name"] and "loop" in params["name"]
    assert params["distance_m"] == "gte.1000.0"
    assert params["moving_time_s"] == "gte.600"
    assert params["elev_gain_m"] == "gte.50.0"
    assert params["order"] == "distance_m.desc,id.desc"
    # postgrest paginates via offset/limit query params (offset=start,
    # limit=end-start+1) plus a Prefer: count=exact header for the total.
    assert params["offset"] == "0"
    assert params["limit"] == "9"
    assert req.headers["prefer"] == "count=exact"
    assert total == 42
    assert rows == [{"id": 9, "athlete_id": 7, "name": "Ride"}]


@respx.mock
def test_list_activities_filtered_omits_empty_filters():
    route = respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(200, json=[], headers={"Content-Range": "*/0"})
    )
    rows, total = activities.list_activities_filtered(
        CLIENT, 7,
        q=None, min_dist=None, min_time=None, min_elev=None,
        order="start_date.desc,id.desc",
        as_of="2026-06-21T12:00:00+00:00",
        offset=0, limit=9,
    )
    params = route.calls.last.request.url.params
    assert "name" not in params
    assert "distance_m" not in params
    assert "moving_time_s" not in params
    assert "elev_gain_m" not in params
    assert total == 0
    assert rows == []


@respx.mock
def test_delete_activity_scopes_by_athlete_and_id():
    route = respx.route(method="DELETE", path="/rest/v1/activities").mock(
        return_value=Response(204)
    )
    activities.delete_activity(CLIENT, athlete_id=7, activity_id=123)
    params = route.calls.last.request.url.params
    assert params["id"] == "eq.123"
    assert params["athlete_id"] == "eq.7"


@respx.mock
def test_list_activities_needing_detail_filters_null():
    route = respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(200, json=[{"id": 3, "athlete_id": 7, "name": "Ride"}])
    )
    rows = activities.list_activities_needing_detail(CLIENT, 7, limit=50)
    params = route.calls.last.request.url.params
    assert params["athlete_id"] == "eq.7"
    assert params["detail_fetched_at"] == "is.null"
    assert params["limit"] == "50"
    assert rows == [{"id": 3, "athlete_id": 7, "name": "Ride"}]


@respx.mock
def test_mark_detail_fetched_updates_row():
    route = respx.route(method="PATCH", path="/rest/v1/activities").mock(return_value=Response(204))
    activities.mark_detail_fetched(CLIENT, 3, [{"distance": 1000}], "2026-06-21T12:00:00+00:00")
    req = route.calls.last.request
    assert req.url.params["id"] == "eq.3"
    assert b"detail_fetched_at" in req.content


@respx.mock
def test_get_activity_scopes_to_athlete():
    route = respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(200, json=[{"id": 5, "athlete_id": 7, "name": "Ride"}]))
    row = activities.get_activity(CLIENT, 7, 5)
    params = route.calls.last.request.url.params
    assert params["id"] == "eq.5" and params["athlete_id"] == "eq.7"
    assert row is not None and row["id"] == 5


@respx.mock
def test_get_activity_none_when_missing():
    respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(200, json=[]))
    assert activities.get_activity(CLIENT, 7, 5) is None
