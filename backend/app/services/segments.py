from datetime import UTC, datetime
from math import ceil

from supabase import Client

from app.db import segments as segments_db
from app.db.segments import SegmentEffortRow, SegmentRow
from app.models.segments import (
    SegmentDetailResponse,
    SegmentEffortItem,
    SegmentListItem,
    SegmentListResponse,
    SegmentSortDir,
    SegmentSortField,
)


def extract_efforts(
    athlete_id: int, detail: dict
) -> tuple[list[SegmentRow], list[SegmentEffortRow]]:
    """Pull segment + effort rows out of one detailed activity payload."""
    seg_by_id: dict[int, SegmentRow] = {}
    efforts: list[SegmentEffortRow] = []
    for e in detail.get("segment_efforts") or []:
        seg = e["segment"]
        seg_id = seg["id"]
        distance = seg.get("distance", 0.0)
        elapsed = e["elapsed_time"]
        hr = e.get("average_heartrate")
        high = seg.get("elevation_high")
        low = seg.get("elevation_low")
        gain = (
            (high - low)
            if (high is not None and low is not None)
            else seg.get("total_elevation_gain", 0.0)
        )
        seg_by_id[seg_id] = {
            "id": seg_id,
            "name": seg.get("name") or "Segment",
            "distance_m": distance,
            "avg_grade": seg.get("average_grade", 0.0),
            "climb_category": seg.get("climb_category", 0) or 0,
            "elev_gain_m": float(gain or 0.0),
        }
        efforts.append(
            {
                "id": e["id"],
                "segment_id": seg_id,
                "athlete_id": athlete_id,
                "activity_id": detail["id"],
                "elapsed_time_s": elapsed,
                "avg_watts": e.get("average_watts"),
                "avg_hr": round(hr) if hr is not None else None,
                "avg_speed_ms": (distance / elapsed) if elapsed else None,
                "start_date": e["start_date"],
                "is_best": False,
            }
        )
    return list(seg_by_id.values()), efforts


def best_effort_id(keys: list[dict]) -> int:
    """Id of the fastest effort; ties broken by the earliest start_date."""
    best = min(keys, key=lambda k: (k["elapsed_time_s"], k["start_date"]))
    return best["id"]


def recompute_is_best(supabase: Client, athlete_id: int, segment_id: int) -> None:
    keys = segments_db.get_effort_keys(supabase, athlete_id, segment_id)
    if not keys:
        return
    segments_db.set_is_best(supabase, athlete_id, segment_id, best_effort_id(keys))


def store_activity_efforts(supabase: Client, athlete_id: int, detail: dict) -> None:
    """Extract efforts from a detailed payload, upsert, and refresh is_best."""
    segs, efforts = extract_efforts(athlete_id, detail)
    if not efforts:
        return
    segments_db.upsert_segments(supabase, segs)
    segments_db.upsert_segment_efforts(supabase, efforts)
    for segment_id in {e["segment_id"] for e in efforts}:
        recompute_is_best(supabase, athlete_id, segment_id)


SEGMENT_PAGE_SIZE = 10


class SegmentNotFoundError(Exception):
    """Raised when a segment has no efforts for the requesting athlete."""


def get_segment(
    supabase: Client, athlete_id: int, segment_id: int
) -> SegmentDetailResponse:
    seg = segments_db.get_segment(supabase, segment_id)
    efforts = segments_db.list_segment_efforts(supabase, athlete_id, segment_id)
    if seg is None or not efforts:
        raise SegmentNotFoundError(f"segment {segment_id} has no efforts for athlete")
    items = [
        SegmentEffortItem(
            id=e["id"], activity_id=e["activity_id"],
            activity_name=(e.get("activities") or {}).get("name") or "Activity",
            start_date=e["start_date"], elapsed_time_s=e["elapsed_time_s"],
            avg_watts=e.get("avg_watts"), avg_hr=e.get("avg_hr"),
            avg_speed_ms=e.get("avg_speed_ms") or 0.0, is_best=e["is_best"],
        )
        for e in efforts
    ]
    pr_time = min(i.elapsed_time_s for i in items)
    return SegmentDetailResponse(
        id=seg["id"], name=seg["name"], distance_m=seg["distance_m"],
        avg_grade=seg["avg_grade"], pr_time_s=pr_time, attempts=len(items), efforts=items,
    )


def list_segments(
    supabase: Client, athlete_id: int, *,
    q: str | None, sort: SegmentSortField, direction: SegmentSortDir,
    page: int, as_of: datetime | None = None,
) -> SegmentListResponse:
    snapshot = as_of or datetime.now(UTC)
    offset = (page - 1) * SEGMENT_PAGE_SIZE
    rows = segments_db.list_segment_summaries(
        supabase, athlete_id,
        as_of=snapshot.isoformat(), q=q, direction=direction,
        limit=SEGMENT_PAGE_SIZE, offset=offset,
    )
    total = rows[0]["total_count"] if rows else 0
    items = [
        SegmentListItem(
            id=r["id"], name=r["name"], distance_m=r["distance_m"],
            avg_grade=r["avg_grade"], best_time_s=r["best_time_s"], attempts=r["attempts"],
            pr=r["pr"], latest_rank=r["latest_rank"], improvement_s=r["improvement_s"],
            recent_times_s=r["recent_times_s"],
        )
        for r in rows
    ]
    return SegmentListResponse(
        segments=items,
        page=page,
        page_size=SEGMENT_PAGE_SIZE,
        total=total,
        total_pages=max(1, ceil(total / SEGMENT_PAGE_SIZE)),
        as_of=snapshot,
    )
