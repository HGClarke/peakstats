from fastapi import APIRouter, Depends, HTTPException, Response

from app.config import Settings, get_settings
from app.deps import get_current_athlete_id, get_strava, get_supabase
from app.models.athlete import AthleteResponse
from app.services import athletes as athletes_service
from app.session import SESSION_COOKIE

router = APIRouter()


@router.get("", response_model=AthleteResponse)
def get_athlete(
    athlete_id: int = Depends(get_current_athlete_id),
    supabase=Depends(get_supabase),
) -> AthleteResponse:
    profile = athletes_service.get_profile(supabase, athlete_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Athlete not found")
    return profile


@router.delete("/connection", status_code=204)
def disconnect(
    athlete_id: int = Depends(get_current_athlete_id),
    supabase=Depends(get_supabase),
    strava=Depends(get_strava),
    settings: Settings = Depends(get_settings),
) -> Response:
    athletes_service.disconnect(supabase, strava, athlete_id)
    response = Response(status_code=204)
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
    )
    return response
