from app.models.athlete import AthleteResponse
from app.services import athletes


def test_get_profile_maps_row(monkeypatch):
    monkeypatch.setattr(
        athletes.athletes_db, "get_athlete",
        lambda supabase, athlete_id: {
            "id": 99, "name": "Ada Lovelace", "avatar_url": "http://img/a.png",
            "settings": {"units": "metric", "theme": "dark", "default_period": "week"},
        },
    )
    profile = athletes.get_profile(object(), 99)
    assert isinstance(profile, AthleteResponse)
    assert profile.id == 99
    assert profile.name == "Ada Lovelace"
    assert profile.settings["units"] == "metric"


def test_get_profile_returns_none_when_missing(monkeypatch):
    monkeypatch.setattr(athletes.athletes_db, "get_athlete",
                        lambda supabase, athlete_id: None)
    assert athletes.get_profile(object(), 99) is None


def test_disconnect_deauthorizes_then_deletes(monkeypatch):
    from datetime import datetime, timezone

    deleted = {}
    monkeypatch.setattr(
        athletes.tokens_db, "get_tokens",
        lambda supabase, athlete_id: {
            "access_token": "AT", "refresh_token": "RT",
            "expires_at": datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat()},
    )
    monkeypatch.setattr(athletes.athletes_db, "delete_athlete",
                        lambda supabase, athlete_id: deleted.update(id=athlete_id))

    class FakeStrava:
        def __init__(self):
            self.deauthorized = []

        def deauthorize(self, access_token):
            self.deauthorized.append(access_token)

    strava = FakeStrava()
    athletes.disconnect(object(), strava, 99)
    assert strava.deauthorized == ["AT"]
    assert deleted["id"] == 99


def test_disconnect_deletes_even_with_no_tokens(monkeypatch):
    deleted = {}
    monkeypatch.setattr(athletes.tokens_db, "get_tokens",
                        lambda supabase, athlete_id: None)
    monkeypatch.setattr(athletes.athletes_db, "delete_athlete",
                        lambda supabase, athlete_id: deleted.update(id=athlete_id))
    athletes.disconnect(object(), object(), 99)
    assert deleted["id"] == 99
