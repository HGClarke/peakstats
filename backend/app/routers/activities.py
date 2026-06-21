import httpx
from fastapi import APIRouter, Depends

from app.deps import get_current_athlete_id, get_supabase
from app.models.activities import OverviewResponse
from app.services import activities as activities_service

router = APIRouter()


@router.get("/overview", response_model=OverviewResponse)
def overview(
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: httpx.Client = Depends(get_supabase),
) -> OverviewResponse:
    return activities_service.get_overview(supabase, athlete_id)
