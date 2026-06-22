# Segments — backfill infra & deferred follow-ups

**Date:** 2026-06-22
**Status:** Notes for later. Nothing actioned here yet — the segments feature is live and the
one-time historical backfill is complete (877/877 activities, ~43.8k efforts, ~5.6k segments).
Related: [`specs/2026-06-21-segments-design.md`](superpowers/specs/2026-06-21-segments-design.md),
[`specs/2026-06-22-segments-list-pagination-design.md`](superpowers/specs/2026-06-22-segments-list-pagination-design.md).

## Context — what happened during the first backfill

Segment efforts are populated from Strava *detailed* activity payloads. New rides come through the
webhook (one call each, already carries efforts — a non-issue). The **initial historical fill** for
an athlete is the expensive part: one `GET /activities/{id}` per ride, bounded by Strava's
**200 requests / 15 min** (and 2000/day) **per application**.

The detail-backfill (`services/sync.run_detail_backfill`) is chained off `POST /sync/start` and runs
as a **FastAPI background task on the Render web service**. For this athlete (~877 rides, ~1hr+ of
work) that approach failed:

1. First run died after **1 activity** — a transient error aborted the whole worker (no per-activity
   isolation).
2. Hardened the worker (`ba979d5`): per-activity try/except (skip + leave `detail_fetched_at NULL`
   for retry), per-iteration token refresh (tokens expire hourly), and a `failed` set to avoid
   re-query loops. It then ran ~80 activities and **died again ~18 min in**.
3. Root cause (inferred, not log-confirmed): **Render free-tier idle spin-down** — a free web service
   sleeps after ~15 min with no inbound HTTP requests, killing the in-flight background task.
4. Workaround used: **ran the backfill locally against prod** (`run_detail_backfill` driven from a
   laptop). Completed reliably (resumable across machine-sleep pauses). 15 scattered transient skips
   (~2%) were recovered by a mop-up pass.

**Decision (2026-06-22):** keep the current setup as-is. Web-service background task + manual local
run for any large one-time fill. The notes below are for when this needs to be productionized
(e.g. real multi-user onboarding).

## Follow-up 1 — move the backfill off web-service background tasks

The web-service background task is the wrong primitive for an hour-plus job. Options:

| Option | Fixes spin-down? | Survives deploys/restarts? | Cost | Notes |
|---|---|---|---|---|
| Keep as-is + run big fills locally | n/a | n/a | free | Current. Fine while single-user. |
| **Upgrade web service to paid (Starter ~$7/mo)** | yes (no spin-down) | **no** — a deploy still kills in-flight tasks | ~$7/mo | Band-aid. A one-time fill would *usually* finish, but it's still a web-process task with no durability/retry. |
| **Render Cron Job** (recommended) | yes (own container, runs to completion) | yes (re-fires on schedule) | usage-billed (cheap for short sweeps) | A periodic sweep over `detail_fetched_at IS NULL`. Clean fit; also covers new-user onboarding. Entry point e.g. `python -m app.jobs.backfill_details`. |
| Render Background Worker (always-on) | yes | better, but still needs resume logic | ~$7/mo+ (paid-only) | Good if you want continuous processing rather than scheduled. |
| Durable queue (Redis + worker) | yes | yes | infra + $ | Only worth it at real scale. |

**Key framing:** this is a *lifecycle* problem, not a *compute* one — the work is light
(~85 Strava calls/15 min, trivial CPU). So the cheapest paid instance or a cron job is plenty; you're
paying for "stays alive / runs to completion," not horsepower.

**Recommendation:** add a **Render Cron Job** that runs the NULL-sweep (reuse `run_detail_backfill`
behind a small `app/jobs/` entry point), and leave the web tier on free. That makes both the one-time
fill and per-user onboarding robust without paying for an always-on box.

## Follow-up 2 — per-activity `recompute_is_best` is slow

During backfill the throughput **decayed 5.7 → 2.6 rides/min** as efforts accumulated, because
`recompute_is_best` re-reads *all* efforts for a segment (and does 2 `UPDATE`s) on **every** activity
that touches it — and popular segments accumulate hundreds of efforts. New-user onboarding hits the
same decay.

**Fix (deliberate, tested — not a mid-run hack):** during backfill, **skip per-activity
`recompute_is_best`** and do a **single bulk `is_best` pass at the end** (one `UPDATE … FROM
(window-ranked) …` per athlete, like the targeted repair already used). The webhook path (one ride at
a time) can keep recomputing inline — it's cheap there.

## Rate-limit ceiling (informational, not a bug)

Even fully optimized, a first-time fill is bounded by Strava's **200 req / 15 min** → ~877 rides ≈
~66–75 min minimum, and the cap is **per-app** (shared across all athletes). For multi-user scale,
apply to Strava for **elevated rate limits** (e.g. 600/15min, 30k/day) — an application, not a code
change. After the initial fill, steady state is trivial (webhook = 1 call/ride).
