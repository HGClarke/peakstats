-- Overview aggregation RPC.
--
-- The old approach pulled a full year of raw activity rows to Python and
-- aggregated there (~400 KB+ payload for active riders). This function does
-- every aggregation in Postgres and returns a single pre-computed row, so
-- only the summary crosses the wire (~1 KB).
--
-- Python still handles zone computation (histograms from activity_metrics)
-- because the binning logic is non-trivial PL/pgSQL. The function returns
-- this_activity_ids so the caller can fetch metrics for just those rides.
--
-- Period bounds follow Python's convention:
--   week  → ISO week (Monday start), ±7 days
--   month → calendar month
--   year  → calendar year
-- Local time is derived from start_date_local (text) when present, falling
-- back to start_date AT TIME ZONE p_timezone.

create or replace function get_overview_data(
    p_athlete_id  bigint,
    p_period      text,           -- 'week' | 'month' | 'year'
    p_now_utc     timestamptz,
    p_timezone    text default 'UTC'
)
returns table (
    this_dist_m       double precision,
    this_elev_m       double precision,
    this_time_s       bigint,
    this_speed_ms     double precision,
    last_dist_m       double precision,
    last_elev_m       double precision,
    last_time_s       bigint,
    last_speed_ms     double precision,
    rides             bigint,
    prs               bigint,
    top_speed_ms      double precision,
    top_avg_power_w   double precision,
    longest_ride_m    double precision,
    max_elev_m        double precision,
    week_dist_m       double precision,
    heatmap_year      int,
    ride_types        jsonb,
    recent_rides      jsonb,
    heatmap_days      jsonb,
    trend             jsonb,
    this_activity_ids jsonb
)
language plpgsql
stable
set search_path = ''
as $$
declare
    v_base            timestamp;
    v_yr              int;
    v_this_start      timestamp;
    v_this_end        timestamp;
    v_last_start      timestamp;
    v_year_start      timestamp;
    v_week_start      timestamp;
    v_query_start_utc timestamptz;
    v_n_buckets       int;
