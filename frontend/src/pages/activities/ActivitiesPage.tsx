import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { disconnect, logout, useAthlete } from "@/api/auth";
import { type ActivitiesQuery, toActivityRow, useActivities } from "@/api/activities";
import { useSyncStatus } from "@/api/sync";
import { useSettings } from "@/app/providers/settings-context";
import { AppShell } from "@/components/app-shell/AppShell";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import { useUrlQueryState } from "@/lib/useUrlQueryState";
import type { SortField } from "@/types/activities";
import { Pager } from "@/components/Pager";
import { ActivityFilterBar } from "./components/ActivityFilterBar";
import { ActivityTable } from "./components/ActivityTable";

function SkeletonRows() {
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-2 transition-colors duration-300" role="status"
      aria-label="Loading activities">
      {[0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
        <div key={i} className="px-[18px] py-[15px]">
          <div className="h-4 w-full rounded bg-skel animate-pkskel" />
        </div>
      ))}
    </div>
  );
}

export default function ActivitiesPage() {
  const { data: athlete, error } = useAthlete();
  const { data: status } = useSyncStatus();
  const navigate = useNavigate();
  const { units } = useSettings();

  // List state lives in the URL so navigating into a ride and pressing Back
  // restores exactly what was on screen (also refresh-safe and shareable).
  const [params, setParams] = useUrlQueryState();
  const q = params.get("q") ?? "";
  const minDist = params.get("min_dist") ?? "";
  const minTime = params.get("min_time") ?? "";
  const minElev = params.get("min_elev") ?? "";
  const sort = (params.get("sort") as SortField | null) ?? "date";
  const direction = params.get("dir") === "asc" ? "asc" : "desc";
  const page = Number(params.get("page")) || 1;

  const [asOf, setAsOf] = useState<string | null>(null);

  const dq = useDebouncedValue(q, 300);
  const dDist = useDebouncedValue(minDist, 300);
  const dTime = useDebouncedValue(minTime, 300);
  const dElev = useDebouncedValue(minElev, 300);

  const query: ActivitiesQuery = {
    q: dq, minDist: dDist, minTime: dTime, minElev: dElev,
    sort, direction, page, asOf, units,
  };
  const { data, isLoading } = useActivities(query);

  // Capture the snapshot from the first response using React's render-time state
  // update pattern (equivalent to getDerivedStateFromProps: safe, synchronous,
  // triggers an immediate second render instead of a paint + re-render cycle).
  if (data?.as_of && asOf === null) {
    setAsOf(data.as_of);
  }

  useEffect(() => {
    if (error) navigate("/", { replace: true });
  }, [error, navigate]);

  useEffect(() => {
    if (status?.status === "never_synced") navigate("/sync", { replace: true });
  }, [status, navigate]);

  const synced = status?.status === "idle";

  const handleSort = (field: SortField) => {
    const dir = field === sort ? (direction === "asc" ? "desc" : "asc") : "desc";
    setParams({ sort: field, dir, page: null });
  };

  const handleQ = (v: string) => setParams({ q: v, page: null });
  const handleMinDist = (v: string) => setParams({ min_dist: v, page: null });
  const handleMinTime = (v: string) => setParams({ min_time: v, page: null });
  const handleMinElev = (v: string) => setParams({ min_elev: v, page: null });

  const handleClear = () =>
    setParams({ q: null, min_dist: null, min_time: null, min_elev: null, page: null });

  const handlePage = (p: number) => setParams({ page: p === 1 ? null : p });

  const handleLogout = async () => { await logout(); navigate("/", { replace: true }); };
  const handleDisconnect = async () => { await disconnect(); navigate("/", { replace: true }); };

  const rows = (data?.activities ?? []).map((a) => toActivityRow(a, units));
  const total = data?.total ?? 0;
  const filtersActive = Boolean(q || minDist || minTime || minElev);
  const emptyMessage =
    rows.length > 0 ? null
      : filtersActive ? "No activities match your filters."
        : "No activities yet.";

  return (
    <AppShell
      navActive="Activities"
      athlete={athlete}
      syncLabel={synced ? "Up to date" : "Syncing…"}
      onLogout={handleLogout}
      title="Activities"
      subtitle={synced ? `${total} RIDES` : "SYNCING"}
    >
      <div className="h-full overflow-y-auto p-7">
        <ActivityFilterBar
          q={q} minDist={minDist} minTime={minTime} minElev={minElev}
          onQ={handleQ} onMinDist={handleMinDist} onMinTime={handleMinTime} onMinElev={handleMinElev}
          onClear={handleClear}
          units={units}
        />
        {isLoading && !data ? (
          <SkeletonRows />
        ) : (
          <>
            <ActivityTable
              rows={rows} sort={sort} direction={direction}
              onSort={handleSort} emptyMessage={emptyMessage}
            />
            <Pager
              page={data?.page ?? 1}
              totalPages={data?.total_pages ?? 1}
              total={total}
              pageSize={data?.page_size ?? 9}
              onPage={handlePage}
              noun="activities"
            />
          </>
        )}
        <div className="pt-7">
          <button
            onClick={handleDisconnect}
            className="font-mono text-[11px] text-faint bg-transparent border-none cursor-pointer hover:text-strava"
          >
            Disconnect Strava
          </button>
        </div>
      </div>
    </AppShell>
  );
}
