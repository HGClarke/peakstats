from app.models.sync import SyncStatusResponse
from app.services import sync as sync_service


class FakeSupabase:
    pass


def test_to_activity_row_maps_summary_fields():
    summary = {
        "id": 555, "name": "River loop", "sport_type": "Ride",
        "start_date": "2026-06-15T08:00:00Z", "distance": 38700.0,
        "moving_time": 5662, "elapsed_time": 5900, "total_elevation_gain": 420.0,
        "average_speed": 6.8, "average_heartrate": 148.6,
        "map": {"summary_polyline": "abc"},
    }
    row = sync_service._to_activity_row(7, summary)
    assert row["id"] == 555
    assert row["athlete_id"] == 7
    assert row["type"] == "Ride"
    assert row["distance_m"] == 38700.0
    assert row["avg_hr"] == 149
    assert row["summary_polyline"] == "abc"


def test_to_activity_row_handles_missing_optionals():
    row = sync_service._to_activity_row(7, {
        "id": 1, "name": "Spin", "type": "Workout",
        "start_date": "2026-06-15T08:00:00Z", "distance": 0.0,
        "moving_time": 10, "elapsed_time": 10, "total_elevation_gain": 0.0,
    })
    assert row["avg_speed_ms"] is None
    assert row["avg_hr"] is None
    assert row["summary_polyline"] is None
    assert row["type"] == "Workout"


def test_get_status_never_synced(monkeypatch):
    monkeypatch.setattr(sync_service.sync_state_db, "get_sync_state",
                        lambda supabase, athlete_id: None)
    monkeypatch.setattr(sync_service.activities_db, "count_activities",
                        lambda supabase, athlete_id: 0)
    status = sync_service.get_status(object(), 7)
    assert status == SyncStatusResponse(status="never_synced", progress=0, synced=0)


def test_get_status_reads_row(monkeypatch):
    monkeypatch.setattr(sync_service.sync_state_db, "get_sync_state",
                        lambda supabase, athlete_id: {"status": "idle", "progress": 100,
                                                      "last_backfill_at": "T1",
                                                      "last_sync_at": "T2",
                                                      "last_webhook_event_id": None})
    monkeypatch.setattr(sync_service.activities_db, "count_activities",
                        lambda supabase, athlete_id: 218)
    status = sync_service.get_status(object(), 7)
    assert status.status == "idle"
    assert status.synced == 218
    assert status.last_sync_at == "T2"


def test_get_status_phantom_idle_treated_as_never_synced(monkeypatch):
    # A row created only by refresh has status='idle' but no completed backfill.
    monkeypatch.setattr(sync_service.sync_state_db, "get_sync_state",
                        lambda supabase, athlete_id: {"status": "idle", "progress": 0,
                                                      "last_backfill_at": None,
                                                      "last_sync_at": "T2",
                                                      "last_webhook_event_id": None})
    monkeypatch.setattr(sync_service.activities_db, "count_activities",
                        lambda supabase, athlete_id: 876)
    status = sync_service.get_status(object(), 7)
    assert status.status == "never_synced"


def test_get_status_backfilling_preserved(monkeypatch):
    monkeypatch.setattr(sync_service.sync_state_db, "get_sync_state",
                        lambda supabase, athlete_id: {"status": "backfilling", "progress": 40,
                                                      "last_backfill_at": None,
                                                      "last_sync_at": None,
                                                      "last_webhook_event_id": None})
    monkeypatch.setattr(sync_service.activities_db, "count_activities",
                        lambda supabase, athlete_id: 100)
    status = sync_service.get_status(object(), 7)
    assert status.status == "backfilling"


