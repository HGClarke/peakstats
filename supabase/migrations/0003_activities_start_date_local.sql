-- Strava's per-ride local wall-clock start time. Stored verbatim (carries a
-- trailing Z from Strava); treat as a wall-clock label, never tz-convert it.
-- Nullable: rows synced before this column fall back to UTC start_date until a
-- re-backfill repopulates them.
alter table activities add column start_date_local timestamptz;
