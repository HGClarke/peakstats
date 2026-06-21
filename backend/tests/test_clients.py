from app.clients import build_strava, build_supabase
from app.config import Settings
from supabase import Client


def _settings() -> Settings:
    return Settings(
        supabase_url="https://test.supabase.co",
        supabase_service_role_key="svc",
        backend_base_url="http://localhost:8000",
        strava_client_id="cid",
        strava_client_secret="sec",
    )


def test_build_supabase_returns_supabase_client():
    client = build_supabase(_settings())
    assert isinstance(client, Client)
    assert callable(client.table)


def test_build_strava_returns_configured_client():
    strava = build_strava(_settings())
    try:
        url = strava.authorize_url("state123")
        assert "client_id=cid" in url
        assert "state=state123" in url
    finally:
        strava.close()
