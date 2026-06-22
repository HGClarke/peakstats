from app.config import Settings
from app.models.webhooks import StravaWebhookEvent
from app.services import webhooks as webhooks_service

# subscription_id 0 => the optional subscription gate is disabled (default).
SETTINGS = Settings(strava_webhook_subscription_id=0)


class FakeSupabase:
    pass


class FakeStrava:
    def __init__(self) -> None:
        self.fetched: list[int] = []

    def get_activity(self, access_token, activity_id):
        self.fetched.append(activity_id)
        return {"id": activity_id, "name": "Ride", "type": "Ride",
                "start_date": "2026-06-21T08:00:00Z", "distance": 1000.0,
                "moving_time": 100, "elapsed_time": 110, "total_elevation_gain": 5.0}

    def close(self) -> None:
        pass


def _event(**overrides: object) -> StravaWebhookEvent:
    base: dict[str, object] = {
        "aspect_type": "create", "object_type": "activity", "object_id": 555,
        "owner_id": 7, "subscription_id": 1, "event_time": 1_700_000_000,
    }
    base.update(overrides)
    return StravaWebhookEvent(**base)  # type: ignore[arg-type]


def _wire(monkeypatch, *, athlete=True):
    strava = FakeStrava()
    monkeypatch.setattr(webhooks_service, "build_strava", lambda settings: strava)
    monkeypatch.setattr(webhooks_service, "get_valid_access_token",
                        lambda supabase, strava, athlete_id: "AT")
    monkeypatch.setattr(webhooks_service.athletes_db, "get_athlete",
                        lambda supabase, athlete_id: {"id": athlete_id} if athlete else None)
    return strava


def test_create_event_fetches_and_upserts(monkeypatch):
    upserts = []
    states = []
    strava = _wire(monkeypatch)
    monkeypatch.setattr(webhooks_service.activities_db, "upsert_activities",
                        lambda supabase, rows: upserts.append(rows))
    monkeypatch.setattr(webhooks_service.sync_state_db, "upsert_sync_state",
                        lambda supabase, athlete_id, fields: states.append(fields))
    monkeypatch.setattr(webhooks_service.activities_db, "mark_detail_fetched",
                        lambda supabase, activity_id, splits_metric, fetched_at: None)

    webhooks_service.process_event(FakeSupabase(), SETTINGS, _event(aspect_type="create"))

    assert strava.fetched == [555]
    assert upserts[0][0]["id"] == 555
    assert upserts[0][0]["athlete_id"] == 7
    assert states[-1] == {"last_webhook_event_id": 1_700_000_000}


def test_delete_event_removes_row_without_fetch(monkeypatch):
    deleted = {}
    strava = _wire(monkeypatch)
    monkeypatch.setattr(webhooks_service.activities_db, "delete_activity",
                        lambda supabase, athlete_id, activity_id: deleted.update(
                            athlete_id=athlete_id, activity_id=activity_id))
    monkeypatch.setattr(webhooks_service.sync_state_db, "upsert_sync_state",
                        lambda supabase, athlete_id, fields: None)

    webhooks_service.process_event(FakeSupabase(), SETTINGS, _event(aspect_type="delete"))

    assert strava.fetched == []
    assert deleted == {"athlete_id": 7, "activity_id": 555}


def test_unknown_owner_is_ignored(monkeypatch):
    strava = _wire(monkeypatch, athlete=False)

    def fail_upsert(*a: object, **k: object) -> None:
        raise AssertionError("must not upsert for unknown owner")

    monkeypatch.setattr(webhooks_service.activities_db, "upsert_activities", fail_upsert)
    webhooks_service.process_event(FakeSupabase(), SETTINGS, _event())
    assert strava.fetched == []


def test_non_activity_event_builds_no_clients(monkeypatch):
    def fail(*a: object, **k: object) -> None:
        raise AssertionError("must not build a strava client for non-activity events")

    monkeypatch.setattr(webhooks_service, "build_strava", fail)
    webhooks_service.process_event(
        FakeSupabase(), SETTINGS, _event(object_type="athlete", aspect_type="update")
    )


def test_foreign_subscription_id_is_ignored(monkeypatch):
    def fail(*a: object, **k: object) -> None:
        raise AssertionError("must not build a strava client for a foreign subscription id")

    monkeypatch.setattr(webhooks_service, "build_strava", fail)
    settings = Settings(strava_webhook_subscription_id=999)
    # Event carries subscription_id=1, which does not match the configured 999.
    webhooks_service.process_event(FakeSupabase(), settings, _event(subscription_id=1))


