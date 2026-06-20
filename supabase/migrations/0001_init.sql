-- Athletes (PK = Strava athlete id)
create table athletes (
  id bigint primary key,
  name text not null,
  avatar_url text,
  settings jsonb not null default '{"units":"metric","theme":"dark","default_period":"week"}',
  created_at timestamptz not null default now()
);

-- Strava OAuth tokens (server-only; no client policies => RLS denies all client access)
create table strava_tokens (
  athlete_id bigint primary key references athletes(id) on delete cascade,
  access_token text not null,
  refresh_token text not null,
  expires_at timestamptz not null
);

-- Activities (PK = Strava activity id). Stored metric.
create table activities (
  id bigint primary key,
  athlete_id bigint not null references athletes(id) on delete cascade,
  name text not null,
  type text not null,
  start_date timestamptz not null,
  distance_m double precision not null,
  moving_time_s integer not null,
  elapsed_time_s integer not null,
  elev_gain_m double precision not null default 0,
  avg_speed_ms double precision,
  avg_hr integer,
  calories integer,
  summary_polyline text,
  splits_metric jsonb,
  detail_fetched_at timestamptz,
  is_pr boolean not null default false
);
create index activities_athlete_date_idx on activities (athlete_id, start_date desc);

create table segments (
  id bigint primary key,
  name text not null,
  distance_m double precision not null,
  avg_grade double precision not null default 0
);

create table segment_efforts (
  id bigint primary key,
  segment_id bigint not null references segments(id) on delete cascade,
  athlete_id bigint not null references athletes(id) on delete cascade,
  activity_id bigint not null references activities(id) on delete cascade,
  elapsed_time_s integer not null,
  avg_watts double precision,
  avg_hr integer,
  avg_speed_ms double precision,
  start_date timestamptz not null,
  is_best boolean not null default false
);
create index segment_efforts_athlete_segment_idx on segment_efforts (athlete_id, segment_id);
create index segment_efforts_activity_idx on segment_efforts (activity_id);

create table sync_state (
  athlete_id bigint primary key references athletes(id) on delete cascade,
  status text not null default 'idle',
  progress integer not null default 0,
  last_backfill_at timestamptz,
  last_sync_at timestamptz,
  last_webhook_event_id bigint
);

-- Enable RLS on every table
alter table athletes enable row level security;
alter table strava_tokens enable row level security;
alter table activities enable row level security;
alter table segments enable row level security;
alter table segment_efforts enable row level security;
alter table sync_state enable row level security;

-- Athlete-scoped read policies. auth.jwt() carries the Strava athlete id under
-- the custom claim "athlete_id" (set when the backend mints the session in Phase 2).
create policy athlete_self_read on athletes
  for select using (id = (auth.jwt() ->> 'athlete_id')::bigint);

create policy activities_self_read on activities
  for select using (athlete_id = (auth.jwt() ->> 'athlete_id')::bigint);

create policy segment_efforts_self_read on segment_efforts
  for select using (athlete_id = (auth.jwt() ->> 'athlete_id')::bigint);

create policy sync_state_self_read on sync_state
  for select using (athlete_id = (auth.jwt() ->> 'athlete_id')::bigint);

-- segments is shared reference data: readable by any authenticated athlete.
create policy segments_authenticated_read on segments
  for select using ((auth.jwt() ->> 'athlete_id') is not null);

-- No policies on strava_tokens => all client access denied. The backend uses the
-- service-role key (bypasses RLS) for all writes and token reads.
