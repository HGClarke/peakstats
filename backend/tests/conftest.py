import os

# The app lifespan builds a real supabase client at startup (create_client, which is
# I/O-free but rejects empty creds). Give the test process valid-looking creds before
# importing the app so startup succeeds; the client is never hit because tests override
# get_supabase below.
os.environ["SUPABASE_URL"] = os.environ.get("SUPABASE_URL") or "https://test.supabase.co"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "svc"
)

import pytest  # noqa: E402
from app.config import Settings, get_settings  # noqa: E402
from app.deps import get_strava, get_supabase  # noqa: E402
from app.main import create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


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
