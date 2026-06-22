import respx
from app.db import segments
from httpx import Response
from supabase import create_client

CLIENT = create_client("https://proj.supabase.co", "svc")


@respx.mock
def test_upsert_segments_merges_on_id():
    route = respx.route(method="POST", path="/rest/v1/segments").mock(
        return_value=Response(201, json=[])
    )
    segments.upsert_segments(
        CLIENT,
        [{"id": 5, "name": "Hill", "distance_m": 1200.0, "avg_grade": 4.8}],
    )
    assert route.calls.last.request.url.params["on_conflict"] == "id"
    assert "merge-duplicates" in route.calls.last.request.headers.get("prefer", "")


@respx.mock
def test_upsert_segments_noop_on_empty():
    route = respx.route(method="POST", path="/rest/v1/segments").mock(
        return_value=Response(201, json=[])
    )
    segments.upsert_segments(CLIENT, [])
    assert not route.called


@respx.mock
def test_upsert_segment_efforts_merges_on_id():
    route = respx.route(method="POST", path="/rest/v1/segment_efforts").mock(
        return_value=Response(201, json=[])
    )
    segments.upsert_segment_efforts(CLIENT, [{"id": 9, "segment_id": 5, "athlete_id": 7,
        "activity_id": 1, "elapsed_time_s": 100, "avg_watts": None, "avg_hr": None,
        "avg_speed_ms": 12.0, "start_date": "2026-06-21T08:00:00Z", "is_best": False}])
    assert route.calls.last.request.url.params["on_conflict"] == "id"


@respx.mock
def test_get_effort_keys_scopes_by_athlete_and_segment():
    route = respx.route(method="GET", path="/rest/v1/segment_efforts").mock(
        return_value=Response(200, json=[{"id": 9, "elapsed_time_s": 100, "start_date": "T"}])
    )
    rows = segments.get_effort_keys(CLIENT, 7, 5)
    params = route.calls.last.request.url.params
    assert params["athlete_id"] == "eq.7"
    assert params["segment_id"] == "eq.5"
    assert rows == [{"id": 9, "elapsed_time_s": 100, "start_date": "T"}]


@respx.mock
def test_set_is_best_clears_then_sets():
    patches = respx.route(method="PATCH", path="/rest/v1/segment_efforts").mock(
        return_value=Response(204)
    )
    segments.set_is_best(CLIENT, 7, 5, best_id=9)
    # two PATCHes: clear all for (athlete,segment), then set the winner by id
    assert patches.call_count == 2
    clear, winner = patches.calls[0].request, patches.calls[1].request
    assert clear.url.params["athlete_id"] == "eq.7"
    assert clear.url.params["segment_id"] == "eq.5"
    assert winner.url.params["id"] == "eq.9"


@respx.mock
def test_list_athlete_efforts_embeds_segment():
    route = respx.route(method="GET", path="/rest/v1/segment_efforts").mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 9,
                    "segment_id": 5,
                    "elapsed_time_s": 100,
                    "start_date": "T",
                    "segments": {"name": "Hill", "distance_m": 1200.0, "avg_grade": 4.8},
                }
            ],
        )
    )
    rows = segments.list_athlete_efforts(CLIENT, 7)
    params = route.calls.last.request.url.params
    assert params["athlete_id"] == "eq.7"
    assert "segments(" in params["select"]
    assert rows[0]["segments"]["name"] == "Hill"


@respx.mock
def test_get_segment_returns_first_or_none():
    respx.route(method="GET", path="/rest/v1/segments").mock(
        return_value=Response(
            200,
            json=[{"id": 5, "name": "Hill", "distance_m": 1200.0, "avg_grade": 4.8}],
        )
    )
    assert segments.get_segment(CLIENT, 5)["name"] == "Hill"


@respx.mock
def test_get_segment_none_when_missing():
    respx.route(method="GET", path="/rest/v1/segments").mock(return_value=Response(200, json=[]))
    assert segments.get_segment(CLIENT, 5) is None


@respx.mock
def test_list_segment_efforts_embeds_activity_and_orders_desc():
    route = respx.route(method="GET", path="/rest/v1/segment_efforts").mock(
        return_value=Response(200, json=[{"id": 9, "activity_id": 1, "elapsed_time_s": 100,
            "start_date": "T", "avg_watts": None, "avg_hr": None, "avg_speed_ms": 12.0,
            "is_best": True, "activities": {"name": "River loop"}}])
    )
    rows = segments.list_segment_efforts(CLIENT, 7, 5)
    params = route.calls.last.request.url.params
    assert params["athlete_id"] == "eq.7"
    assert params["segment_id"] == "eq.5"
    assert params["order"] == "start_date.desc"
    assert "activities(" in params["select"]
    assert rows[0]["activities"]["name"] == "River loop"
