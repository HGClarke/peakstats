-- Categorized-climb fields off each segment, for the activity climbs table.
-- Backfilled for history by re-running the detail backfill (store_activity_efforts).
alter table segments add column if not exists climb_category smallint        not null default 0;
alter table segments add column if not exists elev_gain_m    double precision not null default 0;
