import logging

from supabase import Client

from app.clients import build_strava
from app.config import Settings
from app.db import activities as activities_db
from app.db import athletes as athletes_db
from app.db import sync_state as sync_state_db
from app.models.webhooks import StravaWebhookEvent
from app.services import segments as segments_service
from app.services import sync as sync_service
from app.services.tokens import get_valid_access_token

logger = logging.getLogger(__name__)


def process_event(
    supabase: Client, settings: Settings, event: StravaWebhookEvent
) -> None:
    """Ingest one Strava webhook event: fetch+upsert or delete the activity.

    Runs as a background task on the shared Supabase client. Builds its own Strava
    client; ignores non-activity, foreign-subscription, and unknown-owner events;
    and swallows errors (we have already returned 200 to Strava).
    """
    if event.object_type != "activity":
        logger.info("Ignoring non-activity webhook event: %s", event.object_type)
        return
    if (
        settings.strava_webhook_subscription_id
        and event.subscription_id != settings.strava_webhook_subscription_id
    ):
        logger.warning("Ignoring webhook from unexpected subscription %s",
                       event.subscription_id)
        return

    strava = build_strava(settings)
    try:
        if athletes_db.get_athlete(supabase, event.owner_id) is None:
            logger.info("Ignoring webhook for unknown athlete %s", event.owner_id)
            return

        if event.aspect_type == "delete":
            activities_db.delete_activity(supabase, event.owner_id, event.object_id)
        else:  # "create" or "update"
            access_token = get_valid_access_token(supabase, strava, event.owner_id)
            detail = strava.get_activity(access_token, event.object_id)
            row = sync_service._to_activity_row(event.owner_id, detail)
            activities_db.upsert_activities(supabase, [row])  # type: ignore[list-item]
            segments_service.store_activity_efforts(supabase, event.owner_id, detail)

        sync_state_db.upsert_sync_state(
            supabase, event.owner_id, {"last_webhook_event_id": event.event_time}
        )
    except Exception:
        logger.exception("Failed to process webhook for athlete %s", event.owner_id)
    finally:
        strava.close()
