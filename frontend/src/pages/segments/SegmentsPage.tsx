// frontend/src/pages/segments/SegmentsPage.tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { logout, useAthlete } from "@/api/auth";
import { type SegmentsQuery, toSegmentRow, useSegments } from "@/api/segments";
import { useSyncStatus } from "@/api/sync";
import { AppShell } from "@/components/app-shell/AppShell";
import { Pager } from "@/components/Pager";
import { SearchInput } from "@/components/SearchInput";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import type { SortDir } from "@/types/segments";
import { SegmentTable } from "./components/SegmentTable";

export default function SegmentsPage() {
  const { data: athlete, error } = useAthlete();
  const { data: status } = useSyncStatus();
  const navigate = useNavigate();

  const [q, setQ] = useState("");
  const [direction, setDirection] = useState<SortDir>("desc");
  const [page, setPage] = useState(1);
  const [asOf, setAsOf] = useState<string | null>(null);
  const dq = useDebouncedValue(q, 300);

  const query: SegmentsQuery = { q: dq, sort: "attempts", direction, page, asOf };
  const { data, isLoading } = useSegments(query);

  // Capture the snapshot from the first response (render-time state pattern, as
  // in ActivitiesPage) so paging stays stable if a sync lands mid-browse.
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
  const total = data?.total ?? 0;
  const rows = (data?.segments ?? []).map(toSegmentRow);
  const emptyMessage = rows.length > 0 ? null : "No segments match your search.";

  const handleQ = (v: string) => { setQ(v); setPage(1); };
  const handleSort = () => { setDirection((d) => (d === "asc" ? "desc" : "asc")); setPage(1); };

  const handleLogout = async () => { await logout(); navigate("/", { replace: true }); };

  return (
    <AppShell
      navActive="Segments"
      athlete={athlete ?? null}
      syncLabel={synced ? "Up to date" : "Syncing…"}
      onLogout={handleLogout}
      title="Segments"
      subtitle={`${total} SEGMENTS`}
    >
      <div className="h-full overflow-y-auto p-7">
        <div className="mb-4 max-w-[360px]">
          <SearchInput value={q} onChange={handleQ} placeholder="Search segments…" ariaLabel="Search segments" />
        </div>
        {isLoading && !data ? (
          <div className="bg-surface-card border border-line rounded-2xl p-2" role="status" aria-label="Loading segments">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="px-[18px] py-4"><div className="h-4 w-full rounded bg-skel animate-pkskel" /></div>
            ))}
          </div>
        ) : (
          <>
            <SegmentTable
              rows={rows}
              sortDir={direction}
              onSortAttempts={handleSort}
              onOpen={(id) => navigate(`/segments/${id}`)}
              emptyMessage={emptyMessage}
            />
            <Pager
              page={data?.page ?? 1}
              totalPages={data?.total_pages ?? 1}
              total={total}
              pageSize={data?.page_size ?? 10}
              onPage={setPage}
              noun="segments"
            />
          </>
        )}
      </div>
    </AppShell>
  );
}