def test_refresh_raises_when_never_backfilled(monkeypatch):
    import pytest

    class FakeStrava:
        def close(self):
            pass

    monkeypatch.setattr(sync_service, "build_strava", lambda settings: FakeStrava())
    monkeypatch.setattr(sync_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    monkeypatch.setattr(sync_service.sync_state_db, "get_sync_state",
                        lambda supabase, athlete_id: None)

    def fail_upsert(*a: object, **k: object) -> None:
        raise AssertionError("must not create a sync_state row on refresh")

    monkeypatch.setattr(sync_service.sync_state_db, "upsert_sync_state", fail_upsert)

    with pytest.raises(sync_service.SyncNotReadyError):
        sync_service.refresh(FakeSupabase(), settings=object(), athlete_id=7)


def test_start_backfill_starts_when_idle(monkeypatch):
    calls = {}
    monkeypatch.setattr(sync_service.sync_state_db, "get_sync_state",
                        lambda supabase, athlete_id: None)
    monkeypatch.setattr(sync_service.sync_state_db, "upsert_sync_state",
                        lambda supabase, athlete_id, fields: calls.update(fields=fields))
    monkeypatch.setattr(sync_service.activities_db, "count_activities",
                        lambda supabase, athlete_id: 0)
    _, started = sync_service.start_backfill(object(), 7)
    assert started is True
    assert calls["fields"] == {"status": "backfilling", "progress": 0}


def test_start_backfill_idempotent_when_already_backfilling(monkeypatch):
    monkeypatch.setattr(sync_service.sync_state_db, "get_sync_state",
                        lambda supabase, athlete_id: {"status": "backfilling", "progress": 30,
                                                      "last_backfill_at": None,
                                                      "last_sync_at": None,
                                                      "last_webhook_event_id": None})
    monkeypatch.setattr(sync_service.activities_db, "count_activities",
                        lambda supabase, athlete_id: 50)

    def fail(*a: object, **k: object) -> None:
        raise AssertionError("must not re-upsert while backfilling")

    monkeypatch.setattr(sync_service.sync_state_db, "upsert_sync_state", fail)
    status, started = sync_service.start_backfill(object(), 7)
    assert started is False
    assert status.status == "backfilling"


def test_run_backfill_paginates_and_finalizes(monkeypatch):
    upserts = []
    states = []

    class FakeStrava:
        def __init__(self) -> None:
            self.pages = {1: [{"id": i, "name": "R", "type": "Ride",
                               "start_date": "2026-06-15T08:00:00Z", "distance": 1.0,
                               "moving_time": 1, "elapsed_time": 1,
                               "total_elevation_gain": 0.0} for i in range(200)],
                          2: [{"id": 999, "name": "R", "type": "Ride",
                               "start_date": "2026-06-15T08:00:00Z", "distance": 1.0,
                               "moving_time": 1, "elapsed_time": 1,
                               "total_elevation_gain": 0.0}]}

        def list_activities(self, access_token, *, page, per_page=200, after=None):
            return self.pages.get(page, [])

        def close(self):
            pass

    monkeypatch.setattr(sync_service, "build_strava", lambda settings: FakeStrava())
    monkeypatch.setattr(sync_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    monkeypatch.setattr(sync_service.activities_db, "upsert_activities",
                        lambda supabase, rows: upserts.append(len(rows)))
    monkeypatch.setattr(sync_service.sync_state_db, "upsert_sync_state",
                        lambda supabase, athlete_id, fields: states.append(fields))

    sync_service.run_backfill(FakeSupabase(), settings=object(), athlete_id=7)

    assert upserts == [200, 1]
    assert states[-1]["status"] == "idle"
    assert states[-1]["progress"] == 100
    assert states[-1]["last_backfill_at"]


def test_run_backfill_sets_error_on_failure(monkeypatch):
    states = []

    class BoomStrava:
        def close(self):
            pass

    monkeypatch.setattr(sync_service, "build_strava", lambda settings: BoomStrava())

    def boom(supabase, strava, athlete_id):
        raise RuntimeError("token fail")

    monkeypatch.setattr(sync_service, "get_valid_access_token", boom)
    monkeypatch.setattr(sync_service.sync_state_db, "upsert_sync_state",
                        lambda supabase, athlete_id, fields: states.append(fields))

    sync_service.run_backfill(FakeSupabase(), settings=object(), athlete_id=7)
    assert states[-1] == {"status": "error"}


def test_refresh_pulls_since_last_sync(monkeypatch):
    captured = {}
    final_fields = {}

    class FakeStrava:
        def list_activities(self, access_token, *, page, per_page=200, after=None):
            captured["after"] = after
            return [] if page > 1 else [{"id": 1, "name": "R", "type": "Ride",
                                         "start_date": "2026-06-20T08:00:00Z", "distance": 1.0,
                                         "moving_time": 1, "elapsed_time": 1,
                                         "total_elevation_gain": 0.0}]

        def close(self):
            pass

    monkeypatch.setattr(sync_service, "build_strava", lambda settings: FakeStrava())
    monkeypatch.setattr(sync_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    _state = {"status": "idle", "progress": 100,
              "last_backfill_at": "2026-06-01T00:00:00+00:00",
              "last_sync_at": "2026-06-19T00:00:00+00:00",
              "last_webhook_event_id": None}
    monkeypatch.setattr(sync_service.sync_state_db, "get_sync_state",
                        lambda supabase, athlete_id: _state)
    monkeypatch.setattr(sync_service.activities_db, "upsert_activities",
                        lambda supabase, rows: None)
    monkeypatch.setattr(sync_service.sync_state_db, "upsert_sync_state",
                        lambda supabase, athlete_id, fields: final_fields.update(fields))

    result = sync_service.refresh(FakeSupabase(), settings=object(), athlete_id=7)
    assert result.synced == 1
    assert captured["after"] is not None
    assert "status" not in final_fields
    assert final_fields["last_sync_at"]


def test_to_activity_row_stores_start_date_local():
    row = sync_service._to_activity_row(7, {
        "id": 9, "name": "Evening spin", "type": "Ride",
        "start_date": "2026-06-21T05:00:00Z",
        "start_date_local": "2026-06-20T22:00:00Z",
        "distance": 1000.0, "moving_time": 100, "elapsed_time": 100,
        "total_elevation_gain": 0.0,
    })
    assert row["start_date_local"] == "2026-06-20T22:00:00Z"


def test_to_activity_row_start_date_local_missing_is_none():
    row = sync_service._to_activity_row(7, {
        "id": 1, "name": "Spin", "type": "Workout",
        "start_date": "2026-06-15T08:00:00Z", "distance": 0.0,
        "moving_time": 10, "elapsed_time": 10, "total_elevation_gain": 0.0,
    })
    assert row["start_date_local"] is None


def test_run_detail_backfill_fetches_stores_and_marks(monkeypatch):
    fetched, stored, marked = [], [], []

    class FakeStrava:
        def get_activity(self, access_token, activity_id):
            fetched.append(activity_id)
            return {"id": activity_id, "splits_metric": [{"x": 1}], "segment_efforts": []}

        def close(self):
            pass

    pending = [[{"id": 1}, {"id": 2}], []]  # one batch, then empty -> stop
    monkeypatch.setattr(sync_service, "build_strava", lambda settings: FakeStrava())
    monkeypatch.setattr(sync_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    monkeypatch.setattr(sync_service.activities_db, "list_activities_needing_detail",
                        lambda supabase, athlete_id, limit: pending.pop(0))
    monkeypatch.setattr(sync_service.segments_service, "store_activity_efforts",
                        lambda supabase, athlete_id, detail: stored.append(detail["id"]))
    monkeypatch.setattr(
        sync_service.activities_db, "mark_detail_fetched",
        lambda supabase, activity_id, splits_metric, fetched_at: marked.append(activity_id),
    )
    monkeypatch.setattr(sync_service.time, "sleep", lambda s: None)

    sync_service.run_detail_backfill(FakeSupabase(), settings=object(), athlete_id=7)
    assert fetched == [1, 2]
    assert stored == [1, 2]
    assert marked == [1, 2]


def test_run_detail_backfill_backs_off_on_429(monkeypatch):
    import httpx

    calls = {"n": 0}
    slept = []

    class FakeStrava:
        def get_activity(self, access_token, activity_id):
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.HTTPStatusError(
                    "429", request=httpx.Request("GET", "http://x"),
                    response=httpx.Response(429, headers={"Retry-After": "2"}))
            return {"id": activity_id, "splits_metric": None, "segment_efforts": []}

        def close(self):
            pass

    pending = [[{"id": 1}], []]
    monkeypatch.setattr(sync_service, "build_strava", lambda settings: FakeStrava())
    monkeypatch.setattr(sync_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    monkeypatch.setattr(sync_service.activities_db, "list_activities_needing_detail",
                        lambda supabase, athlete_id, limit: pending.pop(0))
    monkeypatch.setattr(sync_service.segments_service, "store_activity_efforts",
                        lambda supabase, athlete_id, detail: None)
    monkeypatch.setattr(sync_service.activities_db, "mark_detail_fetched",
                        lambda supabase, activity_id, splits_metric, fetched_at: None)
    monkeypatch.setattr(sync_service.time, "sleep", lambda s: slept.append(s))

    sync_service.run_detail_backfill(FakeSupabase(), settings=object(), athlete_id=7)
    assert calls["n"] == 2          # retried after the 429
    assert 2 in slept               # honoured Retry-After


def test_run_detail_backfill_isolates_per_activity_failures(monkeypatch):
    fetched, stored, marked = [], [], []

    class FakeStrava:
        def get_activity(self, access_token, activity_id):
            fetched.append(activity_id)
            return {"id": activity_id, "splits_metric": None, "segment_efforts": []}

        def close(self):
            pass

    def store(supabase, athlete_id, detail):
        if detail["id"] == 2:
            raise RuntimeError("boom on activity 2")
        stored.append(detail["id"])

    # One batch of 3, then empty. The lambda ignores the (growing) limit arg.
    pending = [[{"id": 1}, {"id": 2}, {"id": 3}], []]
    monkeypatch.setattr(sync_service, "build_strava", lambda settings: FakeStrava())
    monkeypatch.setattr(sync_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    monkeypatch.setattr(sync_service.activities_db, "list_activities_needing_detail",
                        lambda supabase, athlete_id, limit: pending.pop(0))
    monkeypatch.setattr(sync_service.segments_service, "store_activity_efforts", store)
    monkeypatch.setattr(
        sync_service.activities_db, "mark_detail_fetched",
        lambda supabase, activity_id, splits_metric, fetched_at: marked.append(activity_id),
    )
    monkeypatch.setattr(sync_service.time, "sleep", lambda s: None)

    sync_service.run_detail_backfill(FakeSupabase(), settings=object(), athlete_id=7)
    assert fetched == [1, 2, 3]     # every activity attempted
    assert stored == [1, 3]         # activity 2 failed mid-store
    assert marked == [1, 3]         # 2 left unmarked (detail_fetched_at stays NULL)


def test_run_detail_backfill_refreshes_token_each_activity(monkeypatch):
    token_calls = []

    class FakeStrava:
        def get_activity(self, access_token, activity_id):
            return {"id": activity_id, "splits_metric": None, "segment_efforts": []}

        def close(self):
            pass

    def fake_token(supabase, strava, athlete_id):
        token_calls.append(1)
        return "AT"

    pending = [[{"id": 1}, {"id": 2}], []]
    monkeypatch.setattr(sync_service, "build_strava", lambda settings: FakeStrava())
    monkeypatch.setattr(sync_service, "get_valid_access_token", fake_token)
    monkeypatch.setattr(sync_service.activities_db, "list_activities_needing_detail",
                        lambda supabase, athlete_id, limit: pending.pop(0))
    monkeypatch.setattr(sync_service.segments_service, "store_activity_efforts",
                        lambda supabase, athlete_id, detail: None)
    monkeypatch.setattr(sync_service.activities_db, "mark_detail_fetched",
                        lambda supabase, activity_id, splits_metric, fetched_at: None)
    monkeypatch.setattr(sync_service.time, "sleep", lambda s: None)

    sync_service.run_detail_backfill(FakeSupabase(), settings=object(), athlete_id=7)
    assert len(token_calls) == 2    # token re-validated once per activity


def test_to_activity_row_maps_avg_watts():
    row = sync_service._to_activity_row(7, {
        "id": 9, "name": "Power ride", "type": "Ride",
        "start_date": "2026-06-21T05:00:00Z", "distance": 1000.0,
        "moving_time": 100, "elapsed_time": 100, "total_elevation_gain": 0.0,
        "average_watts": 211.4,
    })
    assert row["avg_watts"] == 211.4


def test_to_activity_row_avg_watts_missing_is_none():
    row = sync_service._to_activity_row(7, {
        "id": 1, "name": "Spin", "type": "Workout",
        "start_date": "2026-06-15T08:00:00Z", "distance": 0.0,
        "moving_time": 10, "elapsed_time": 10, "total_elevation_gain": 0.0,
    })
    assert row["avg_watts"] is None


def test_run_streams_backfill_computes_and_upserts_only_pending(monkeypatch):
    fetched, upserts = [], []

    class FakeStrava:
        def get_activity_streams(self, access_token, activity_id, keys, resolution="high"):
            fetched.append(activity_id)
            return {"time": [0, 1], "watts": [100, 200], "heartrate": [120, 130]}

        def close(self):
            pass

    monkeypatch.setattr(sync_service, "build_strava", lambda settings: FakeStrava())
    monkeypatch.setattr(sync_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    monkeypatch.setattr(sync_service.metrics_db, "list_activity_ids_needing_metrics",
                        lambda supabase, athlete_id: [11, 12])
    monkeypatch.setattr(sync_service.metrics_db, "upsert_metrics",
                        lambda supabase, row: upserts.append(row["activity_id"]))
    monkeypatch.setattr(sync_service.time, "sleep", lambda s: None)

    sync_service.run_streams_backfill(FakeSupabase(), settings=object(), athlete_id=7)
    assert fetched == [11, 12]
    assert upserts == [11, 12]


def test_run_streams_backfill_isolates_failures(monkeypatch):
    upserts = []

    class FakeStrava:
        def get_activity_streams(self, access_token, activity_id, keys, resolution="high"):
            if activity_id == 12:
                raise RuntimeError("boom")
            return {"time": [0, 1], "watts": [100, 200]}

        def close(self):
            pass

    monkeypatch.setattr(sync_service, "build_strava", lambda settings: FakeStrava())
    monkeypatch.setattr(sync_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    monkeypatch.setattr(sync_service.metrics_db, "list_activity_ids_needing_metrics",
                        lambda supabase, athlete_id: [11, 12, 13])
    monkeypatch.setattr(sync_service.metrics_db, "upsert_metrics",
                        lambda supabase, row: upserts.append(row["activity_id"]))
    monkeypatch.setattr(sync_service.time, "sleep", lambda s: None)

    sync_service.run_streams_backfill(FakeSupabase(), settings=object(), athlete_id=7)
    assert upserts == [11, 13]   # 12 failed mid-fetch, batch continued


def test_run_streams_backfill_backs_off_on_429(monkeypatch):
    import httpx
    calls = {"n": 0}
    slept = []

    class FakeStrava:
        def get_activity_streams(self, access_token, activity_id, keys, resolution="high"):
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.HTTPStatusError(
                    "429", request=httpx.Request("GET", "http://x"),
                    response=httpx.Response(429, headers={"Retry-After": "2"}))
            return {"time": [0, 1], "watts": [100, 200]}

        def close(self):
            pass

    monkeypatch.setattr(sync_service, "build_strava", lambda settings: FakeStrava())
    monkeypatch.setattr(sync_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    monkeypatch.setattr(sync_service.metrics_db, "list_activity_ids_needing_metrics",
                        lambda supabase, athlete_id: [11])
    monkeypatch.setattr(sync_service.metrics_db, "upsert_metrics", lambda supabase, row: None)
    monkeypatch.setattr(sync_service.time, "sleep", lambda s: slept.append(s))

    sync_service.run_streams_backfill(FakeSupabase(), settings=object(), athlete_id=7)
    assert calls["n"] == 2 and 2 in slept   # retried after 429, honoured Retry-After
