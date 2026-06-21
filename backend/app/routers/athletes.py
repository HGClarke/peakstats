import httpx
from fastapi import APIRouter, Depends, HTTPException, Response

from app.config import Settings, get_settings
from app.cookies import clear_session_cookie
from app.deps import get_current_athlete_id, get_strava, get_supabase
from app.models.athlete import AthleteResponse
from app.services import athletes as athletes_service
from app.strava import StravaClient

router = APIRouter()


@router.get("", response_model=AthleteResponse)
def get_athlete(
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: httpx.Client = Depends(get_supabase),
) -> AthleteResponse:
    """Return the authenticated athlete's profile; 404 if the record is missing."""
    profile = athletes_service.get_profile(supabase, athlete_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Athlete not found")
    return profile


@router.delete("/connection", status_code=204)
def disconnect(
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: httpx.Client = Depends(get_supabase),
    strava: StravaClient = Depends(get_strava),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Revoke Strava access, delete athlete data, and clear the session cookie."""
    athletes_service.disconnect(supabase, strava, athlete_id)
    response = Response(status_code=204)
    clear_session_cookie(response, settings)
    return response
