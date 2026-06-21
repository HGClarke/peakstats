# Peakstats Phase 3b — Webhook Ingest (auto-sync after every ride) Design

**Date:** 2026-06-21
**Status:** Approved (design); pending implementation plan
**Parent spec:** `docs/superpowers/specs/2026-06-20-peakstats-design.md` (Phase 3 — real-time updates / webhooks)
**Predecessor:** `docs/superpowers/specs/2026-06-20-phase3-sync-pipeline-design.md` (Phase 3a — backfill + sync screen + manual refresh, merged to `main`)

## Overview

Phase 3a backfilled an athlete's history and added a manual "Refresh from Strava".
Phase 3b makes the app **auto-sync after every ride** by subscribing to Strava push
subscriptions: when an athlete creates, edits, or deletes an activity on Strava, Strava
calls our webhook, and the backend fetches that one activity and upserts it (or deletes
the row). An already-open dashboard picks up the change on its own via **cheap polling**
(TanStack Query refetch-on-window-focus + a light interval) — no manual reload.

This is the deferred half of the parent spec's Phase 3. It is **backend-weighted**: the
frontend change is a tightly-scoped tweak to one query hook.

## Goals

- Subscribe to Strava push subscriptions (one subscription per application).
- Answer Strava's subscription-validation challenge (`GET /webhooks/strava`).
- Ingest activity create/update/delete events (`POST /webhooks/strava`) and keep our
  `activities` copy in sync with Strava.
- Respond to webhook POSTs in well under Strava's 2-second limit.
- Keep an open dashboard current without a manual refresh.

## Non-goals (Phase 3b)

- **Real-time server push to the browser** (`WS /ws/updates` / SSE). Deferred — the open
  tab stays fresh via cheap polling instead. (Rationale below.) A true push channel can be
  a later slice if desired.
- **Athlete deauthorization webhook events** (`object_type=athlete`,
  `updates.authorized=false`). Logged and ignored; the existing in-app disconnect flow
  already handles revocation + data wipe. Auto-wiping data from an unauthenticated webhook
  is intentionally avoided.
- **Detailed activity ingest** (splits, segment efforts, streams) and segment derivation —
  still Phase 6. Webhook ingest stores **summary columns only**, reusing 3a's
  `_to_activity_row` (`calories`, `splits_metric`, `detail_fetched_at` stay null).
- Multi-instance fan-out / pub-sub. Single Render web dyno; in-process background tasks.

## Key decisions

1. **Scope:** webhook subscription + ingest (create/update/delete) + cheap-polling browser
   freshness. Real-time browser push is explicitly deferred.

2. **Transport for browser freshness — cheap polling, not WebSocket/SSE.** The app proxies
   the API through a Vercel rewrite (`/api/:path*` → Render) specifically so the
   `ps_session` cookie is **first-party** (see `peakstats-auth-cookie-proxy`). A WebSocket
   cannot traverse that rewrite (no `Upgrade` proxying), so `WS /ws/updates` would have to
   connect cross-site to Render, reintroducing the third-party-cookie 401 the proxy was
   built to fix. SSE would fit the proxy but adds a long-lived stream against free-tier
   limits. For Phase 3b we instead keep the open dashboard fresh with TanStack Query
   `refetchOnWindowFocus` + a ~60s `refetchInterval` on the overview query. No streaming
   infra, no cookie/auth risk, robust on Render's free tier. Trade-off: not instant
   (≤ ~60s or next focus), which is acceptable for ride analytics.

3. **Webhook callback points directly at Render**, not through the Vercel proxy. The
   webhook is server-to-server (Strava → us) with **no cookie involved**, so the proxy buys
   nothing; pointing Strava at `https://peakstats-api.onrender.com/webhooks/strava` removes
   a hop and any proxy streaming/timeout concern. Strava's webhook callback URL is
   independent of the OAuth "Authorization Callback Domain", so this is unaffected by the
   OAuth setup.

