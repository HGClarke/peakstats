import logging
import time
from datetime import UTC, datetime

import httpx
from supabase import Client

from app.clients import build_strava
from app.config import Settings
from app.db import activities as activities_db
from app.db import sync_state as sync_state_db
from app.models.sync import RefreshResponse, SyncStatusResponse
from app.services import segments as segments_service
from app.services.tokens import get_valid_access_token

logger = logging.getLogger(__name__)

PER_PAGE = 200
DETAIL_BATCH = 50          # activities pulled per DB round-trip
DETAIL_PAUSE_S = 5.0       # ~12 calls/min = 180/15min, just under Strava's 200/15min cap
DETAIL_BACKOFF_S = 60.0    # fallback wait when a 429 carries no Retry-After


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
        "avg_watts": summary.get("average_watts"),
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


def _fetch_detail_with_backoff(strava: object, access_token: str, activity_id: int) -> dict:
    while True:
        try:
            return strava.get_activity(access_token, activity_id)  # type: ignore[attr-defined]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429:
                raise
            retry_after = exc.response.headers.get("Retry-After")
            time.sleep(float(retry_after) if retry_after else DETAIL_BACKOFF_S)


def run_detail_backfill(supabase: Client, settings: Settings, athlete_id: int) -> None:
    """Fetch detail for activities lacking it; extract efforts + store splits.

    Built for a long (~hour), rate-limited run over the full history:
    - Per-activity isolation: a single failed ride is logged and skipped (left
      with detail_fetched_at NULL) so one transient error never aborts the batch.
    - Token refreshed each iteration: access tokens expire hourly, so a multi-hour
      run re-validates before every fetch (get_valid_access_token only re-auths
      when near expiry).
    - Resumable: only activities with detail_fetched_at IS NULL are selected, and
      skipped ones stay NULL, so a later run retries them. The in-run `failed` set
      prevents re-querying the same skips in a tight loop.
    """
    strava = build_strava(settings)
    failed: set[int] = set()
    try:
        while True:
            pending = activities_db.list_activities_needing_detail(
                supabase, athlete_id, DETAIL_BATCH + len(failed)
            )
            batch = [row for row in pending if row["id"] not in failed]
            if not batch:
                break
            for row in batch:
                try:
                    access_token = get_valid_access_token(supabase, strava, athlete_id)
                    detail = _fetch_detail_with_backoff(strava, access_token, row["id"])
                    segments_service.store_activity_efforts(supabase, athlete_id, detail)
                    activities_db.mark_detail_fetched(
                        supabase, row["id"], detail.get("splits_metric"),
                        datetime.now(UTC).isoformat(),
                    )
                except Exception:
                    logger.exception(
                        "Detail backfill: skipping activity %s", row["id"]
                    )
                    failed.add(row["id"])
                time.sleep(DETAIL_PAUSE_S)
    except Exception:
        logger.exception("Detail backfill failed for athlete %s", athlete_id)
    finally:
        strava.close()
