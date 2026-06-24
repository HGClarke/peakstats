from app.services import activities as svc


class _Strava:
    def __init__(self): self.calls = 0
    def get_activity_streams(self, token, aid, keys, resolution="high"):
        self.calls += 1
        return {"time": [0, 1], "distance": [0.0, 5.0], "watts": [100, 200]}


def test_ensure_streams_returns_cached_without_fetch(monkeypatch):
    saved = {}
    monkeypatch.setattr(svc.streams_db, "get_streams",
        lambda c, aid: {"activity_id": aid, "athlete_id": 7,
                        "data": {"time": [0, 1], "watts": [100, 200]},
                        "resolution": "high", "point_count": 2})
    monkeypatch.setattr(svc.metrics_db, "upsert_metrics", lambda c, row: saved.update(row))
    strava = _Strava()
    data = svc.ensure_streams(object(), strava, 7, 5)
    assert data == {"time": [0, 1], "watts": [100, 200]} and strava.calls == 0
    # metrics self-heal on cache hit
    assert saved["activity_id"] == 5 and saved["has_power"] is True


def test_ensure_streams_fetches_persists_on_miss(monkeypatch):
    saved, metrics = {}, {}
    monkeypatch.setattr(svc.streams_db, "get_streams", lambda c, aid: None)
    monkeypatch.setattr(svc.streams_db, "upsert_streams", lambda c, row: saved.update(row))
    monkeypatch.setattr(svc.metrics_db, "upsert_metrics", lambda c, row: metrics.update(row))
    monkeypatch.setattr(svc, "get_valid_access_token", lambda c, s, a: "tok")
    data = svc.ensure_streams(object(), _Strava(), 7, 5)
    assert data["watts"] == [100, 200]
    assert saved["point_count"] == 2 and saved["activity_id"] == 5 and saved["athlete_id"] == 7
    assert metrics["activity_id"] == 5 and metrics["athlete_id"] == 7
    assert metrics["has_power"] is True


def test_ensure_streams_sentinel_when_strava_empty(monkeypatch):
    saved = {}
    monkeypatch.setattr(svc.streams_db, "get_streams", lambda c, aid: None)
    monkeypatch.setattr(svc.streams_db, "upsert_streams", lambda c, row: saved.update(row))
    monkeypatch.setattr(svc, "get_valid_access_token", lambda c, s, a: "tok")
    monkeypatch.setattr(svc.metrics_db, "upsert_metrics", lambda c, row: None)

    class Empty:
        def get_activity_streams(self, *a: object, **k: object) -> dict:  # noqa: ANN001
            return {}
    data = svc.ensure_streams(object(), Empty(), 7, 5)
    assert data == {} and saved["point_count"] == 0


def test_get_streams_payload_shapes_channels(monkeypatch):
    monkeypatch.setattr(svc, "ensure_streams",
        lambda c, s, a, aid: {"time": [0, 1], "distance": [0.0, 5.0], "watts": [100, 200]})
    out = svc.get_streams_payload(object(), object(), 7, 5)
    assert out.point_count == 2
    assert out.watts == [100, 200] and out.altitude is None and out.heartrate is None
