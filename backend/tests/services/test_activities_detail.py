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
    d = svc.get_detail(object(), object(), 7, 5)
    assert d.name == "Saturday Gravel Loop" and d.distance_m == 84300.0
    assert d.avg_hr == 148 and d.summary_polyline == "abc"
    assert round(d.avg_power_w) == 200
    assert d.normalized_power_w is not None and d.work_kj is not None


def test_get_detail_nulls_power_without_watts(monkeypatch):
    monkeypatch.setattr(svc.activities_db, "get_activity", lambda c, a, aid: dict(ROW))
    monkeypatch.setattr(svc, "ensure_streams", lambda c, s, a, aid: {"time": [0, 1]})
    d = svc.get_detail(object(), object(), 7, 5)
    assert d.avg_power_w is None and d.normalized_power_w is None and d.work_kj is None


def test_get_detail_raises_when_missing(monkeypatch):
    monkeypatch.setattr(svc.activities_db, "get_activity", lambda c, a, aid: None)
    with pytest.raises(svc.ActivityNotFoundError):
        svc.get_detail(object(), object(), 7, 5)
