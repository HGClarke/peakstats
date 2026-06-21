from pydantic import BaseModel, Field


class StravaWebhookEvent(BaseModel):
    """A Strava push-subscription event payload."""

    aspect_type: str
    object_type: str
    object_id: int
    owner_id: int
    subscription_id: int
    event_time: int
    updates: dict = Field(default_factory=dict)
