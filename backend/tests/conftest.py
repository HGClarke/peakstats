import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.deps import get_strava, get_supabase
from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        session_secret="test-secret",
        frontend_origin="http://localhost:5173",
        backend_base_url="http://localhost:8000",
        supabase_url="https://test.supabase.co",
        supabase_service_role_key="svc",
        strava_client_id="cid",
        strava_client_secret="sec",
    )
    app.dependency_overrides[get_supabase] = lambda: "supabase-sentinel"
    app.dependency_overrides[get_strava] = lambda: "strava-sentinel"
    with TestClient(app) as test_client:
        yield test_client
