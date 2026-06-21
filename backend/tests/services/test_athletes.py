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
