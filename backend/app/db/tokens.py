from datetime import datetime
from typing import TypedDict

import httpx

_MERGE = {"Prefer": "resolution=merge-duplicates"}


class TokenRow(TypedDict):
    """Shape of a row in the `strava_tokens` table as returned by PostgREST."""

    athlete_id: int
    access_token: str
    refresh_token: str
    expires_at: str  # ISO-8601 timestamp string


def upsert_tokens(
    client: httpx.Client,
    athlete_id: int,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
) -> None:
    """Insert or update a Strava token row for the athlete, merging on athlete_id."""
    response = client.post(
        "/strava_tokens",
        params={"on_conflict": "athlete_id"},
        headers=_MERGE,
        json=[
            {
                "athlete_id": athlete_id,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at.isoformat(),
            }
        ],
    )
    response.raise_for_status()


def get_tokens(client: httpx.Client, athlete_id: int) -> TokenRow | None:
    """Return the stored Strava tokens for the athlete, or None if not found."""
    response = client.get(
        "/strava_tokens", params={"athlete_id": f"eq.{athlete_id}", "select": "*"}
    )
    response.raise_for_status()
    rows = response.json()
    return rows[0] if rows else None
