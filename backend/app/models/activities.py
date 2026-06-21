from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SortField = Literal["date", "distance", "time", "elevation", "speed"]
SortDir = Literal["asc", "desc"]


class WeekTotals(BaseModel):
    distance_m: float
    elev_gain_m: float
    moving_time_s: int
    avg_speed_ms: float | None


class WeekDay(BaseModel):
    day: str
    km: float


class RecentRideItem(BaseModel):
    id: int
    name: str
    type: str
    start_date: str
    start_date_local: str | None = None
    distance_m: float
    moving_time_s: int


class OverviewResponse(BaseModel):
    this_week: WeekTotals
    last_week: WeekTotals
    week: list[WeekDay]
    recent_rides: list[RecentRideItem]


class ActivityListItem(BaseModel):
    id: int
    name: str
    type: str
    start_date: str
    distance_m: float
    moving_time_s: int
    elev_gain_m: float
    avg_speed_ms: float | None


class ActivityListResponse(BaseModel):
    activities: list[ActivityListItem]
    page: int
    page_size: int
    total: int
    total_pages: int
    as_of: datetime
