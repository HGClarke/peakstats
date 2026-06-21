from pydantic import BaseModel


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
    distance_m: float
    moving_time_s: int


class OverviewResponse(BaseModel):
    this_week: WeekTotals
    last_week: WeekTotals
    week: list[WeekDay]
    recent_rides: list[RecentRideItem]
