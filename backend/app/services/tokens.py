from datetime import UTC, datetime

from supabase import Client

from app.db import tokens as tokens_db
from app.strava import StravaClient

REFRESH_BUFFER_S = 60


def get_valid_access_token(
    supabase: Client,
    strava: StravaClient,
    athlete_id: int,
    *,
    now: datetime | None = None,
) -> str:
    current = now or datetime.now(UTC)
    row = tokens_db.get_tokens(supabase, athlete_id)
    if row is None:
        raise ValueError(f"No Strava tokens stored for athlete {athlete_id}")
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at.timestamp() - current.timestamp() > REFRESH_BUFFER_S:
        return row["access_token"]
    token = strava.refresh(row["refresh_token"])
    tokens_db.upsert_tokens(
        supabase, athlete_id, token.access_token, token.refresh_token, token.expires_at
    )
    return token.access_token
