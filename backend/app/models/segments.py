from typing import Literal

from pydantic import BaseModel

SegmentSortField = Literal["attempts"]
SegmentSortDir = Literal["asc", "desc"]


class SegmentListItem(BaseModel):
    id: int
    name: str
    distance_m: float
    avg_grade: float
    best_time_s: int
    attempts: int
    pr: bool
    latest_rank: int
    improvement_s: int | None
    recent_times_s: list[int]  # recent effort times, oldest -> newest, for the trend


class SegmentListResponse(BaseModel):
    segments: list[SegmentListItem]


class SegmentEffortItem(BaseModel):
    id: int
    activity_id: int
    activity_name: str
    start_date: str
    elapsed_time_s: int
    avg_watts: float | None
    avg_hr: int | None
    avg_speed_ms: float
    is_best: bool


class SegmentDetailResponse(BaseModel):
    id: int
    name: str
    distance_m: float
    avg_grade: float
    pr_time_s: int
    attempts: int
    efforts: list[SegmentEffortItem]
