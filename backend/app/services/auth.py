import secrets

import httpx

from app.db import athletes as athletes_db
from app.db import tokens as tokens_db
from app.strava import StravaClient


def start_login(strava: StravaClient) -> tuple[str, str]:
    """Generate a CSRF state token and return (authorization_url, state)."""
    state = secrets.token_urlsafe(32)
    return strava.authorize_url(state), state


def handle_callback(code: str, supabase: httpx.Client, strava: StravaClient) -> int:
    """Exchange the OAuth code, upsert athlete and tokens in DB, and return the athlete ID."""
    token = strava.exchange_code(code)
    athlete = token.athlete
    name = f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip()
    athletes_db.upsert_athlete(supabase, athlete["id"], name, athlete.get("profile"))
    tokens_db.upsert_tokens(
        supabase, athlete["id"], token.access_token, token.refresh_token, token.expires_at
    )
    return athlete["id"]
