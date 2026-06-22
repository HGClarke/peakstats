from supabase import Client

from app.db import segments as segments_db
from app.db.segments import SegmentEffortRow, SegmentRow


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
