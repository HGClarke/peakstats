import logging
from datetime import UTC, datetime

from supabase import Client

from app.clients import build_strava
from app.config import Settings
from app.db import activities as activities_db
from app.db import sync_state as sync_state_db
from app.models.sync import RefreshResponse, SyncStatusResponse
from app.services.tokens import get_valid_access_token

logger = logging.getLogger(__name__)

PER_PAGE = 200


class SyncNotReadyError(Exception):
    """Raised when an incremental refresh is attempted before a backfill completes."""


def _to_activity_row(athlete_id: int, summary: dict) -> dict:
    hr = summary.get("average_heartrate")
    activity_map = summary.get("map") or {}
    return {
        "id": summary["id"],
        "athlete_id": athlete_id,
        "name": summary.get("name") or "Untitled",
        "type": summary.get("sport_type") or summary.get("type") or "Workout",
        "start_date": summary["start_date"],
        "start_date_local": summary.get("start_date_local"),
        "distance_m": summary.get("distance", 0.0),
        "moving_time_s": summary.get("moving_time", 0),
        "elapsed_time_s": summary.get("elapsed_time", 0),
        "elev_gain_m": summary.get("total_elevation_gain", 0.0),
        "avg_speed_ms": summary.get("average_speed"),
        "avg_hr": round(hr) if hr is not None else None,
        "summary_polyline": activity_map.get("summary_polyline"),
    }


def get_status(supabase: Client, athlete_id: int) -> SyncStatusResponse:
    row = sync_state_db.get_sync_state(supabase, athlete_id)
    synced = activities_db.count_activities(supabase, athlete_id)
    if row is None:
        return SyncStatusResponse(status="never_synced", progress=0, synced=synced)
    # A row with no completed backfill (e.g. one created by a refresh upsert filling
    # column defaults) is not a real synced state — treat it as never_synced so the
    # first-sync flow runs and self-heals.
    if row["last_backfill_at"] is None and row["status"] not in (
        "backfilling",
        "error",
    ):
        return SyncStatusResponse(status="never_synced", progress=0, synced=synced)
    return SyncStatusResponse(
        status=row["status"],
        progress=row["progress"],
        synced=synced,
        last_backfill_at=row["last_backfill_at"],
        last_sync_at=row["last_sync_at"],
    )


def start_backfill(
    supabase: Client, athlete_id: int
) -> tuple[SyncStatusResponse, bool]:
    row = sync_state_db.get_sync_state(supabase, athlete_id)
    already_running = row is not None and row["status"] == "backfilling"
    if not already_running:
        sync_state_db.upsert_sync_state(
            supabase, athlete_id, {"status": "backfilling", "progress": 0}
        )
    return get_status(supabase, athlete_id), not already_running


def run_backfill(supabase: Client, settings: Settings, athlete_id: int) -> None:
    strava = build_strava(settings)
    try:
        access_token = get_valid_access_token(supabase, strava, athlete_id)
        page = 1
        while True:
            summaries = strava.list_activities(
                access_token, page=page, per_page=PER_PAGE
            )
            if not summaries:
                break
            rows = [_to_activity_row(athlete_id, s) for s in summaries]
            activities_db.upsert_activities(supabase, rows)  # type: ignore[arg-type]
            sync_state_db.upsert_sync_state(
                supabase, athlete_id,
                {"status": "backfilling", "progress": min(95, page * 10)},
            )
            if len(summaries) < PER_PAGE:
                break
            page += 1
        now = datetime.now(UTC).isoformat()
        sync_state_db.upsert_sync_state(
            supabase, athlete_id,
            {"status": "idle", "progress": 100,
             "last_backfill_at": now, "last_sync_at": now},
        )
    except Exception:
        logger.exception("Backfill failed for athlete %s", athlete_id)
        sync_state_db.upsert_sync_state(supabase, athlete_id, {"status": "error"})
    finally:
        strava.close()


def refresh(supabase: Client, settings: Settings, athlete_id: int) -> RefreshResponse:
    strava = build_strava(settings)
    try:
        access_token = get_valid_access_token(supabase, strava, athlete_id)
        row = sync_state_db.get_sync_state(supabase, athlete_id)
        if row is None or row["last_backfill_at"] is None:
            raise SyncNotReadyError(
                "Refresh requires a completed initial backfill"
            )
        after: int | None = None
        if row["last_sync_at"] is not None:
            after = int(datetime.fromisoformat(row["last_sync_at"]).timestamp())
        count = 0
        page = 1
        while True:
            summaries = strava.list_activities(
                access_token, page=page, per_page=PER_PAGE, after=after
            )
            if not summaries:
                break
            rows = [_to_activity_row(athlete_id, s) for s in summaries]
            activities_db.upsert_activities(supabase, rows)  # type: ignore[arg-type]
            count += len(summaries)
            if len(summaries) < PER_PAGE:
                break
            page += 1
        now = datetime.now(UTC).isoformat()
        sync_state_db.upsert_sync_state(
            supabase, athlete_id, {"last_sync_at": now}
        )
        return RefreshResponse(synced=count)
    finally:
        strava.close()