begin
    -- Local midnight as a naive timestamp (tz info dropped after conversion)
    v_base := date_trunc('day', p_now_utc at time zone p_timezone);
    v_yr   := extract(year from v_base)::int;

    -- Period bounds; ISO week uses Monday (isodow=1) as the start
    case p_period
        when 'week' then
            v_this_start := v_base - make_interval(days => (extract(isodow from v_base)::int - 1));
            v_this_end   := v_this_start + interval '7 days';
            v_last_start := v_this_start - interval '7 days';
            v_n_buckets  := 7;
        when 'month' then
            v_this_start := date_trunc('month', v_base);
            v_this_end   := v_this_start + interval '1 month';
            v_last_start := v_this_start - interval '1 month';
            v_n_buckets  := (v_this_end::date - v_this_start::date)::int;
        else  -- 'year'
            v_this_start := make_timestamp(v_yr, 1, 1, 0, 0, 0);
            v_this_end   := make_timestamp(v_yr + 1, 1, 1, 0, 0, 0);
            v_last_start := make_timestamp(v_yr - 1, 1, 1, 0, 0, 0);
            v_n_buckets  := 12;
    end case;

    v_year_start      := make_timestamp(v_yr, 1, 1, 0, 0, 0);
    v_week_start      := v_base - make_interval(days => (extract(isodow from v_base)::int - 1));
    -- Extra day buffer mirrors Python: UTC start_date can lag local time by up to ~14h
    v_query_start_utc := (least(v_year_start, v_last_start) - interval '1 day') at time zone p_timezone;

    return query
    with acts as (
        select
            a.id,
            a.name,
            a.type,
            -- Emit start_date as ISO-8601 UTC string matching PostgREST's default format
            to_char(a.start_date at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') as start_date,
            a.start_date_local,
            a.distance_m,
            a.moving_time_s,
            a.elev_gain_m,
            a.avg_speed_ms,
            a.avg_watts,
            coalesce(a.is_pr, false)                                           as is_pr,
            -- Wall-clock local time used for all bucketing; text col cast, falls back to UTC→local
            coalesce(
                nullif(a.start_date_local, '')::timestamp,
                a.start_date at time zone p_timezone
            )                                                                  as local_ts
        from public.activities a
        where a.athlete_id = p_athlete_id
          and a.start_date >= v_query_start_utc
    ),
    this_acts as (
        select * from acts where local_ts >= v_this_start and local_ts < v_this_end
    ),
    last_acts as (
        select distance_m, moving_time_s, elev_gain_m
        from acts
        where local_ts >= v_last_start and local_ts < v_this_start
    ),
    heatmap_agg as (
        select
            (local_ts::date)::text                                             as day,
            round(sum(distance_m)::numeric, 1)::double precision              as dist
        from acts
        where extract(year from local_ts)::int = v_yr
        group by local_ts::date
        having sum(distance_m) > 0
        order by day
    ),
    trend_raw as (
        select
            case p_period
                when 'year' then extract(month from local_ts)::int - 1
                else (local_ts::date - v_this_start::date)::int
            end                                                                as bucket,
            round(sum(distance_m)::numeric, 1)::double precision              as dist
        from this_acts
        group by 1
    ),
    trend_full as (
        select
            gs.i::int                                                          as bucket,
            coalesce(tr.dist, 0.0)                                            as value,
            case p_period
                when 'week' then
                    (array['MON','TUE','WED','THU','FRI','SAT','SUN'])[gs.i + 1]
                when 'year' then
                    (array['JAN','FEB','MAR','APR','MAY','JUN',
                           'JUL','AUG','SEP','OCT','NOV','DEC'])[gs.i + 1]
                else
                    case when gs.i % 7 = 0
                         then 'W' || ((gs.i / 7) + 1)::text
                         else ''
                    end
            end                                                                as label
        from generate_series(0, v_n_buckets - 1) as gs(i)
        left join trend_raw tr on tr.bucket = gs.i
    ),
    this_agg as (
        select
            coalesce(sum(distance_m), 0)                                      as dist_m,
            coalesce(sum(elev_gain_m), 0)                                     as elev_m,
            coalesce(sum(moving_time_s), 0)::bigint                           as time_s,
            case when sum(moving_time_s) > 0
                 then sum(distance_m) / sum(moving_time_s)::double precision
                 end                                                           as speed_ms,
            count(*)                                                           as rides,
            count(*) filter (where is_pr)                                     as prs,
            max(avg_speed_ms)                                                  as top_speed_ms,
            max(avg_watts)                                                     as top_avg_power_w,
            coalesce(max(distance_m), 0.0)                                    as longest_ride_m,
            coalesce(max(elev_gain_m), 0.0)                                   as max_elev_m
        from this_acts
    ),
    last_agg as (
        select
            coalesce(sum(distance_m), 0)                                      as dist_m,
            coalesce(sum(elev_gain_m), 0)                                     as elev_m,
            coalesce(sum(moving_time_s), 0)::bigint                           as time_s,
            case when sum(moving_time_s) > 0
                 then sum(distance_m) / sum(moving_time_s)::double precision
                 end                                                           as speed_ms
        from last_acts
    )
    select
        ta.dist_m,
        ta.elev_m,
        ta.time_s,
        ta.speed_ms,
        la.dist_m,
        la.elev_m,
        la.time_s,
        la.speed_ms,
        ta.rides,
        ta.prs,
        ta.top_speed_ms,
        ta.top_avg_power_w,
        ta.longest_ride_m,
        ta.max_elev_m,
        -- week_dist_m: current-week distance used by the goal ring regardless of period
        coalesce(
            (select sum(distance_m) from acts
             where local_ts >= v_week_start and local_ts < v_week_start + interval '7 days'),
            0.0
        ),
        v_yr::int,
        -- ride_types: [{type, count}] sorted by count desc, type asc
        coalesce(
            (select jsonb_agg(
                        jsonb_build_object('type', rt.type, 'count', rt.cnt)
                        order by rt.cnt desc, rt.type
                    )
             from (select type, count(*)::int as cnt from this_acts group by type) rt),
            '[]'::jsonb
        ),
        -- recent_rides: 5 most recent from the entire query window
        coalesce(
            (select jsonb_agg(jsonb_build_object(
                'id',               r.id,
                'name',             r.name,
                'type',             r.type,
                'start_date',       r.start_date,
                'start_date_local', r.start_date_local,
                'distance_m',       r.distance_m,
                'moving_time_s',    r.moving_time_s,
                'is_pr',            r.is_pr
             ))
             from (select id, name, type, start_date, start_date_local,
                          distance_m, moving_time_s, is_pr
                   from acts order by local_ts desc limit 5) r),
            '[]'::jsonb
        ),
        -- heatmap_days: [{date, distance_m}] for current year
        coalesce(
            (select jsonb_agg(jsonb_build_object('date', h.day, 'distance_m', h.dist))
             from heatmap_agg h),
            '[]'::jsonb
        ),
        -- trend: complete bucket array with labels
        (select jsonb_agg(
                    jsonb_build_object('label', tf.label, 'value', tf.value)
                    order by tf.bucket
                )
         from trend_full tf),
        -- this_activity_ids: for zones computation in Python
        coalesce(
            (select jsonb_agg(id) from this_acts),
            '[]'::jsonb
        )
    from this_agg ta
    cross join last_agg la;
end;
$$;
