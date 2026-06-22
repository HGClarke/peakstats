from typing import TypedDict, cast

from supabase import Client


class AthleteRow(TypedDict):
    """Shape of a row in the `athletes` table as returned by PostgREST."""

    id: int
    name: str
    avatar_url: str | None
    settings: dict


def upsert_athlete(
    client: Client, athlete_id: int, name: str, avatar_url: str | None
) -> None:
    """Insert or update an athlete row, merging on the primary key."""
    client.table("athletes").upsert(
        {"id": athlete_id, "name": name, "avatar_url": avatar_url},
        on_conflict="id",
    ).execute()


def get_athlete(client: Client, athlete_id: int) -> AthleteRow | None:
    """Return the athlete row for the given ID, or None if not found."""
    resp = client.table("athletes").select("*").eq("id", athlete_id).execute()
    return cast(AthleteRow, resp.data[0]) if resp.data else None


def delete_athlete(client: Client, athlete_id: int) -> None:
    """Delete the athlete row and all cascade-deleted related data."""
    client.table("athletes").delete().eq("id", athlete_id).execute()


def update_settings(client: Client, athlete_id: int, settings: dict) -> AthleteRow:
    """Overwrite the athlete's settings JSONB and return the updated row."""
    resp = (
        client.table("athletes")
        .update({"settings": settings})
        .eq("id", athlete_id)
        .execute()
    )
    return cast(AthleteRow, resp.data[0])
