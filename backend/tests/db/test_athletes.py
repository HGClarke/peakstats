import httpx

from app.db import athletes


def _client(handler) -> httpx.Client:
    return httpx.Client(
        base_url="https://proj.supabase.co/rest/v1",
        headers={"apikey": "svc", "Authorization": "Bearer svc",
                 "Content-Type": "application/json"},
        transport=httpx.MockTransport(handler),
    )


def test_upsert_athlete_posts_with_merge_and_service_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = request.headers
        seen["body"] = request.read().decode()
        return httpx.Response(201, json=[])

    athletes.upsert_athlete(_client(handler), 7, "Ada Lovelace", "http://img/a.png")
    assert seen["url"] == "https://proj.supabase.co/rest/v1/athletes?on_conflict=id"
    assert seen["headers"]["apikey"] == "svc"
    assert seen["headers"]["prefer"] == "resolution=merge-duplicates"
    assert '"id": 7' in seen["body"]
    assert '"name": "Ada Lovelace"' in seen["body"]


def test_get_athlete_returns_first_row_or_none():
    def found(request: httpx.Request) -> httpx.Response:
        assert request.url.params["id"] == "eq.7"
        return httpx.Response(200, json=[{"id": 7, "name": "Ada"}])

    assert athletes.get_athlete(_client(found), 7) == {"id": 7, "name": "Ada"}

    def empty(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    assert athletes.get_athlete(_client(empty), 7) is None


def test_delete_athlete_filters_by_id():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["params"] = dict(request.url.params)
        return httpx.Response(204)

    athletes.delete_athlete(_client(handler), 7)
    assert seen["method"] == "DELETE"
    assert seen["params"]["id"] == "eq.7"
