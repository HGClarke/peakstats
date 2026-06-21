-- Strava's per-ride local wall-clock start time. Stored as text so the value is
-- kept verbatim (Strava's string carries a trailing Z); it is a wall-clock label,
-- never an instant, so we deliberately avoid timestamptz to keep its correctness
-- independent of any Postgres session timezone. Never tz-convert it.
-- Nullable: rows synced before this column fall back to UTC start_date until a
-- re-backfill repopulates them.
alter table activities add column start_date_local text;
