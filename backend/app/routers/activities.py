from datetime import datetime

from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.deps import get_current_athlete_id, get_strava, get_supabase
from app.models.activities import (
    ActivityListResponse,
    ActivityStreamsResponse,
    OverviewResponse,
    SortDir,
    SortField,
)
from app.services import activities as activities_service
from app.strava import StravaClient

router = APIRouter()


@router.get("", response_model=ActivityListResponse)
def list_activities(
    q: str | None = None,
    min_dist: float | None = None,
    min_time: int | None = None,
    min_elev: float | None = None,
    sort: SortField = "date",
    direction: SortDir = "desc",
    page: int = Query(1, ge=1),
    as_of: datetime | None = None,
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: Client = Depends(get_supabase),
) -> ActivityListResponse:
    return activities_service.list_activities(
        supabase, athlete_id,
        q=q, min_dist=min_dist, min_time=min_time, min_elev=min_elev,
        sort=sort, direction=direction, page=page, as_of=as_of,
    )


@router.get("/overview", response_model=OverviewResponse)
def overview(
    tz: str = Query("UTC"),
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: Client = Depends(get_supabase),
) -> OverviewResponse:
    return activities_service.get_overview(supabase, athlete_id, tz=tz)


@router.get("/{activity_id}/streams", response_model=ActivityStreamsResponse)
def activity_streams(
    activity_id: int,
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: Client = Depends(get_supabase),
    strava: StravaClient = Depends(get_strava),
) -> ActivityStreamsResponse:
    return activities_service.get_streams_payload(supabase, strava, athlete_id, activity_id)
