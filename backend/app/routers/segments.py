from fastapi import APIRouter, Depends
from supabase import Client

from app.deps import get_current_athlete_id, get_supabase
from app.models.segments import SegmentListResponse, SegmentSortDir, SegmentSortField
from app.services import segments as segments_service

router = APIRouter()


@router.get("", response_model=SegmentListResponse)
def list_segments(
    q: str | None = None,
    sort: SegmentSortField = "attempts",
    direction: SegmentSortDir = "desc",
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: Client = Depends(get_supabase),
) -> SegmentListResponse:
    return segments_service.list_segments(
        supabase, athlete_id, q=q, sort=sort, direction=direction
    )
