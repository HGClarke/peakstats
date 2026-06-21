from datetime import datetime, timedelta, timezone

import httpx

from app.db import athletes as athletes_db
from app.db import tokens as tokens_db
from app.models.athlete import AthleteResponse
from app.strava import StravaClient


def get_profile(supabase: httpx.Client, athlete_id: int) -> AthleteResponse | None:
    row = athletes_db.get_athlete(supabase, athlete_id)
    if row is None:
        return None
    return AthleteResponse(
        id=row["id"],
        name=row["name"],
        avatar_url=row.get("avatar_url"),
        settings=row["settings"],
    )


def disconnect(supabase: httpx.Client, strava: StravaClient, athlete_id: int) -> None:
    tokens = tokens_db.get_tokens(supabase, athlete_id)
    if tokens:
        access_token = tokens["access_token"]
        expires_at = datetime.fromisoformat(tokens["expires_at"])
        if expires_at <= datetime.now(timezone.utc) + timedelta(seconds=60):
            access_token = strava.refresh(tokens["refresh_token"]).access_token
        try:
            strava.deauthorize(access_token)
        except httpx.HTTPError:
            pass  # best-effort: still drop local data if Strava is unreachable
    athletes_db.delete_athlete(supabase, athlete_id)
