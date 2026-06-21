import httpx

from app.config import Settings
from app.strava import StravaClient


def build_supabase(settings: Settings) -> httpx.Client:
    """A short-lived httpx client pre-configured for the Supabase REST API."""
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }
    return httpx.Client(
        base_url=f"{settings.supabase_url}/rest/v1", headers=headers, timeout=10
    )


def build_strava(settings: Settings) -> StravaClient:
    """A StravaClient backed by a short-lived httpx session."""
    redirect_uri = f"{settings.backend_base_url}/auth/strava/callback"
    http = httpx.Client(timeout=10)
    return StravaClient(
        http, settings.strava_client_id, settings.strava_client_secret, redirect_uri
    )
