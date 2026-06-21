from pydantic import BaseModel


class AthleteResponse(BaseModel):
    id: int
    name: str
    avatar_url: str | None = None
    settings: dict
