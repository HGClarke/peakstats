from datetime import UTC, datetime, timedelta

import httpx
from supabase import Client

from app.db import athletes as athletes_db
from app.db import tokens as tokens_db
from app.models.athlete import AthleteResponse
from app.strava import StravaClient


def get_profile(supabase: Client, athlete_id: int) -> AthleteResponse | None:
    """Fetch athlete from the DB and return a response model, or None if not found."""
    row = athletes_db.get_athlete(supabase, athlete_id)
    if row is None:
        return None
    return AthleteResponse(
        id=row["id"],
        name=row["name"],
        avatar_url=row.get("avatar_url"),
        settings=row["settings"],
    )


def disconnect(supabase: Client, strava: StravaClient, athlete_id: int) -> None:
    """Revoke Strava access (best-effort) and delete all athlete data from the DB."""
    tokens = tokens_db.get_tokens(supabase, athlete_id)
    if tokens:
        access_token = tokens["access_token"]
        expires_at = datetime.fromisoformat(tokens["expires_at"])
        if expires_at <= datetime.now(UTC) + timedelta(seconds=60):
            access_token = strava.refresh(tokens["refresh_token"]).access_token
        try:
            strava.deauthorize(access_token)
        except httpx.HTTPError:
            pass  # best-effort: still drop local data if Strava is unreachable
    athletes_db.delete_athlete(supabase, athlete_id)
