from app.clients import build_strava, build_supabase
from app.config import Settings


def _settings() -> Settings:
    return Settings(
        supabase_url="https://test.supabase.co",
        supabase_service_role_key="svc",
        backend_base_url="http://localhost:8000",
        strava_client_id="cid",
        strava_client_secret="sec",
    )


def test_build_supabase_sets_base_url_and_auth_headers():
    client = build_supabase(_settings())
    try:
        assert str(client.base_url) == "https://test.supabase.co/rest/v1/"
        assert client.headers["apikey"] == "svc"
        assert client.headers["Authorization"] == "Bearer svc"
    finally:
        client.close()


def test_build_strava_returns_configured_client():
    strava = build_strava(_settings())
    try:
        url = strava.authorize_url("state123")
        assert "client_id=cid" in url
        assert "state=state123" in url
    finally:
        strava.close()
