-- Cached raw Strava streams for one activity, stored as a flat object-of-arrays
-- JSONB: {"time":[…],"distance":[…],"altitude":[…],"heartrate":[…],"watts":[…],
--         "velocity_smooth":[…]}. One row per activity; computed-on-read panels
-- (zones, charts) derive from this. A sentinel row with data='{}' / point_count=0
-- marks activities Strava has no streams for, so we never refetch.
create table if not exists activity_streams (
  activity_id bigint primary key references activities(id) on delete cascade,
  athlete_id  bigint not null references athletes(id) on delete cascade,
  data        jsonb  not null,
  resolution  text   not null,
  point_count integer not null,
  fetched_at  timestamptz not null default now()
);

alter table activity_streams enable row level security;

create policy activity_streams_self_read on activity_streams
  for select using (athlete_id = (auth.jwt() ->> 'athlete_id')::bigint);
