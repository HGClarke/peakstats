// frontend/src/pages/segments/components/SegmentAttemptsTable.tsx
import { useState } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { prepareAttempts } from "@/api/segments";
import { Pager } from "@/components/Pager";
import { SearchInput } from "@/components/SearchInput";
import type { Units } from "@/lib/units";
import type { AttemptSortKey, SegmentEffortDTO, SortDir } from "@/types/segments";

const PAGE_SIZE = 8;
const COLUMNS: { label: string; key: AttemptSortKey }[] = [
  { label: "DATE", key: "date" },
  { label: "ACTIVITY", key: "activity" },
  { label: "TIME", key: "time" },
  { label: "POWER", key: "power" },
  { label: "SPEED", key: "speed" },
  { label: "HR", key: "hr" },
];
const grid = "grid grid-cols-[1.25fr_1.3fr_0.9fr_1fr_1fr_0.85fr] gap-3 items-center";

export function SegmentAttemptsTable({
  efforts, selectedId, onSelect, units,
}: {
  efforts: SegmentEffortDTO[];
  selectedId: number;
  onSelect: (id: number) => void;
  units: Units;
}) {
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<AttemptSortKey>("date");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [page, setPage] = useState(1);

  const { rows, total, totalPages } = prepareAttempts(efforts, {
    query, sortKey, sortDir, page, pageSize: PAGE_SIZE, units,
  });

  const sort = (key: AttemptSortKey) => {
    if (key === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("desc"); }
    setPage(1);
  };

  return (
    <div>
      <div className="flex items-center justify-between gap-3 mb-3">
        <span className="font-display font-medium text-[15px]">All attempts</span>
        <div className="w-[260px] max-w-[55%]">
          <SearchInput value={query} onChange={(v) => { setQuery(v); setPage(1); }}
            placeholder="Search activity or date" ariaLabel="Search attempts" />
        </div>
      </div>
      <div className="bg-surface-card border border-line rounded-2xl p-2">
        <div className={`${grid} px-[18px] py-[14px] font-mono text-[10px] tracking-[0.1em] text-faint border-b border-line-subtle`}>
          {COLUMNS.map((c) => (
            <button key={c.key} onClick={() => sort(c.key)}
              className={`flex items-center gap-1 select-none bg-transparent border-none cursor-pointer text-left font-mono ${sortKey === c.key ? "text-ink" : "text-faint"}`}>
              {c.label}
              {sortKey === c.key && (sortDir === "asc" ? <ArrowUp size={11} aria-hidden /> : <ArrowDown size={11} aria-hidden />)}
            </button>
          ))}
        </div>
        {rows.map((r) => {
          const tag = r.isBest ? "PR" : r.id === selectedId ? "SELECTED" : null;
          return (
            <button key={r.id} onClick={() => onSelect(r.id)}
              className={`${grid} w-full text-left px-[18px] py-[14px] rounded-[11px] bg-transparent border-none cursor-pointer hover:bg-surface-inset ${r.id === selectedId ? "bg-surface-inset" : ""}`}>
              <span className="flex items-center gap-[11px] text-[13.5px] text-ink2">
                <span className={`w-2 h-2 rounded-full flex-none ${r.isBest ? "bg-strava" : "bg-muted5"}`} />
                {r.date}
                {tag && (
                  <span className={`font-mono text-[9px] tracking-[0.08em] px-[7px] py-[2px] rounded-[5px] ${r.isBest ? "text-strava bg-strava-soft" : "text-body bg-surface-inset"}`}>{tag}</span>
                )}
              </span>
              <span className="text-[13.5px] text-ink2 truncate">{r.activity}</span>
              <span className="font-mono text-[14px] text-ink">{r.time}</span>
              <span className="font-mono text-[13px] text-body">{r.power}</span>
              <span className="font-mono text-[13px] text-body">{r.speed}</span>
              <span className="font-mono text-[13px] text-body">{r.hr}</span>
            </button>
          );
        })}
        {rows.length === 0 && (
          <div className="px-[18px] py-10 text-center text-subtle text-[13.5px]">No attempts match your search.</div>
        )}
      </div>
      <Pager page={page} totalPages={totalPages} total={total} pageSize={PAGE_SIZE} onPage={setPage} noun="attempts" />
    </div>
  );
}
