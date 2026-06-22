from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class AthleteResponse(BaseModel):
    id: int
    name: str
    avatar_url: str | None = None
    settings: dict


class SettingsUpdate(BaseModel):
    """Partial update of athlete settings; at least one field required."""

    model_config = ConfigDict(extra="forbid")

    units: Literal["metric", "imperial"] | None = None
    theme: Literal["dark", "light"] | None = None

    @model_validator(mode="after")
    def require_at_least_one(self) -> "SettingsUpdate":
        if self.units is None and self.theme is None:
            raise ValueError("at least one of units, theme is required")
        return self
