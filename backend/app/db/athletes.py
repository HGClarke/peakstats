import httpx

_MERGE = {"Prefer": "resolution=merge-duplicates"}


def upsert_athlete(
    client: httpx.Client, athlete_id: int, name: str, avatar_url: str | None
) -> None:
    response = client.post(
        "/athletes",
        params={"on_conflict": "id"},
        headers=_MERGE,
        json=[{"id": athlete_id, "name": name, "avatar_url": avatar_url}],
    )
    response.raise_for_status()


def get_athlete(client: httpx.Client, athlete_id: int) -> dict | None:
    response = client.get(
        "/athletes", params={"id": f"eq.{athlete_id}", "select": "*"}
    )
    response.raise_for_status()
    rows = response.json()
    return rows[0] if rows else None


def delete_athlete(client: httpx.Client, athlete_id: int) -> None:
    response = client.request("DELETE", "/athletes", params={"id": f"eq.{athlete_id}"})
    response.raise_for_status()