4. **Fast ack + background work.** Strava disables endpoints that don't return `200` within
   ~2s (and after repeated failures). The `POST` handler parses the event, returns `200`
   immediately, and hands the Strava fetch/upsert to in-process `BackgroundTasks` — the same
   pattern 3a uses for backfill. The background task builds its **own** Supabase/Strava
   clients (request-scoped `deps` clients are already closed by the time it runs).

5. **Subscription managed by a committed one-time CLI script**, not an admin HTTP endpoint.
   Creating/deleting the (single, app-level) subscription is a one-time operational action;
   a script keeps it out of the request surface. Considered an endpoint and rejected (adds a
   public/admin surface for a one-shot action).

6. **`owner_id` maps directly to our athlete.** `athletes.id` already **is** the Strava
   athlete id (`upsert_athlete(supabase, athlete["id"], …)`), so a webhook's `owner_id` is
   the athlete id and the token row key with no extra lookup table. Events for an
   `owner_id` we don't know are ignored (logged) before any Strava call.

## Architecture & data flow

```
One-time setup (scripts/strava_webhook.py create, run once post-deploy):
  POST https://www.strava.com/api/v3/push_subscriptions
       {client_id, client_secret, callback_url, verify_token}
    └─ Strava ──GET callback?hub.mode=subscribe&hub.verify_token=…&hub.challenge=…──►
         GET /webhooks/strava
           verify_token matches → 200 {"hub.challenge": <value>}
    └─ Strava stores subscription, returns {"id": <subscription_id>}

Per ride (runtime):
  athlete creates / edits / deletes an activity on Strava
    └─ Strava ──POST /webhooks/strava
         {aspect_type, object_type, object_id, owner_id, subscription_id, event_time, updates}
         router: parse → return 200 IMMEDIATELY + BackgroundTasks(process_event)
         background task (builds its OWN clients, closes in finally):
           object_type != "activity"   → log + done
           owner_id not a known athlete → log + done
           create / update → get_valid_access_token
                           → strava.get_activity(object_id)
                           → _to_activity_row(owner_id, detail)
                           → db.activities.upsert_activities
           delete          → db.activities.delete_activity(owner_id, object_id)
           on success      → sync_state.last_webhook_event_id = event_time

Open dashboard (no reload):
  useOverview(): refetchOnWindowFocus + refetchInterval ~60s
    → reflects webhook-ingested changes within a tick
```

The background task **must build its own Supabase/Strava clients** via `app/clients.py`
factories — it cannot reuse the request-scoped `deps` clients, which close when the
`POST /webhooks/strava` response is sent.

## Backend design (layered: routers → services → db)

Follows `backend/CLAUDE.md`: thin routers, fastapi-free services, typed `db` wrappers
returning `TypedDict` rows, sync I/O in plain `def`, `ruff` + `mypy` clean.
`test_architecture.py` enforces layering (the new service imports no fastapi).

### Infrastructure (`app/strava.py`, modify)

- `get_activity(access_token, activity_id) -> dict` — authenticated
  `GET https://www.strava.com/api/v3/activities/{id}` with per-call `Authorization: Bearer`;
  raises for non-2xx. Returns Strava's DetailedActivity (a superset of the summary fields
  `_to_activity_row` reads).
- `create_push_subscription(callback_url, verify_token) -> int` — app-level
  `POST /push_subscriptions` with `client_id` + `client_secret` form params; returns the new
  subscription id.
- `list_push_subscriptions() -> list[dict]` — `GET /push_subscriptions` (app-level).
- `delete_push_subscription(subscription_id) -> None` — `DELETE /push_subscriptions/{id}`
  (app-level).

### Services (`app/services/webhooks.py`, new — fastapi-free)

- `process_event(settings, event) -> None` — background entry point. Builds its own clients;
  ignores non-`activity` `object_type` and unknown `owner_id`; dispatches create/update vs
  delete; records the event on `sync_state.last_webhook_event_id` (= the event's
  `event_time`) on success; catches + logs all errors without secrets; closes clients in
  `finally`.
- Helpers as needed (`_handle_upsert`, `_handle_delete`) kept small and pure-ish.

