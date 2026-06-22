from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.deps import get_current_athlete_id, get_supabase
from app.models.segments import (
    SegmentDetailResponse,
    SegmentListResponse,
    SegmentSortDir,
    SegmentSortField,
)
from app.services import segments as segments_service

router = APIRouter()


@router.get("", response_model=SegmentListResponse)
def list_segments(
    q: str | None = None,
    sort: SegmentSortField = "attempts",
    direction: SegmentSortDir = "desc",
    page: int = Query(1, ge=1),
    as_of: datetime | None = None,
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: Client = Depends(get_supabase),
) -> SegmentListResponse:
    return segments_service.list_segments(
        supabase, athlete_id, q=q, sort=sort, direction=direction, page=page, as_of=as_of
    )


@router.get("/{segment_id}", response_model=SegmentDetailResponse)
def get_segment(
    segment_id: int,
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: Client = Depends(get_supabase),
) -> SegmentDetailResponse:
    try:
        return segments_service.get_segment(supabase, athlete_id, segment_id)
    except segments_service.SegmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Segment not found") from exc
