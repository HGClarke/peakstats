from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from supabase import Client

from app.clients import build_strava
from app.config import Settings, get_settings
from app.session import SESSION_COOKIE, read_session
from app.strava import StravaClient

__all__ = ["get_settings", "get_supabase", "get_strava", "get_current_athlete_id"]


def get_supabase(request: Request) -> Client:
    """Return the process-wide shared Supabase client (created in the app lifespan)."""
    return request.app.state.supabase


def get_strava(settings: Settings = Depends(get_settings)) -> Iterator[StravaClient]:
    """Yield a StravaClient backed by a short-lived httpx session."""
    strava = build_strava(settings)
    try:
        yield strava
    finally:
        strava.close()


def get_current_athlete_id(
    request: Request, settings: Settings = Depends(get_settings)
) -> int:
    """Return the athlete ID from the signed session cookie; raise 401 if missing or invalid."""
    token = request.cookies.get(SESSION_COOKIE)
    athlete_id = read_session(token, settings.session_secret) if token else None
    if athlete_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return athlete_id
