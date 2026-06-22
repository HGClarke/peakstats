-- Server-side aggregation for the segments list.
--
-- Previously the API pulled every one of an athlete's segment_efforts (34k+ rows
-- over ~34 paged PostgREST round-trips, ~11s) and aggregated them in Python just
-- to render a 10-row page. This function does the group/rank/recent-trend/sort/
-- paginate in Postgres (~70ms, index-backed) and returns only the requested page
-- plus a total_count window column, so the read cost stays flat as efforts grow.
--
-- It reproduces the previous Python summary semantics exactly:
--   best_time_s   = fastest effort
--   attempts      = effort count
--   latest_rank   = rank of the most-recent effort by (elapsed_time_s, start_date)
--   pr            = latest_rank = 1
--   improvement_s = pr and attempts >= 2 ? second_best - best : null
--   recent_times_s= last 8 efforts by date, oldest -> newest
-- Name search is a literal case-insensitive substring (strpos), matching the old
-- `needle in name.lower()`. Sort is by attempts (p_dir), then name asc.
create or replace function list_segment_summaries(
  p_athlete_id bigint,
  p_as_of      timestamptz,
  p_q          text,
  p_dir        text,
  p_limit      int,
  p_offset     int
)
returns table (
  id             bigint,
  name           text,
  distance_m     double precision,
  avg_grade      double precision,
  best_time_s    int,
  attempts       int,
  pr             boolean,
  latest_rank    int,
  improvement_s  int,
  recent_times_s int[],
  total_count    bigint
)
language sql
stable
set search_path = ''
as $$
  with ranked as (
    select
      se.segment_id,
      se.elapsed_time_s,
      se.start_date,
      row_number() over (partition by se.segment_id order by se.start_date desc)               as recency,
      rank()       over (partition by se.segment_id order by se.elapsed_time_s asc, se.start_date asc) as time_rank
    from public.segment_efforts se
    where se.athlete_id = p_athlete_id
      and se.created_at <= p_as_of
  ),
  agg as (
    select
      r.segment_id,
      count(*)::int                                                              as attempts,
      min(r.elapsed_time_s)::int                                                 as best_time_s,
      (array_agg(r.elapsed_time_s order by r.elapsed_time_s))[2]                 as second_best_s,
      max(case when r.recency = 1 then r.time_rank end)::int                     as latest_rank,
      (array_agg(r.elapsed_time_s order by r.recency desc)
         filter (where r.recency <= 8))::int[]                                   as recent_times_s
    from ranked r
    group by r.segment_id
  ),
  joined as (
    select
      s.id,
      coalesce(s.name, 'Segment')                                               as name,
      coalesce(s.distance_m, 0)                                                 as distance_m,
      coalesce(s.avg_grade, 0)                                                  as avg_grade,
      a.best_time_s,
      a.attempts,
      (a.latest_rank = 1)                                                       as pr,
      a.latest_rank,
      case when a.latest_rank = 1 and a.attempts >= 2
           then a.second_best_s - a.best_time_s end                            as improvement_s,
      a.recent_times_s
    from agg a
    join public.segments s on s.id = a.segment_id
    where p_q is null or strpos(lower(s.name), lower(p_q)) > 0
  )
  select
    j.id, j.name, j.distance_m, j.avg_grade, j.best_time_s, j.attempts,
    j.pr, j.latest_rank, j.improvement_s, j.recent_times_s,
    count(*) over ()                                                            as total_count
  from joined j
  order by
    case when p_dir = 'asc'  then j.attempts end asc,
    case when p_dir = 'desc' then j.attempts end desc,
    j.name asc
  limit p_limit offset p_offset
$$;
