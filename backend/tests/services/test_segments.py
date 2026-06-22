from app.models.segments import SegmentListResponse
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




def test_summarize_segment_new_pr_with_improvement():
    efforts = [
        {"id": 1, "elapsed_time_s": 130, "start_date": "2026-06-10T08:00:00Z"},
        {"id": 2, "elapsed_time_s": 118, "start_date": "2026-06-21T08:00:00Z"},  # latest = fastest
    ]
    item = svc.summarize_segment(5, "Hill", 1200.0, 4.8, efforts)
    assert item.best_time_s == 118
    assert item.attempts == 2
    assert item.pr is True
    assert item.latest_rank == 1
    assert item.improvement_s == 12          # 130 - 118


def test_summarize_segment_nth_best_when_latest_slower():
    efforts = [
        {"id": 1, "elapsed_time_s": 118, "start_date": "2026-06-10T08:00:00Z"},
        {"id": 2, "elapsed_time_s": 130, "start_date": "2026-06-21T08:00:00Z"},  # latest = slowest
    ]
    item = svc.summarize_segment(5, "Hill", 1200.0, 4.8, efforts)
    assert item.pr is False
    assert item.latest_rank == 2
    assert item.improvement_s is None


def test_summarize_segment_single_effort_is_pr_without_improvement():
    effort = [{"id": 1, "elapsed_time_s": 118, "start_date": "2026-06-10T08:00:00Z"}]
    item = svc.summarize_segment(5, "Hill", 1200.0, 4.8, effort)
    assert item.pr is True and item.latest_rank == 1 and item.improvement_s is None


def test_list_segments_groups_filters_and_sorts(monkeypatch):
    rows = [
        {"segment_id": 5, "elapsed_time_s": 118, "start_date": "2026-06-21T08:00:00Z",
         "segments": {"name": "Hill", "distance_m": 1200.0, "avg_grade": 4.8}},
        {"segment_id": 5, "elapsed_time_s": 130, "start_date": "2026-06-10T08:00:00Z",
         "segments": {"name": "Hill", "distance_m": 1200.0, "avg_grade": 4.8}},
        {"segment_id": 9, "elapsed_time_s": 200, "start_date": "2026-06-20T08:00:00Z",
         "segments": {"name": "Flat", "distance_m": 3000.0, "avg_grade": 0.3}},
    ]
    monkeypatch.setattr(svc.segments_db, "list_athlete_efforts", lambda supabase, a: rows)
    resp = svc.list_segments(object(), 7, q=None, sort="attempts", direction="desc")
    assert isinstance(resp, SegmentListResponse)
    assert [s.name for s in resp.segments] == ["Hill", "Flat"]   # 2 attempts before 1
    assert resp.segments[0].attempts == 2

    resp_q = svc.list_segments(object(), 7, q="fla", sort="attempts", direction="desc")
    assert [s.name for s in resp_q.segments] == ["Flat"]
