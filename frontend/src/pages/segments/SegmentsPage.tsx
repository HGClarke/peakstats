// frontend/src/pages/segments/SegmentsPage.tsx
import { useState } from "react";
import { useNavigate } from "react-router";
import { logout, useAthlete } from "@/api/auth";
import { toSegmentRow, useSegments } from "@/api/segments";
import { useSyncStatus } from "@/api/sync";
import { AppShell } from "@/components/app-shell/AppShell";
import { SearchInput } from "@/components/SearchInput";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import type { SortDir } from "@/types/segments";
import { useEffect } from "react";
import { SegmentTable } from "./components/SegmentTable";

export default function SegmentsPage() {
  const { data: athlete, error } = useAthlete();
  const { data: status } = useSyncStatus();
  const navigate = useNavigate();

  const [q, setQ] = useState("");
  const [direction, setDirection] = useState<SortDir>("desc");
  const dq = useDebouncedValue(q, 300);

  const { data, isLoading } = useSegments({ q: dq, sort: "attempts", direction });

  useEffect(() => {
    if (error) navigate("/", { replace: true });
  }, [error, navigate]);
  useEffect(() => {
    if (status?.status === "never_synced") navigate("/sync", { replace: true });
  }, [status, navigate]);

  const synced = status?.status === "idle";
  const rows = (data?.segments ?? []).map(toSegmentRow);
  const emptyMessage = rows.length > 0 ? null : "No segments match your search.";

  const handleLogout = async () => { await logout(); navigate("/", { replace: true }); };

  return (
    <AppShell
      navActive="Segments"
      athlete={athlete ?? null}
      syncLabel={synced ? "Up to date" : "Syncing…"}
      onLogout={handleLogout}
      title="Segments"
      subtitle={`${data?.segments.length ?? 0} SEGMENTS`}
    >
      <div className="h-full overflow-y-auto p-7">
        <div className="mb-4 max-w-[360px]">
          <SearchInput value={q} onChange={setQ} placeholder="Search segments…" ariaLabel="Search segments" />
        </div>
        {isLoading && !data ? (
          <div className="bg-surface-card border border-line rounded-2xl p-2" role="status" aria-label="Loading segments">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="px-[18px] py-4"><div className="h-4 w-full rounded bg-skel animate-pkskel" /></div>
            ))}
          </div>
        ) : (
          <SegmentTable
            rows={rows}
            sortDir={direction}
            onSortAttempts={() => setDirection((d) => (d === "asc" ? "desc" : "asc"))}
            onOpen={(id) => navigate(`/segments/${id}`)}
            emptyMessage={emptyMessage}
          />
        )}
      </div>
    </AppShell>
  );
}
