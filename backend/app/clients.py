import httpx
from supabase import Client, ClientOptions, create_client

from app.config import Settings
from app.strava import StravaClient


def build_supabase(settings: Settings) -> Client:
    """A Supabase client configured with the service-role key.

    `create_client` performs no network I/O, so this is safe to call at startup.
    The client wraps a synchronous httpx session (connection pooling + keep-alive);
    share one instance for the app's lifetime (see app.main lifespan).
    """
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
        options=ClientOptions(postgrest_client_timeout=10),
    )


def build_strava(settings: Settings) -> StravaClient:
    """A StravaClient backed by a short-lived httpx session."""
    redirect_uri = f"{settings.backend_base_url}/auth/strava/callback"
    http = httpx.Client(timeout=10)
    return StravaClient(
        http, settings.strava_client_id, settings.strava_client_secret, redirect_uri
    )
