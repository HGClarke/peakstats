import httpx

from app.db import athletes as athletes_db
from app.models.athlete import AthleteResponse


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
