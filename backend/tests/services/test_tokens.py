from datetime import UTC, datetime, timedelta

import pytest
from app.services import tokens as tokens_service
from app.strava import StravaToken


class FakeStrava:
    def __init__(self) -> None:
        self.refreshed_with: str | None = None

    def refresh(self, refresh_token: str) -> StravaToken:
        self.refreshed_with = refresh_token
        return StravaToken("NEW_AT", "NEW_RT",
                           datetime(2099, 1, 1, tzinfo=UTC))


def test_returns_existing_token_when_not_expiring(monkeypatch):
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    monkeypatch.setattr(tokens_service.tokens_db, "get_tokens",
                        lambda supabase, athlete_id: {"access_token": "AT",
                                                      "refresh_token": "RT",
                                                      "expires_at": future})
    strava = FakeStrava()
    token = tokens_service.get_valid_access_token(object(), strava, 7)
    assert token == "AT"
    assert strava.refreshed_with is None


def test_refreshes_and_persists_when_expiring(monkeypatch):
    soon = (datetime.now(UTC) + timedelta(seconds=5)).isoformat()
    saved = {}
    monkeypatch.setattr(tokens_service.tokens_db, "get_tokens",
                        lambda supabase, athlete_id: {"access_token": "OLD",
                                                      "refresh_token": "RT",
                                                      "expires_at": soon})
    monkeypatch.setattr(tokens_service.tokens_db, "upsert_tokens",
                        lambda supabase, athlete_id, access_token, refresh_token, expires_at:
                        saved.update(at=access_token, rt=refresh_token))
    strava = FakeStrava()
    token = tokens_service.get_valid_access_token(object(), strava, 7)
    assert token == "NEW_AT"
    assert strava.refreshed_with == "RT"
    assert saved == {"at": "NEW_AT", "rt": "NEW_RT"}


def test_raises_when_no_tokens(monkeypatch):
    monkeypatch.setattr(tokens_service.tokens_db, "get_tokens",
                        lambda supabase, athlete_id: None)
    with pytest.raises(ValueError):
        tokens_service.get_valid_access_token(object(), FakeStrava(), 7)
