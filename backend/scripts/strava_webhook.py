"""One-time CLI to manage the single Strava webhook push subscription.

Run from backend/ with the app environment, e.g.:
    ./.venv/bin/python scripts/strava_webhook.py create \
        --callback-url https://peakstats-api.onrender.com/webhooks/strava
    ./.venv/bin/python scripts/strava_webhook.py view
    ./.venv/bin/python scripts/strava_webhook.py delete --id 42
"""

import argparse

from app.clients import build_strava
from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the Strava webhook subscription")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="Create the push subscription")
    create.add_argument("--callback-url", required=True)
    sub.add_parser("view", help="List current push subscriptions")
    delete = sub.add_parser("delete", help="Delete a push subscription by id")
    delete.add_argument("--id", type=int, required=True)
    args = parser.parse_args()

    settings = get_settings()
    strava = build_strava(settings)
    try:
        if args.command == "create":
            sub_id = strava.create_push_subscription(
                args.callback_url, settings.strava_webhook_verify_token
            )
            print(f"Created subscription {sub_id}")
        elif args.command == "view":
            print(strava.list_push_subscriptions())
        elif args.command == "delete":
            strava.delete_push_subscription(args.id)
            print(f"Deleted subscription {args.id}")
    finally:
        strava.close()


if __name__ == "__main__":
    main()