Reuses `services.tokens.get_valid_access_token`, `services.sync._to_activity_row`,
`db.activities.upsert_activities`, `db.sync_state.upsert_sync_state`, `db.athletes.get_athlete`.

### Data access (`app/db/activities.py`, modify)

- `delete_activity(client, athlete_id, activity_id) -> None` — PostgREST
  `DELETE /activities?id=eq.{activity_id}&athlete_id=eq.{athlete_id}` (scoped by athlete so
  one athlete's event can never delete another's row).

`sync_state` needs **no schema change**: the existing `last_webhook_event_id bigint` column
(provisioned in `0001_init.sql`) is reused to store the last processed event's `event_time`
(epoch seconds), written via 3a's `db.sync_state.upsert_sync_state`. Strava emits no stable
event id, so `event_time` is the honest "last webhook seen" marker; it is observability only
(dedup relies on idempotent upsert, not this field).

### Models (`app/models/webhooks.py`, new)

- `StravaWebhookEvent` — `aspect_type` (`"create" | "update" | "delete"`), `object_type`
  (`"activity" | "athlete"`), `object_id: int`, `owner_id: int`, `subscription_id: int`,
  `event_time: int`, `updates: dict` (default `{}`).
- `WebhookValidationResponse` — `{"hub.challenge": str}` (aliased field name).

### Router (`app/routers/webhooks.py`, new; register in `main.py`)

- `GET /webhooks/strava` — Strava validation. Reads `hub.mode` / `hub.verify_token` /
  `hub.challenge`; constant-time compare of the verify token against
  `settings.strava_webhook_verify_token`; `403` on mismatch; `200 {"hub.challenge": …}` on
  match. **Not** behind `get_current_athlete_id` (Strava has no session).
- `POST /webhooks/strava` — parse the event body; return `200` immediately; schedule
  `webhooks_service.process_event(settings, event)` via `BackgroundTasks` for activity
  events (non-activity events: log + `200`). Malformed body → log + `200` (never make Strava
  retry garbage). **Not** behind session auth.

### Config (`app/config.py`, modify)

- `strava_webhook_verify_token` — already present (placeholder on Render today); set a real
  value at rollout.
- `strava_webhook_subscription_id: int = 0` (new, optional) — when non-zero, `process_event`
  may verify the event's `subscription_id` matches; the CLI also reads/writes it.

### Subscription CLI (`backend/scripts/strava_webhook.py`, new — outside `app/`)

One-time operational tool, exempt from the `app/` layering tests. Subcommands:
- `create --callback-url <url>` → `StravaClient.create_push_subscription`, prints the id.
- `view` → `list_push_subscriptions`.
- `delete --id <n>` → `delete_push_subscription`.

Builds settings + a Strava client via `app.config` / `app.clients`.

## Frontend design (cheap polling)

React 19 + Vite + TS + TanStack Query (per `frontend/CLAUDE.md`). The global `QueryClient`
keeps `refetchOnWindowFocus: false`; the change is scoped to the one live data-display query.

- **`src/api/overview.ts`** (modify) — the overview `useQuery` (key `["activities",
  "overview"]`) gains `refetchOnWindowFocus: true` and `refetchInterval: 60_000`.
- `["athlete"]` and `["sync","status"]` are untouched (sync status already self-limits its
  polling to `backfilling`).
- No new UI: the dashboard quietly reflects new rides. Future Activities/Trends queries
  adopt the same two options when those phases land.

## Error handling

- **Fast ack always.** `POST` returns `200` before/independently of the background work, so a
  slow or failing fetch never triggers Strava retries or endpoint disabling.
- **Background fetch failures** (token refresh fail, Strava 401/429/5xx, network) → caught,
  logged without secrets, no retry in v1; the next manual refresh / re-backfill reconciles.
  `sync_state.last_webhook_event_id` is updated only after a successfully processed event.
- **Unknown `owner_id` / non-activity events** → ignored before any Strava call (logged).
- **Malformed payload** → logged + `200`.
- **GET challenge token mismatch** → `403`.

## Security

