from app.config import Settings, get_settings
from app.services import webhooks as webhooks_service


def _with_verify_token(client, token: str) -> None:
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        session_secret="test-secret", strava_webhook_verify_token=token
    )


def test_get_challenge_echoes_when_token_matches(client):
    _with_verify_token(client, "VT")
    response = client.get(
        "/webhooks/strava",
        params={"hub.mode": "subscribe", "hub.verify_token": "VT",
                "hub.challenge": "ping-123"},
    )
    assert response.status_code == 200
    assert response.json() == {"hub.challenge": "ping-123"}


def test_get_challenge_rejects_bad_token(client):
    _with_verify_token(client, "VT")
    response = client.get(
        "/webhooks/strava",
        params={"hub.mode": "subscribe", "hub.verify_token": "WRONG",
                "hub.challenge": "ping-123"},
    )
    assert response.status_code == 403


def test_post_accepts_and_schedules_processing(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(webhooks_service, "process_event",
                        lambda supabase, settings, event: seen.update(owner=event.owner_id,
                                                                      obj=event.object_id))
    response = client.post("/webhooks/strava", json={
        "aspect_type": "create", "object_type": "activity", "object_id": 555,
        "owner_id": 7, "subscription_id": 1, "event_time": 1_700_000_000,
    })
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    assert seen == {"owner": 7, "obj": 555}


def test_post_ignores_malformed_payload(client, monkeypatch):
    def fail(supabase, settings, event):
        raise AssertionError("must not schedule processing for malformed payload")

    monkeypatch.setattr(webhooks_service, "process_event", fail)
    response = client.post("/webhooks/strava", json={"hello": "world"})
    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
