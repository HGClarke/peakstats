import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import ValidationError
from supabase import Client

from app.config import Settings, get_settings
from app.deps import get_supabase
from app.models.webhooks import StravaWebhookEvent
from app.services import webhooks as webhooks_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/strava")
def validate_subscription(
    hub_challenge: str = Query("", alias="hub.challenge"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    if not hmac.compare_digest(hub_verify_token, settings.strava_webhook_verify_token):
        raise HTTPException(status_code=403, detail="Invalid verify token")
    return {"hub.challenge": hub_challenge}


@router.post("/strava")
async def receive_event(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
    supabase: Client = Depends(get_supabase),
) -> dict[str, str]:
    try:
        payload = await request.json()
        event = StravaWebhookEvent.model_validate(payload)
    except (ValueError, ValidationError):
        logger.warning("Ignoring malformed Strava webhook payload")
        return {"status": "ignored"}
    background_tasks.add_task(
        webhooks_service.process_event, supabase, settings, event
    )
    return {"status": "accepted"}
