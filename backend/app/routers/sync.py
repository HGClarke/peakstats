import httpx
from fastapi import APIRouter, BackgroundTasks, Depends

from app.config import Settings, get_settings
from app.deps import get_current_athlete_id, get_supabase
from app.models.sync import SyncStatusResponse
from app.services import sync as sync_service

router = APIRouter()


@router.get("/status", response_model=SyncStatusResponse)
def status(
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: httpx.Client = Depends(get_supabase),
) -> SyncStatusResponse:
    return sync_service.get_status(supabase, athlete_id)


@router.post("/start", response_model=SyncStatusResponse)
def start(
    background_tasks: BackgroundTasks,
    athlete_id: int = Depends(get_current_athlete_id),
    supabase: httpx.Client = Depends(get_supabase),
    settings: Settings = Depends(get_settings),
) -> SyncStatusResponse:
    result, started = sync_service.start_backfill(supabase, athlete_id)
    if started:
        background_tasks.add_task(sync_service.run_backfill, settings, athlete_id)
    return result
