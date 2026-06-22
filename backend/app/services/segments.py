from supabase import Client

from app.db import segments as segments_db
from app.db.segments import SegmentEffortRow, SegmentRow
from app.models.segments import (
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
        seg_by_id[seg_id] = {
            "id": seg_id,
            "name": seg.get("name") or "Segment",
            "distance_m": distance,
            "avg_grade": seg.get("average_grade", 0.0),
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


def summarize_segment(
    segment_id: int, name: str, distance_m: float, avg_grade: float, efforts: list[dict]
) -> SegmentListItem:
    times = sorted(e["elapsed_time_s"] for e in efforts)
    best_time = times[0]
    latest = max(efforts, key=lambda e: e["start_date"])
    ordered = sorted(efforts, key=lambda e: (e["elapsed_time_s"], e["start_date"]))
    latest_rank = next(i for i, e in enumerate(ordered, 1) if e is latest)
    pr = latest_rank == 1
    improvement = times[1] - times[0] if pr and len(times) >= 2 else None
    return SegmentListItem(
        id=segment_id, name=name, distance_m=distance_m, avg_grade=avg_grade,
        best_time_s=best_time, attempts=len(efforts), pr=pr,
        latest_rank=latest_rank, improvement_s=improvement,
    )


def list_segments(
    supabase: Client, athlete_id: int, *,
    q: str | None, sort: SegmentSortField, direction: SegmentSortDir,
) -> SegmentListResponse:
    rows = segments_db.list_athlete_efforts(supabase, athlete_id)
    grouped: dict[int, list[dict]] = {}
    meta: dict[int, dict] = {}
    for r in rows:
        seg = r.get("segments") or {}
        grouped.setdefault(r["segment_id"], []).append(r)
        meta[r["segment_id"]] = seg
    items = [
        summarize_segment(
            sid, meta[sid].get("name") or "Segment",
            meta[sid].get("distance_m", 0.0), meta[sid].get("avg_grade", 0.0), efforts,
        )
        for sid, efforts in grouped.items()
    ]
    if q:
        needle = q.lower()
        items = [s for s in items if needle in s.name.lower()]
    items.sort(key=lambda s: s.name)                       # stable secondary order
    items.sort(key=lambda s: s.attempts, reverse=direction == "desc")
    return SegmentListResponse(segments=items)
