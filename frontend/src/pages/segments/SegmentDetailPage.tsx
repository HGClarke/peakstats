// frontend/src/pages/segments/SegmentDetailPage.tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { logout, useAthlete } from "@/api/auth";
import { useSegment } from "@/api/segments";
import { useSyncStatus } from "@/api/sync";
import { AppShell } from "@/components/app-shell/AppShell";
import { SegmentAttemptsTable } from "./components/SegmentAttemptsTable";
import { SegmentCompare } from "./components/SegmentCompare";
import { SegmentMetaCards } from "./components/SegmentMetaCards";

export default function SegmentDetailPage() {
  const { id } = useParams();
  const segmentId = Number(id);
  const { data: athlete, error } = useAthlete();
  const { data: status } = useSyncStatus();
  const { data: seg, isLoading } = useSegment(segmentId);
  const navigate = useNavigate();

  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    if (error) navigate("/", { replace: true });
  }, [error, navigate]);

  // Default the compared attempt to the most recent non-best effort.
  const best = seg?.efforts.find((e) => e.is_best) ?? seg?.efforts[0];
  const defaultSel = seg?.efforts.find((e) => !e.is_best) ?? best;
  if (seg && selectedId === null && defaultSel) setSelectedId(defaultSel.id);

  const synced = status?.status === "idle";
  const handleLogout = async () => { await logout(); navigate("/", { replace: true }); };

  const selected = seg?.efforts.find((e) => e.id === selectedId) ?? best;

  return (
    <AppShell
      navActive="Segments"
      athlete={athlete ?? null}
      syncLabel={synced ? "Up to date" : "Syncing…"}
      onLogout={handleLogout}
      title={seg?.name ?? "Segment"}
      subtitle={seg ? `${seg.attempts} ATTEMPTS` : ""}
      backTo="/segments"
    >
      <div className="h-full overflow-y-auto p-7">
        {isLoading || !seg || !best || !selected ? (
          <div role="status" aria-label="Loading segment" className="h-24 rounded-2xl bg-skel animate-pkskel" />
        ) : (
          <>
            <SegmentMetaCards seg={seg} />
            <SegmentCompare best={best} selected={selected} />
            <SegmentAttemptsTable
              efforts={seg.efforts}
              selectedId={selected.id}
              onSelect={setSelectedId}
            />
          </>
        )}
      </div>
    </AppShell>
  );
}
