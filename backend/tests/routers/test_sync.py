from app.models.sync import RefreshResponse, SyncStatusResponse
from app.services import sync as sync_service
from app.session import SESSION_COOKIE, sign_session


def _auth(client):
    client.cookies.set(SESSION_COOKIE, sign_session(99, "test-secret"))


def test_status_requires_session(client):
    assert client.get("/sync/status").status_code == 401


def test_status_returns_body(client, monkeypatch):
    monkeypatch.setattr(sync_service, "get_status",
                        lambda supabase, athlete_id: SyncStatusResponse(
                            status="idle", progress=100, synced=42))
    _auth(client)
    response = client.get("/sync/status")
    assert response.status_code == 200
    assert response.json()["synced"] == 42


def test_start_schedules_backfill_when_started(client, monkeypatch):
    spawned = {}
    monkeypatch.setattr(sync_service, "start_backfill",
                        lambda supabase, athlete_id: (
                            SyncStatusResponse(status="backfilling", progress=0, synced=0), True))
    monkeypatch.setattr(sync_service, "run_backfill",
                        lambda supabase, settings, athlete_id: spawned.update(backfill=athlete_id))
    monkeypatch.setattr(sync_service, "run_detail_backfill",
                        lambda supabase, settings, athlete_id: spawned.update(detail=athlete_id))
    monkeypatch.setattr(sync_service, "run_streams_backfill",
                        lambda supabase, settings, athlete_id: spawned.update(streams=athlete_id))
    _auth(client)
    response = client.post("/sync/start")
    assert response.status_code == 200
    assert spawned == {"backfill": 99, "detail": 99, "streams": 99}


def test_start_does_not_reschedule_when_already_running(client, monkeypatch):
    monkeypatch.setattr(sync_service, "start_backfill",
                        lambda supabase, athlete_id: (
                            SyncStatusResponse(status="backfilling", progress=30, synced=5), False))

    def fail(supabase, settings, athlete_id):
        raise AssertionError("must not spawn a second backfill")

    monkeypatch.setattr(sync_service, "run_backfill", fail)
    monkeypatch.setattr(sync_service, "run_detail_backfill",
                        lambda supabase, settings, athlete_id: None)
    monkeypatch.setattr(sync_service, "run_streams_backfill",
                        lambda supabase, settings, athlete_id: None)
    _auth(client)
    assert client.post("/sync/start").status_code == 200


def test_refresh_returns_count(client, monkeypatch):
    monkeypatch.setattr(sync_service, "refresh",
                        lambda supabase, settings, athlete_id: RefreshResponse(synced=4))
    _auth(client)
    response = client.post("/sync/refresh")
    assert response.status_code == 200
    assert response.json() == {"synced": 4}


def test_refresh_requires_session(client):
    assert client.post("/sync/refresh").status_code == 401


def test_refresh_conflict_when_not_synced(client, monkeypatch):
    def not_ready(supabase, settings, athlete_id):
        raise sync_service.SyncNotReadyError("no backfill yet")

    monkeypatch.setattr(sync_service, "refresh", not_ready)
    _auth(client)
    assert client.post("/sync/refresh").status_code == 409
