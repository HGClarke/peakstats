import respx
from app.db import metrics
from httpx import Response
from supabase import create_client

CLIENT = create_client("https://proj.supabase.co", "svc")


@respx.mock
def test_get_metrics_returns_row_or_none():
    respx.route(method="GET", path="/rest/v1/activity_metrics").mock(
        return_value=Response(200, json=[{"activity_id": 5, "athlete_id": 7,
                                          "avg_power_w": 180.0, "np_w": 195.0, "work_kj": 720.0,
                                          "power_hist": [1.0], "hr_hist": None,
                                          "has_power": True, "has_hr": False}])
    )
    row = metrics.get_metrics(CLIENT, 5)
    assert row is not None and row["avg_power_w"] == 180.0 and row["has_power"] is True


@respx.mock
def test_get_metrics_none_when_missing():
    respx.route(method="GET", path="/rest/v1/activity_metrics").mock(
        return_value=Response(200, json=[]))
    assert metrics.get_metrics(CLIENT, 5) is None


@respx.mock
def test_upsert_metrics_merges_on_activity_id():
    route = respx.route(method="POST", path="/rest/v1/activity_metrics").mock(
        return_value=Response(201, json=[]))
    metrics.upsert_metrics(CLIENT, {"activity_id": 5, "athlete_id": 7,
                                    "avg_power_w": None, "np_w": None, "work_kj": None,
                                    "power_hist": None, "hr_hist": None,
                                    "has_power": False, "has_hr": False})
    req = route.calls.last.request
    assert req.url.params["on_conflict"] == "activity_id"
    assert "merge-duplicates" in req.headers.get("prefer", "")


def test_list_metrics_for_activities_empty_ids_skips_query():
    # No respx route registered: an HTTP call would raise. Empty ids must short-circuit.
    assert metrics.list_metrics_for_activities(CLIENT, 7, []) == []


@respx.mock
def test_list_metrics_for_activities_filters_by_ids():
    route = respx.route(method="GET", path="/rest/v1/activity_metrics").mock(
        return_value=Response(200, json=[{"activity_id": 1, "athlete_id": 7,
                                          "avg_power_w": 1.0, "np_w": None, "work_kj": None,
                                          "power_hist": [2.0], "hr_hist": None,
                                          "has_power": True, "has_hr": False}]))
    rows = metrics.list_metrics_for_activities(CLIENT, 7, [1, 2])
    assert [r["activity_id"] for r in rows] == [1]
    assert "in.(1,2)" in route.calls.last.request.url.params["activity_id"]


@respx.mock
def test_list_activity_ids_needing_metrics_returns_difference():
    respx.route(method="GET", path="/rest/v1/activities").mock(
        return_value=Response(200, json=[{"id": 1}, {"id": 2}, {"id": 3}]))
    respx.route(method="GET", path="/rest/v1/activity_metrics").mock(
        return_value=Response(200, json=[{"activity_id": 2}]))
    assert metrics.list_activity_ids_needing_metrics(CLIENT, 7) == [1, 3]
