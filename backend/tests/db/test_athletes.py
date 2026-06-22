import respx
from app.db import athletes
from httpx import Response
from supabase import create_client

CLIENT = create_client("https://proj.supabase.co", "svc")


@respx.mock
def test_upsert_athlete_merges_on_id():
    route = respx.route(method="POST", path="/rest/v1/athletes").mock(
        return_value=Response(201, json=[])
    )
    athletes.upsert_athlete(CLIENT, 7, "Ada", "http://x/a.png")
    req = route.calls.last.request
    assert req.url.params["on_conflict"] == "id"
    assert b'"id": 7' in req.content or b'"id":7' in req.content
    assert "merge-duplicates" in req.headers.get("prefer", "")


@respx.mock
def test_get_athlete_returns_first_row():
    respx.route(method="GET", path="/rest/v1/athletes").mock(
        return_value=Response(
            200, json=[{"id": 7, "name": "Ada", "avatar_url": None, "settings": {}}]
        )
    )
    row = athletes.get_athlete(CLIENT, 7)
    assert row == {"id": 7, "name": "Ada", "avatar_url": None, "settings": {}}


@respx.mock
def test_get_athlete_none_when_empty():
    respx.route(method="GET", path="/rest/v1/athletes").mock(
        return_value=Response(200, json=[])
    )
    assert athletes.get_athlete(CLIENT, 7) is None


@respx.mock
def test_delete_athlete_scopes_by_id():
    route = respx.route(method="DELETE", path="/rest/v1/athletes").mock(
        return_value=Response(204)
    )
    athletes.delete_athlete(CLIENT, 7)
    assert route.calls.last.request.url.params["id"] == "eq.7"


@respx.mock
def test_update_settings_writes_and_scopes_by_id():
    route = respx.route(method="PATCH", path="/rest/v1/athletes").mock(
        return_value=Response(
            200,
            json=[{
                "id": 7, "name": "Ada", "avatar_url": None,
                "settings": {"units": "imperial", "theme": "dark", "default_period": "week"},
            }],
        )
    )
    row = athletes.update_settings(
        CLIENT, 7,
        {"units": "imperial", "theme": "dark", "default_period": "week"},
    )
    req = route.calls.last.request
    assert req.url.params["id"] == "eq.7"
    assert b'"units": "imperial"' in req.content or b'"units":"imperial"' in req.content
    assert row["settings"]["units"] == "imperial"
