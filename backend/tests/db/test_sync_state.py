import respx
from app.db import sync_state
from httpx import Response
from supabase import create_client

CLIENT = create_client("https://proj.supabase.co", "svc")


@respx.mock
def test_get_sync_state_returns_row():
    respx.route(method="GET", path="/rest/v1/sync_state").mock(
        return_value=Response(
            200,
            json=[{"athlete_id": 7, "status": "idle", "progress": 100,
                   "last_backfill_at": "T1", "last_sync_at": "T2",
                   "last_webhook_event_id": None}],
        )
    )
    row = sync_state.get_sync_state(CLIENT, 7)
    assert row is not None and row["status"] == "idle"


@respx.mock
def test_get_sync_state_none_when_empty():
    respx.route(method="GET", path="/rest/v1/sync_state").mock(
        return_value=Response(200, json=[])
    )
    assert sync_state.get_sync_state(CLIENT, 7) is None


@respx.mock
def test_upsert_sync_state_merges_and_includes_fields():
    route = respx.route(method="POST", path="/rest/v1/sync_state").mock(
        return_value=Response(201, json=[])
    )
    sync_state.upsert_sync_state(CLIENT, 7, {"status": "backfilling", "progress": 0})
    req = route.calls.last.request
    assert req.url.params["on_conflict"] == "athlete_id"
    assert b'"status": "backfilling"' in req.content or b'"status":"backfilling"' in req.content
    assert b'"athlete_id": 7' in req.content or b'"athlete_id":7' in req.content
    assert "merge-duplicates" in req.headers.get("prefer", "")
