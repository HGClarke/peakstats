from datetime import UTC, datetime

import pytest
from app.models.segments import SegmentDetailResponse, SegmentListResponse
from app.services import segments as svc


def _detail() -> dict:
    return {
        "id": 1001,
        "segment_efforts": [
            {"id": 9, "elapsed_time": 120, "start_date": "2026-06-20T08:00:00Z",
             "average_watts": 240.0, "average_heartrate": 158.4,
             "segment": {"id": 5, "name": "Hill", "distance": 1200.0, "average_grade": 4.8}},
            {"id": 10, "elapsed_time": 118, "start_date": "2026-06-21T08:00:00Z",
             "average_watts": None, "average_heartrate": None,
             "segment": {"id": 5, "name": "Hill", "distance": 1200.0, "average_grade": 4.8}},
        ],
    }


def test_extract_efforts_maps_segment_and_effort_fields():
    segs, efforts = svc.extract_efforts(7, _detail())
    assert {s["id"] for s in segs} == {5}
    assert segs[0] == {"id": 5, "name": "Hill", "distance_m": 1200.0, "avg_grade": 4.8}
    e0 = next(e for e in efforts if e["id"] == 9)
    assert e0["segment_id"] == 5 and e0["athlete_id"] == 7 and e0["activity_id"] == 1001
    assert e0["elapsed_time_s"] == 120
    assert e0["avg_watts"] == 240.0
    assert e0["avg_hr"] == 158            # rounded
    assert round(e0["avg_speed_ms"], 2) == 10.0   # 1200 / 120
    assert e0["is_best"] is False
    e1 = next(e for e in efforts if e["id"] == 10)
    assert e1["avg_watts"] is None and e1["avg_hr"] is None


def test_extract_efforts_empty_when_no_efforts():
    assert svc.extract_efforts(7, {"id": 1, "segment_efforts": []}) == ([], [])
    assert svc.extract_efforts(7, {"id": 1}) == ([], [])


def test_best_effort_id_picks_min_time_then_earliest():
    keys = [
        {"id": 9, "elapsed_time_s": 118, "start_date": "2026-06-21T08:00:00Z"},
        {"id": 11, "elapsed_time_s": 118, "start_date": "2026-06-19T08:00:00Z"},
        {"id": 10, "elapsed_time_s": 120, "start_date": "2026-06-20T08:00:00Z"},
    ]
    assert svc.best_effort_id(keys) == 11   # tie on 118 -> earliest date wins


def test_recompute_is_best_reads_keys_and_sets_winner(monkeypatch):  # noqa: ANN001
    captured = {}
    monkeypatch.setattr(svc.segments_db, "get_effort_keys",
                        lambda supabase, a, s: [{"id": 9, "elapsed_time_s": 120, "start_date": "A"},
                                                {"id": 10, "elapsed_time_s": 118,
                                                 "start_date": "B"}])
    monkeypatch.setattr(svc.segments_db, "set_is_best",
                        lambda supabase, a, s, best_id: captured.update(a=a, s=s, best_id=best_id))
    svc.recompute_is_best(object(), 7, 5)
    assert captured == {"a": 7, "s": 5, "best_id": 10}


def test_recompute_is_best_noop_when_no_efforts(monkeypatch):  # noqa: ANN001
    monkeypatch.setattr(svc.segments_db, "get_effort_keys", lambda supabase, a, s: [])

    def fail(*a: object, **k: object) -> None:  # noqa: ARG001
        raise AssertionError("must not set_is_best with no efforts")

    monkeypatch.setattr(svc.segments_db, "set_is_best", fail)
    svc.recompute_is_best(object(), 7, 5)


def test_store_activity_efforts_upserts_and_recomputes(monkeypatch):
    calls = {"segs": None, "efforts": None, "recomputed": []}
    monkeypatch.setattr(svc.segments_db, "upsert_segments",
                        lambda supabase, rows: calls.update(segs=rows))
    monkeypatch.setattr(svc.segments_db, "upsert_segment_efforts",
                        lambda supabase, rows: calls.update(efforts=rows))
    monkeypatch.setattr(svc, "recompute_is_best",
                        lambda supabase, a, s: calls["recomputed"].append(s))
    svc.store_activity_efforts(object(), 7, _detail())
    assert len(calls["segs"]) == 1        # deduped by segment id
    assert len(calls["efforts"]) == 2
    assert calls["recomputed"] == [5]


def test_store_activity_efforts_noop_when_none(monkeypatch):  # noqa: ANN001
    def fail(*a: object, **k: object) -> None:  # noqa: ARG001
        raise AssertionError("must not touch db without efforts")

    monkeypatch.setattr(svc.segments_db, "upsert_segment_efforts", fail)
    svc.store_activity_efforts(object(), 7, {"id": 1, "segment_efforts": []})




def _summary_row(over: dict | None = None) -> dict:
    row = {
        "id": 5, "name": "Hill", "distance_m": 1200.0, "avg_grade": 4.8,
        "best_time_s": 118, "attempts": 3, "pr": True, "latest_rank": 1,
        "improvement_s": 4, "recent_times_s": [130, 125, 118], "total_count": 42,
    }
    if over:
        row.update(over)
    return row


