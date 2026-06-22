from app.models.segments import SegmentListItem, SegmentListResponse
from app.services import segments as segments_service
from app.session import SESSION_COOKIE, sign_session


def _auth(client):
    client.cookies.set(SESSION_COOKIE, sign_session(99, "test-secret"))


def _list() -> SegmentListResponse:
    return SegmentListResponse(segments=[SegmentListItem(
        id=5, name="Hill", distance_m=1200.0, avg_grade=4.8, best_time_s=118,
        attempts=3, pr=True, latest_rank=1, improvement_s=4)])


def test_list_requires_session(client):
    assert client.get("/segments").status_code == 401


def test_list_returns_body_and_forwards_params(client, monkeypatch):
    captured = {}

    def fake(supabase, athlete_id, **kwargs: object) -> SegmentListResponse:  # noqa: ANN001
        captured.update(kwargs)
        return _list()

    monkeypatch.setattr(segments_service, "list_segments", fake)
    _auth(client)
    response = client.get("/segments?q=hill&sort=attempts&direction=asc")
    assert response.status_code == 200
    body = response.json()
    assert body["segments"][0]["name"] == "Hill"
    assert captured == {"q": "hill", "sort": "attempts", "direction": "asc"}


def test_list_rejects_bad_sort(client):
    _auth(client)
    assert client.get("/segments?sort=bogus").status_code == 422