def test_fetch_error_is_swallowed(monkeypatch):
    _wire(monkeypatch)

    def boom(access_token, activity_id):
        raise RuntimeError("strava 500")

    # Replace the fake strava's get_activity with a raising one.
    monkeypatch.setattr(webhooks_service, "build_strava",
                        lambda settings: type("S", (), {"get_activity": staticmethod(boom),
                                                         "close": lambda self: None})())

    def fail_state(*a: object, **k: object) -> None:
        raise AssertionError("must not record marker when processing failed")

    monkeypatch.setattr(webhooks_service.sync_state_db, "upsert_sync_state", fail_state)
    # Should not raise.
    webhooks_service.process_event(FakeSupabase(), SETTINGS, _event(aspect_type="update"))


def test_create_event_stores_segment_efforts(monkeypatch):
    stored = {}
    strava = _wire(monkeypatch)

    # detail payload carries one segment effort
    def detail(access_token, activity_id):
        strava.fetched.append(activity_id)
        return {
            "id": activity_id, "name": "Ride", "type": "Ride",
            "start_date": "2026-06-21T08:00:00Z", "distance": 1000.0,
            "moving_time": 100, "elapsed_time": 110, "total_elevation_gain": 5.0,
            "segment_efforts": [{
                "id": 1, "elapsed_time": 60,
                "start_date": "2026-06-21T08:00:00Z", "average_watts": 200.0,
                "average_heartrate": 150.0,
                "segment": {
                    "id": 2, "name": "Sprint", "distance": 500.0,
                    "average_grade": 1.0
                }
            }]
        }

    monkeypatch.setattr(strava, "get_activity", detail)
    monkeypatch.setattr(webhooks_service.activities_db, "upsert_activities",
                        lambda supabase, rows: None)
    monkeypatch.setattr(webhooks_service.sync_state_db, "upsert_sync_state",
                        lambda supabase, athlete_id, fields: None)
    monkeypatch.setattr(webhooks_service.activities_db, "mark_detail_fetched",
                        lambda supabase, activity_id, splits_metric, fetched_at: None)

    def mock_store(supabase, athlete_id, det):
        stored.update(athlete=athlete_id, det=det)

    monkeypatch.setattr(webhooks_service.segments_service, "store_activity_efforts",
                        mock_store)

    webhooks_service.process_event(FakeSupabase(), SETTINGS, _event(aspect_type="create"))
    assert stored["athlete"] == 7
    assert stored["det"]["segment_efforts"][0]["segment"]["id"] == 2


def test_create_event_marks_detail_fetched(monkeypatch):
    marked = {}
    _wire(monkeypatch)
    monkeypatch.setattr(webhooks_service.activities_db, "upsert_activities",
                        lambda supabase, rows: None)
    monkeypatch.setattr(webhooks_service.sync_state_db, "upsert_sync_state",
                        lambda supabase, athlete_id, fields: None)
    monkeypatch.setattr(webhooks_service.segments_service, "store_activity_efforts",
                        lambda supabase, athlete_id, det: None)

    def mock_mark(supabase, activity_id, splits_metric, fetched_at):
        marked.update(activity_id=activity_id, splits=splits_metric, fetched_at=fetched_at)

    monkeypatch.setattr(webhooks_service.activities_db, "mark_detail_fetched",
                        mock_mark)

    webhooks_service.process_event(FakeSupabase(), SETTINGS, _event(aspect_type="create"))
    assert marked["activity_id"] == 555
    assert "fetched_at" in marked and marked["fetched_at"]


def test_delete_event_does_not_mark_detail_fetched(monkeypatch):
    marked = {}
    _wire(monkeypatch)
    monkeypatch.setattr(webhooks_service.activities_db, "delete_activity",
                        lambda supabase, athlete_id, activity_id: None)
    monkeypatch.setattr(webhooks_service.sync_state_db, "upsert_sync_state",
                        lambda supabase, athlete_id, fields: None)

    def mock_mark(supabase, activity_id, splits_metric, fetched_at):
        marked.update(activity_id=activity_id)

    monkeypatch.setattr(webhooks_service.activities_db, "mark_detail_fetched",
                        mock_mark)

    webhooks_service.process_event(FakeSupabase(), SETTINGS, _event(aspect_type="delete"))
    assert not marked
