-- Compact, FTP/HR-max-independent per-activity metrics: precomputed power
-- scalars plus absolute-bin histograms (seconds per wattage / bpm bin). Zone
-- boundaries are applied at QUERY time from the athlete's current ftp_w / hr_max,
-- so changing them re-buckets instantly with no re-backfill. One row per activity.
-- Histogram bin geometry is documented in app/services/analysis.py
-- (POWER_BIN_W=10/POWER_BINS=150 → [0,1500)W; HR_BIN_BPM=5/HR_BINS=44 → [0,220)bpm;
-- overflow folds into the last bin). hist columns are NULL when the ride has no
-- power / no HR.
create table if not exists activity_metrics (
  activity_id  bigint primary key references activities(id) on delete cascade,
  athlete_id   bigint not null references athletes(id) on delete cascade,
  avg_power_w  double precision,
  np_w         double precision,
  work_kj      double precision,
  power_hist   jsonb,
  hr_hist      jsonb,
  has_power    boolean not null default false,
  has_hr       boolean not null default false,
  computed_at  timestamptz not null default now()
);

create index if not exists activity_metrics_athlete_idx on activity_metrics(athlete_id);

alter table activity_metrics enable row level security;

create policy activity_metrics_self_read on activity_metrics
  for select using (athlete_id = (auth.jwt() ->> 'athlete_id')::bigint);

-- Highest single-ride average power for the period's "Top avg power" stat.
-- Sourced from Strava summary average_watts (nullable; no power meter → null).
alter table activities add column if not exists avg_watts double precision;
