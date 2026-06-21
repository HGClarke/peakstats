from collections.abc import Iterator

import httpx
from fastapi import Depends, HTTPException, Request

from app.config import Settings, get_settings
from app.session import SESSION_COOKIE, read_session
from app.strava import StravaClient

__all__ = ["get_settings", "get_supabase", "get_strava", "get_current_athlete_id"]


def get_supabase(settings: Settings = Depends(get_settings)) -> Iterator[httpx.Client]:
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(
        base_url=f"{settings.supabase_url}/rest/v1", headers=headers, timeout=10
    ) as client:
        yield client


def get_strava(settings: Settings = Depends(get_settings)) -> Iterator[StravaClient]:
    redirect_uri = f"{settings.backend_base_url}/auth/strava/callback"
    with httpx.Client(timeout=10) as http:
        yield StravaClient(
            http, settings.strava_client_id, settings.strava_client_secret, redirect_uri
        )


def get_current_athlete_id(
    request: Request, settings: Settings = Depends(get_settings)
) -> int:
    token = request.cookies.get(SESSION_COOKIE)
    athlete_id = read_session(token, settings.session_secret) if token else None
    if athlete_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return athlete_id
