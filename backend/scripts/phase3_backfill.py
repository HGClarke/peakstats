"""One-off CLI for the Overview Phase 3 backfills (run once after deploying 0008).

Run from backend/ with the app environment (a .env pointing at prod Supabase +
Strava). `PYTHONPATH=.` makes the `app` package importable, e.g.:

    # Populate activities.avg_watts for historical rides (fast — ~5 Strava calls):
    PYTHONPATH=. ./.venv/bin/python scripts/phase3_backfill.py avg-watts

    # Compute compact activity_metrics for every un-metriced ride (paced ~12/min,
    # ~1h+ over a full history; resumable — safe to re-run / Ctrl-C and resume):
    PYTHONPATH=. ./.venv/bin/python scripts/phase3_backfill.py streams

    # Both, in order:
    PYTHONPATH=. ./.venv/bin/python scripts/phase3_backfill.py all

The athlete id is auto-detected when the athletes table holds exactly one row;
pass --athlete-id to target a specific athlete.
"""

import argparse
import logging

from app.clients import build_supabase
from app.config import get_settings
from app.services import sync as sync_service
from supabase import Client


def _resolve_athlete_id(supabase: Client, override: int | None) -> int:
    if override is not None:
        return override
    rows = supabase.table("athletes").select("id").execute().data
    if len(rows) != 1:
        raise SystemExit(
            f"Found {len(rows)} athletes; pass --athlete-id to choose one."
        )
    return int(rows[0]["id"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Overview Phase 3 one-off backfills")
    parser.add_argument(
        "command", choices=["avg-watts", "streams", "all"],
        help="avg-watts: re-list summaries for avg_watts; "
             "streams: compute activity_metrics; all: both, in order",
    )
    parser.add_argument("--athlete-id", type=int, default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    supabase = build_supabase(settings)
    athlete_id = _resolve_athlete_id(supabase, args.athlete_id)

    if args.command in ("avg-watts", "all"):
        print(f"avg_watts backfill: athlete {athlete_id} …")
        sync_service.run_avg_watts_backfill(supabase, settings, athlete_id)
        print("avg_watts backfill done.")
    if args.command in ("streams", "all"):
        print(f"streams/metrics backfill: athlete {athlete_id} (paced — this takes a while) …")
        sync_service.run_streams_backfill(supabase, settings, athlete_id)
        print("streams/metrics backfill done.")


if __name__ == "__main__":
    main()
