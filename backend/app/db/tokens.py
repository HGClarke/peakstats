from datetime import datetime
from typing import TypedDict, cast

from supabase import Client


class TokenRow(TypedDict):
    """Shape of a row in the `strava_tokens` table as returned by PostgREST."""

    athlete_id: int
    access_token: str
    refresh_token: str
    expires_at: str  # ISO-8601 timestamp string


def upsert_tokens(
    client: Client,
    athlete_id: int,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
) -> None:
    """Insert or update a Strava token row for the athlete, merging on athlete_id."""
    client.table("strava_tokens").upsert(
        {
            "athlete_id": athlete_id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at.isoformat(),
        },
        on_conflict="athlete_id",
    ).execute()


def get_tokens(client: Client, athlete_id: int) -> TokenRow | None:
    """Return the stored Strava tokens for the athlete, or None if not found."""
    resp = (
        client.table("strava_tokens")
        .select("*")
        .eq("athlete_id", athlete_id)
        .execute()
    )
    return cast(TokenRow, resp.data[0]) if resp.data else None
