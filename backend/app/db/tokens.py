import json
from datetime import datetime

import httpx

_MERGE = {"Prefer": "resolution=merge-duplicates"}


def upsert_tokens(
    client: httpx.Client,
    athlete_id: int,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
) -> None:
    response = client.post(
        "/strava_tokens",
        params={"on_conflict": "athlete_id"},
        headers=_MERGE,
        content=json.dumps(
            [
                {
                    "athlete_id": athlete_id,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_at": expires_at.isoformat(),
                }
            ],
            separators=(", ", ": "),
        ),
    )
    response.raise_for_status()


def get_tokens(client: httpx.Client, athlete_id: int) -> dict | None:
    response = client.get(
        "/strava_tokens", params={"athlete_id": f"eq.{athlete_id}", "select": "*"}
    )
    response.raise_for_status()
    rows = response.json()
    return rows[0] if rows else None
