from typing import TypedDict

import httpx

_MERGE = {"Prefer": "resolution=merge-duplicates"}


class AthleteRow(TypedDict):
    """Shape of a row in the `athletes` table as returned by PostgREST."""

    id: int
    name: str
    avatar_url: str | None
    settings: dict


def upsert_athlete(
    client: httpx.Client, athlete_id: int, name: str, avatar_url: str | None
) -> None:
    """Insert or update an athlete row, merging on the primary key."""
    response = client.post(
        "/athletes",
        params={"on_conflict": "id"},
        headers=_MERGE,
        json=[{"id": athlete_id, "name": name, "avatar_url": avatar_url}],
    )
    response.raise_for_status()


def get_athlete(client: httpx.Client, athlete_id: int) -> AthleteRow | None:
    """Return the athlete row for the given ID, or None if not found."""
    response = client.get(
        "/athletes", params={"id": f"eq.{athlete_id}", "select": "*"}
    )
    response.raise_for_status()
    rows = response.json()
    return rows[0] if rows else None


def delete_athlete(client: httpx.Client, athlete_id: int) -> None:
    """Delete the athlete row and all cascade-deleted related data."""
    response = client.request("DELETE", "/athletes", params={"id": f"eq.{athlete_id}"})
    response.raise_for_status()
