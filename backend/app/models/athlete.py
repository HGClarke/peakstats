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
    ftp_w: int | None = None
    hr_max: int | None = None

    @model_validator(mode="after")
    def require_at_least_one(self) -> "SettingsUpdate":
        if all(v is None for v in (self.units, self.theme, self.ftp_w, self.hr_max)):
            raise ValueError("at least one of units, theme, ftp_w, hr_max is required")
        return self