def test_list_segments_maps_rpc_rows_to_items(monkeypatch):
    monkeypatch.setattr(svc.segments_db, "list_segment_summaries",
                        lambda *a, **k: [_summary_row()])
    resp = svc.list_segments(object(), 7, q=None, sort="attempts", direction="desc", page=1)
    assert isinstance(resp, SegmentListResponse)
    item = resp.segments[0]
    assert item.id == 5 and item.name == "Hill"
    assert item.distance_m == 1200.0 and item.avg_grade == 4.8
    assert item.best_time_s == 118 and item.attempts == 3
    assert item.pr is True and item.latest_rank == 1 and item.improvement_s == 4
    assert item.recent_times_s == [130, 125, 118]


def test_list_segments_reads_total_from_rpc_and_computes_pages(monkeypatch):
    rows = [_summary_row({"id": i, "total_count": 42}) for i in range(10)]
    monkeypatch.setattr(svc.segments_db, "list_segment_summaries", lambda *a, **k: rows)
    resp = svc.list_segments(object(), 7, q=None, sort="attempts", direction="desc", page=2)
    assert resp.total == 42
    assert resp.page == 2
    assert resp.page_size == svc.SEGMENT_PAGE_SIZE
    assert resp.total_pages == 5            # ceil(42 / 10)
    assert len(resp.segments) == 10


def test_list_segments_total_zero_when_empty(monkeypatch):
    monkeypatch.setattr(svc.segments_db, "list_segment_summaries", lambda *a, **k: [])
    resp = svc.list_segments(object(), 7, q="zzz", sort="attempts", direction="desc", page=1)
    assert resp.segments == []
    assert resp.total == 0
    assert resp.total_pages == 1            # never below 1


def test_list_segments_forwards_snapshot_filters_and_paging(monkeypatch):
    captured = {}

    def fake(supabase, athlete_id, *, as_of, q, direction, limit, offset):  # noqa: ANN001, ANN202
        captured.update(as_of=as_of, q=q, direction=direction, limit=limit, offset=offset)
        return []

    monkeypatch.setattr(svc.segments_db, "list_segment_summaries", fake)
    snap = datetime(2026, 6, 22, 12, 0, 0, tzinfo=UTC)
    resp = svc.list_segments(
        object(), 7, q="hill", sort="attempts", direction="asc", page=3, as_of=snap
    )
    assert captured == {
        "as_of": snap.isoformat(), "q": "hill", "direction": "asc",
        "limit": svc.SEGMENT_PAGE_SIZE, "offset": 2 * svc.SEGMENT_PAGE_SIZE,
    }
    assert resp.as_of == snap               # snapshot echoed back


def _detail_efforts():
    return [
        {"id": 10, "activity_id": 2, "start_date": "2026-06-21T08:00:00Z",
         "elapsed_time_s": 118, "avg_watts": None, "avg_hr": None, "avg_speed_ms": 10.2,
         "is_best": True, "activities": {"name": "River loop"}},
        {"id": 9, "activity_id": 1, "start_date": "2026-06-10T08:00:00Z",
         "elapsed_time_s": 130, "avg_watts": 240.0, "avg_hr": 158, "avg_speed_ms": 9.2,
         "is_best": False, "activities": {"name": "Hill repeats"}},
    ]


def test_get_segment_builds_detail(monkeypatch):
    seg = {"id": 5, "name": "Hill", "distance_m": 1200.0, "avg_grade": 4.8}
    monkeypatch.setattr(svc.segments_db, "get_segment", lambda supabase, sid: seg)
    monkeypatch.setattr(svc.segments_db, "list_segment_efforts",
                        lambda supabase, a, sid: _detail_efforts())
    resp = svc.get_segment(object(), 7, 5)
    assert isinstance(resp, SegmentDetailResponse)
    assert resp.pr_time_s == 118
    assert resp.attempts == 2
    assert resp.efforts[0].activity_name == "River loop"
    assert resp.efforts[1].avg_hr == 158


def test_get_segment_404_when_segment_missing(monkeypatch):
    monkeypatch.setattr(svc.segments_db, "get_segment", lambda supabase, sid: None)
    monkeypatch.setattr(svc.segments_db, "list_segment_efforts", lambda supabase, a, sid: [])
    with pytest.raises(svc.SegmentNotFoundError):
        svc.get_segment(object(), 7, 5)


def test_get_segment_404_when_no_efforts_for_athlete(monkeypatch):
    seg = {"id": 5, "name": "Hill", "distance_m": 1200.0, "avg_grade": 4.8}
    monkeypatch.setattr(svc.segments_db, "get_segment", lambda supabase, sid: seg)
    monkeypatch.setattr(svc.segments_db, "list_segment_efforts", lambda supabase, a, sid: [])
    with pytest.raises(svc.SegmentNotFoundError):
        svc.get_segment(object(), 7, 5)
