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


class ActivityStreamsResponse(BaseModel):
    point_count: int
    time: list[int] | None = None
    distance: list[float] | None = None
    altitude: list[float] | None = None
    watts: list[float | None] | None = None
    heartrate: list[int | None] | None = None
    velocity_smooth: list[float] | None = None


class ZoneBucket(BaseModel):
    z: str
    name: str
    range: str
    seconds: int
    pct: float


class ZonesBlock(BaseModel):
    unset: bool
    avg: float | None = None
    buckets: list[ZoneBucket] = []


class ClimbItem(BaseModel):
    name: str
    climb_category: int
    distance_m: float
    avg_grade: float
    elev_gain_m: float
    time_s: int
    vam: int


class ActivityDetailResponse(BaseModel):
    id: int
    name: str
    type: str
    start_date: str
    start_date_local: str | None = None
    location: str | None = None
    distance_m: float
    moving_time_s: int
    elev_gain_m: float
    avg_speed_ms: float | None = None
    avg_power_w: float | None = None
    normalized_power_w: float | None = None
    work_kj: float | None = None
    avg_hr: int | None = None
    summary_polyline: str | None = None
    power_zones: ZonesBlock = ZonesBlock(unset=True)
    hr_zones: ZonesBlock = ZonesBlock(unset=True)
    climbs: list[ClimbItem] = []
