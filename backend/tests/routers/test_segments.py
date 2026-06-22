from datetime import UTC, datetime

from app.models.segments import (
    SegmentDetailResponse,
    SegmentEffortItem,
    SegmentListItem,
    SegmentListResponse,
)
from app.services import segments as segments_service
from app.session import SESSION_COOKIE, sign_session


def _auth(client):
    client.cookies.set(SESSION_COOKIE, sign_session(99, "test-secret"))


def _list() -> SegmentListResponse:
    return SegmentListResponse(
        segments=[SegmentListItem(
            id=5, name="Hill", distance_m=1200.0, avg_grade=4.8, best_time_s=118,
            attempts=3, pr=True, latest_rank=1, improvement_s=4,
            recent_times_s=[130, 125, 118])],
        page=1, page_size=10, total=1, total_pages=1,
        as_of=datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC))


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
    assert body["total"] == 1 and body["page"] == 1     # pagination envelope
    assert captured == {
        "q": "hill", "sort": "attempts", "direction": "asc", "page": 1, "as_of": None,
    }


def test_list_forwards_page_and_as_of(client, monkeypatch):
    captured = {}

    def fake(supabase, athlete_id, **kwargs: object) -> SegmentListResponse:  # noqa: ANN001
        captured.update(kwargs)
        return _list()

    monkeypatch.setattr(segments_service, "list_segments", fake)
    _auth(client)
    response = client.get("/segments?page=2&as_of=2026-06-21T12:00:00Z")
    assert response.status_code == 200
    assert captured["page"] == 2
    assert captured["as_of"].isoformat() == "2026-06-21T12:00:00+00:00"


def test_list_rejects_bad_sort(client):
    _auth(client)
    assert client.get("/segments?sort=bogus").status_code == 422


def test_list_rejects_non_positive_page(client):
    _auth(client)
    assert client.get("/segments?page=0").status_code == 422


def _detail() -> SegmentDetailResponse:
    return SegmentDetailResponse(
        id=5, name="Hill", distance_m=1200.0, avg_grade=4.8, pr_time_s=118, attempts=1,
        efforts=[SegmentEffortItem(id=10, activity_id=2, activity_name="River loop",
            start_date="2026-06-21T08:00:00Z", elapsed_time_s=118, avg_watts=None,
            avg_hr=None, avg_speed_ms=10.2, is_best=True)])


def test_detail_returns_body(client, monkeypatch):
    monkeypatch.setattr(segments_service, "get_segment",
                        lambda supabase, athlete_id, segment_id: _detail())
    _auth(client)
    response = client.get("/segments/5")
    assert response.status_code == 200
    assert response.json()["efforts"][0]["activity_name"] == "River loop"


def test_detail_404_when_not_found(client, monkeypatch):
    def boom(supabase, athlete_id, segment_id):
        raise segments_service.SegmentNotFoundError("none")

    monkeypatch.setattr(segments_service, "get_segment", boom)
    _auth(client)
    assert client.get("/segments/5").status_code == 404


def test_detail_requires_session(client):
    assert client.get("/segments/5").status_code == 401
