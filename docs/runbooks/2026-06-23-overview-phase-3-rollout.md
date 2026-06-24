# Overview Phase 3 — Rollout Runbook

**What's shipping:** Top-avg-power stat + selector-scoped power/HR zone panels, backed
by the new `activity_metrics` table (migration `0008`) and `activities.avg_watts`.

**Merge state:** Phase 3 is merged to `main` **locally** (merge commit `c8ea1ae`), **not
pushed**. `main` is `ahead 19 / behind 2` of `origin/main` (`03010fb` = parallel work).

**Golden rule on ordering:** apply migration `0008` to Supabase **before** the new
backend deploys. The new `GET /activities/overview` queries `activity_metrics`/`avg_watts`;
if those don't exist yet, the endpoint 500s for everyone.

Project coordinates (from memory): Supabase ref `qjyxkggxqvhlnjelcsgn`; Render service
`peakstats-api` (`srv-d8rf7tgjs32c73c04t40`); Vercel `hgclarke98/peakstats`. Push to `main`
auto-deploys both Render + Vercel.

---

## Step 0 — Reconcile the diverged origin (before anything pushes)

`main` is behind `origin/main` by 2 commits (your parallel work already pushed). Rebase
local `main` on top of them so the eventual push is clean:

```bash
cd /Users/hollandclarke/Desktop/peakstats
git fetch origin
git log --oneline origin/main -3        # see the 2 commits you're behind
git rebase origin/main                   # replays the Phase 3 merge on top; resolve any conflicts
```

Phase 3 touches `backend/app/**`, `frontend/src/**` (overview/zones), `supabase/migrations/0008`,
and docs — low overlap with a settings/parallel change, but resolve conflicts if any. Do
**not** push yet (Step 1 must land in Supabase first).

---

## Step 1 — Apply migration `0008` to Supabase (BEFORE deploy)

The file is `supabase/migrations/0008_activity_metrics.sql` (table + `avg_watts` column +
RLS). Pick one path:

- **Supabase SQL editor (simplest):** open the project (`qjyxkggxqvhlnjelcsgn`) → SQL editor
  → paste the full contents of `0008_activity_metrics.sql` → Run.
- **Supabase MCP (have Claude do it):** ask me to run `apply_migration` with name
  `0008_activity_metrics` and that file's body — same way `0004`/`0005` were applied.

**Verify it landed** (SQL editor or MCP `list_tables`):

```sql
select column_name from information_schema.columns
where table_name = 'activity_metrics' order by ordinal_position;     -- 10 columns
select 1 from information_schema.columns
where table_name = 'activities' and column_name = 'avg_watts';        -- 1 row
```

---

## Step 2 — Push → deploy backend + frontend

```bash
git push origin main      # triggers Render (peakstats-api) + Vercel (peakstats)
```

Wait for both to go green, then sanity-check the API is up and the new fields flow:

```bash
curl -s https://peakstats-api.onrender.com/health           # {"status":"ok"}
# Authenticated check (browser is easier): GET /activities/overview?period=week should
# now return power_zones / hr_zones / summary.top_avg_power_w without 500s.
```

If `/activities/overview` 500s here, Step 1 didn't land — fix the migration before continuing.

---

## Step 3 — Run the one-off backfills (after deploy is green)

These run **locally** against prod (your `backend/.env` already points at prod Supabase +
Strava — same setup the webhook script uses). The runner is `backend/scripts/phase3_backfill.py`.

```bash
cd /Users/hollandclarke/Desktop/peakstats/backend

# 3a. avg_watts — fast (~5 Strava calls for ~877 rides). "Top avg power" lights up immediately.
PYTHONPATH=. ./.venv/bin/python scripts/phase3_backfill.py avg-watts

# 3b. activity_metrics — paced (~12/min, ~1h+ over the full history). Zone panels fill in
#     progressively (partial data renders correctly — it just undercounts until complete).
#     Resumable: only un-metriced rides are processed, so Ctrl-C and re-run picks up where
#     it left off. Safe to run in a screen/tmux session or background.
PYTHONPATH=. ./.venv/bin/python scripts/phase3_backfill.py streams
```

`avg-watts` and `streams` are idempotent. The athlete id is auto-detected when there's a
single athlete; otherwise pass `--athlete-id <id>`.

> Note: `run_streams_backfill` is **also auto-chained** on `POST /sync/start`, so brand-new
> athletes get metrics during their initial sync. Step 3b is the **one-time** pass for the
> existing ~877-ride history only.

**Progress check** (Supabase SQL editor) — watch the metrics table fill:

```sql
select count(*) as metriced from activity_metrics;
select count(*) as total_rides from activities;          -- target
select count(*) as with_avg_watts from activities where avg_watts is not null;
```

---

## Step 4 — Browser smoke test

On https://peakstats.vercel.app/home (logged in):

- **Top avg power** shows a value in the Weekly Highlights card (after Step 3a).
- **Power zones / Heart-rate zones** panels render; switching **Week / Month / Year**
  re-scopes them (and the bars fill in as Step 3b progresses).
- With **FTP / Max HR unset** in Settings → panels show the "Set your FTP / Max HR in
  Settings" prompts. Set them in `/settings` → panels **re-bucket instantly** with no
  re-backfill (boundaries are applied at query time).
- A period with no power/HR data → "No power/heart-rate data for this period" (not the
  unset prompt).

---

## Rollback

- **Frontend/backend code:** revert the merge commit and push —
  `git revert -m 1 c8ea1ae && git push origin main` (redeploys both). The new columns/table
  are additive and harmless if left in place.
- **Migration:** `0008` is additive (new table + nullable column); no need to roll it back.
  If you must: `drop table activity_metrics; alter table activities drop column avg_watts;`
  (only after the code that reads them is reverted).

## Known trade-off (accepted)

Overview period zones use the compact histogram store, so they can differ from the activity
detail page's exact per-sample zones by ≤½ bin (≤5 W / ≤2.5 bpm) at zone boundaries —
inherent to the FTP-independent design, fine for a dashboard.

## Deferred follow-up

Task 12 (`get_detail` serving zones/scalars from `activity_metrics` to skip recomputing from
full streams — a detail-page perf win) was deferred; it continues the existing
activity-detail-perf item. Not required for this rollout.
