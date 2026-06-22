-- Snapshot boundary for duplicate-free pagination of the segments list.
-- Records when each effort row was first ingested into our DB. Set once on
-- insert and preserved across PostgREST merge-duplicates upserts, because the
-- sync upsert payload omits this column. (start_date is the effort's ride time,
-- not its ingest time, so it can't serve as the snapshot boundary.)
alter table segment_efforts
  add column created_at timestamptz not null default now();