- `GET` challenge verified by constant-time compare against `strava_webhook_verify_token`.
- `POST` is necessarily public (no session). Strava does not HMAC-sign payloads, so defense
  is: act only on **known `owner_id`** (so the endpoint can't be coerced into hammering
  Strava for arbitrary athletes); optional `subscription_id` match when configured;
  **idempotent upsert** so replays are harmless; `delete_activity` scoped by `athlete_id`.
- Never log tokens or full event payloads. No new secrets leave the server;
  client_id/secret are used only by the one-time CLI.

## Testing

- **Backend (pytest; Strava + Supabase stubbed via `httpx.MockTransport`; ruff + mypy;
  `test_architecture.py` green):**
  - `strava.get_activity` (Bearer + path); `create/list/delete_push_subscription` (form
    params, id parse).
  - `db.activities.delete_activity` (eq filters + DELETE method).
  - `services.webhooks.process_event`: create→upsert, update→upsert, delete→delete,
    unknown owner ignored, non-activity ignored, fetch-error swallowed + logged,
    `last_webhook_event_id` set on success.
  - `routers.webhooks`: GET challenge (valid token echoes challenge; invalid → 403);
    POST returns 200 + schedules background task for activity events; malformed → 200.
- **Frontend (Vitest + RTL):** overview hook exposes `refetchInterval` /
  `refetchOnWindowFocus`; existing tests stay green. `npm test && npm run lint && npm run
  build` pass.

## Increments (vertical slices — each implemented, verified, committed)

1. **Strava client + db primitives** — `strava.get_activity` +
   `create/list/delete_push_subscription`; `db.activities.delete_activity`. Verify: pytest +
   ruff + mypy green.
2. **Webhook ingest** — `models/webhooks`, `services/webhooks.process_event`,
   `routers/webhooks` (GET challenge + POST enqueue), register in `main.py`, record
   `sync_state.last_webhook_event_id`. Tests.
3. **Subscription CLI** — `scripts/strava_webhook.py` (create / view / delete).
4. **Frontend cheap polling** — overview hook `refetchOnWindowFocus` + `refetchInterval`;
   tests/lint/build green.
5. **Live setup + end-to-end** — set real `STRAVA_WEBHOOK_VERIFY_TOKEN` on Render, deploy,
   run the CLI to create the subscription, record the id (optionally set
   `STRAVA_WEBHOOK_SUBSCRIPTION_ID`), and verify a real create/edit/delete on Strava flows
   into the overview within a tick.

## One-time rollout (manual, after merge + deploy)

1. Set a real `STRAVA_WEBHOOK_VERIFY_TOKEN` on the Render `peakstats-api` service.
2. Deploy the backend so `/webhooks/strava` is live (the GET challenge must answer before
   Strava will accept the subscription).
3. `python scripts/strava_webhook.py create --callback-url
   https://peakstats-api.onrender.com/webhooks/strava` (with prod client id/secret).
4. Record the returned subscription id (optionally set `STRAVA_WEBHOOK_SUBSCRIPTION_ID`).
5. Create/edit/delete a ride on Strava → confirm the overview reflects it.

## Cross-cutting

- **Secrets:** reuse `STRAVA_WEBHOOK_VERIFY_TOKEN` (set real value); Strava/Supabase
  credentials remain server-only; the CLI uses client id/secret locally only.
- **Rate limits:** one `GET /activities/{id}` per create/update event; deletes need no Strava
  call; unknown owners short-circuit before any call.
- **Deployment:** existing single Render web service + Vercel SPA; no `render.yaml` change.
  The subscription is created once via the CLI post-deploy.

## Open questions / risks

- **Free-dyno spin-down:** an event arriving while the dyno is asleep — Strava retries
  failed deliveries for a window, and the next manual refresh / re-backfill reconciles
  regardless; acceptable for v1.
- **No payload signature:** mitigated by known-owner gating + idempotent upsert + optional
  subscription-id check.
- **Polling latency:** browser freshness is ≤ ~60s / next focus, not instant; revisit with
  SSE only if users notice.
