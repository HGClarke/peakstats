-- Snapshot boundary for duplicate-free pagination of the activities list.
-- Records when each activity row was first ingested into our DB. Set once on
-- insert and preserved across PostgREST merge-duplicates upserts, because the
-- sync upsert payload omits this column.
alter table activities
  add column created_at timestamptz not null default now();
