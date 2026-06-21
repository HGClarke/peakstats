from app.models.sync import SyncStatusResponse
from app.services import sync as sync_service


class FakeSupabase:
    def close(self) -> None:
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

    monkeypatch.setattr(sync_service, "build_supabase", lambda settings: FakeSupabase())
    monkeypatch.setattr(sync_service, "build_strava", lambda settings: FakeStrava())
    monkeypatch.setattr(sync_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    monkeypatch.setattr(sync_service.activities_db, "upsert_activities",
                        lambda supabase, rows: upserts.append(len(rows)))
    monkeypatch.setattr(sync_service.sync_state_db, "upsert_sync_state",
                        lambda supabase, athlete_id, fields: states.append(fields))

    sync_service.run_backfill(settings=object(), athlete_id=7)

    assert upserts == [200, 1]
    assert states[-1]["status"] == "idle"
    assert states[-1]["progress"] == 100
    assert states[-1]["last_backfill_at"]


def test_run_backfill_sets_error_on_failure(monkeypatch):
    states = []
    monkeypatch.setattr(sync_service, "build_supabase", lambda settings: FakeSupabase())

    class BoomStrava:
        def close(self):
            pass

    monkeypatch.setattr(sync_service, "build_strava", lambda settings: BoomStrava())

    def boom(supabase, strava, athlete_id):
        raise RuntimeError("token fail")

    monkeypatch.setattr(sync_service, "get_valid_access_token", boom)
    monkeypatch.setattr(sync_service.sync_state_db, "upsert_sync_state",
                        lambda supabase, athlete_id, fields: states.append(fields))

    sync_service.run_backfill(settings=object(), athlete_id=7)
    assert states[-1] == {"status": "error"}


def test_refresh_pulls_since_last_sync(monkeypatch):
    captured = {}

    class FakeStrava:
        def list_activities(self, access_token, *, page, per_page=200, after=None):
            captured["after"] = after
            return [] if page > 1 else [{"id": 1, "name": "R", "type": "Ride",
                                         "start_date": "2026-06-20T08:00:00Z", "distance": 1.0,
                                         "moving_time": 1, "elapsed_time": 1,
                                         "total_elevation_gain": 0.0}]

        def close(self):
            pass

    monkeypatch.setattr(sync_service, "build_supabase", lambda settings: FakeSupabase())
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
                        lambda supabase, athlete_id, fields: None)

    result = sync_service.refresh(settings=object(), athlete_id=7)
    assert result.synced == 1
    assert captured["after"] is not None
