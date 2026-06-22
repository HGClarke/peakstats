import pytest
from app.services import activities as svc

ROW = {"id": 5, "athlete_id": 7, "name": "Saturday Gravel Loop", "type": "Ride",
       "start_date": "2026-06-21T14:42:00Z", "start_date_local": "2026-06-21T07:42:00",
       "distance_m": 84300.0, "moving_time_s": 11820, "elapsed_time_s": 12000,
       "elev_gain_m": 1284.0, "avg_speed_ms": 7.13, "avg_hr": 148,
       "summary_polyline": "abc"}


def test_get_detail_maps_header_and_power_stats(monkeypatch):
    monkeypatch.setattr(svc.activities_db, "get_activity", lambda c, a, aid: dict(ROW))
    monkeypatch.setattr(svc, "ensure_streams",
        lambda c, s, a, aid: {"time": [0, 1, 2], "watts": [200, 200, 200]})
    monkeypatch.setattr(svc.athletes_db, "get_athlete", lambda c, aid: {"settings": {}})
    d = svc.get_detail(object(), object(), 7, 5)
    assert d.name == "Saturday Gravel Loop" and d.distance_m == 84300.0
    assert d.avg_hr == 148 and d.summary_polyline == "abc"
    assert round(d.avg_power_w) == 200
    assert d.normalized_power_w is not None and d.work_kj is not None


def test_get_detail_nulls_power_without_watts(monkeypatch):
    monkeypatch.setattr(svc.activities_db, "get_activity", lambda c, a, aid: dict(ROW))
    monkeypatch.setattr(svc, "ensure_streams", lambda c, s, a, aid: {"time": [0, 1]})
    monkeypatch.setattr(svc.athletes_db, "get_athlete", lambda c, aid: {"settings": {}})
    d = svc.get_detail(object(), object(), 7, 5)
    assert d.avg_power_w is None and d.normalized_power_w is None and d.work_kj is None


def test_get_detail_raises_when_missing(monkeypatch):
    monkeypatch.setattr(svc.activities_db, "get_activity", lambda c, a, aid: None)
    with pytest.raises(svc.ActivityNotFoundError):
        svc.get_detail(object(), object(), 7, 5)


def test_get_detail_builds_zones_from_settings(monkeypatch):
    row = dict(ROW)
    monkeypatch.setattr(svc.activities_db, "get_activity", lambda c, a, aid: row)
    monkeypatch.setattr(svc, "ensure_streams",
        lambda c, s, a, aid: {"time": [0, 1, 2, 3],
                              "watts": [50, 220, 220, 600],
                              "heartrate": [120, 150, 150, 180]})
    monkeypatch.setattr(svc.athletes_db, "get_athlete",
        lambda c, aid: {"id": 7, "name": "A", "avatar_url": None,
                        "settings": {"ftp_w": 280, "hr_max": 190}})
    d = svc.get_detail(object(), object(), 7, 5)
    assert d.power_zones.unset is False
    assert round(sum(b.pct for b in d.power_zones.buckets)) == 100
    assert d.hr_zones.unset is False and d.hr_zones.avg is not None


def test_get_detail_zones_unset_without_settings(monkeypatch):
    monkeypatch.setattr(svc.activities_db, "get_activity", lambda c, a, aid: dict(ROW))
    monkeypatch.setattr(svc, "ensure_streams",
        lambda c, s, a, aid: {"time": [0, 1], "watts": [200, 210]})
    monkeypatch.setattr(svc.athletes_db, "get_athlete",
        lambda c, aid: {"id": 7, "name": "A", "avatar_url": None, "settings": {}})
    d = svc.get_detail(object(), object(), 7, 5)
    assert d.power_zones.unset is True and d.hr_zones.unset is True
