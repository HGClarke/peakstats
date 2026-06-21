import httpx
from app.db import sync_state


def _client(handler) -> httpx.Client:
    return httpx.Client(
        base_url="https://proj.supabase.co/rest/v1",
        headers={"apikey": "svc", "Authorization": "Bearer svc",
                 "Content-Type": "application/json"},
        transport=httpx.MockTransport(handler),
    )


def test_get_sync_state_returns_first_row_or_none():
    def found(request: httpx.Request) -> httpx.Response:
        assert request.url.params["athlete_id"] == "eq.7"
        return httpx.Response(200, json=[{"athlete_id": 7, "status": "idle", "progress": 100,
                                          "last_backfill_at": None, "last_sync_at": None,
                                          "last_webhook_event_id": None}])

    assert sync_state.get_sync_state(_client(found), 7)["status"] == "idle"

    def empty(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    assert sync_state.get_sync_state(_client(empty), 7) is None


def test_upsert_sync_state_merges_fields():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["prefer"] = request.headers.get("prefer")
        seen["body"] = request.read().decode()
        return httpx.Response(201, json=[])

    sync_state.upsert_sync_state(_client(handler), 7, {"status": "backfilling", "progress": 0})
    assert seen["url"] == "https://proj.supabase.co/rest/v1/sync_state?on_conflict=athlete_id"
    assert seen["prefer"] == "resolution=merge-duplicates"
    assert '"athlete_id":7' in seen["body"]
    assert '"status":"backfilling"' in seen["body"]
