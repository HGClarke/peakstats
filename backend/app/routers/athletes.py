from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_current_athlete_id, get_supabase
from app.models.athlete import AthleteResponse
from app.services import athletes as athletes_service

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
