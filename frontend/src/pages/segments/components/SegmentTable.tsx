// frontend/src/pages/segments/components/SegmentTable.tsx
import { ArrowDown, ArrowUp, ChevronRight } from "lucide-react";
import type { SegmentRowVM } from "@/types/segments";
import type { SortDir } from "@/types/segments";

interface Props {
  rows: SegmentRowVM[];
  sortDir: SortDir;
  onSortAttempts: () => void;
  onOpen: (id: number) => void;
  emptyMessage: string | null;
}

const grid = "grid grid-cols-[2fr_1fr_1fr_1fr_36px] gap-3 items-center";

export function SegmentTable({ rows, sortDir, onSortAttempts, onOpen, emptyMessage }: Props) {
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-2">
      <div className={`${grid} px-[18px] py-[14px] font-mono text-[10px] tracking-[0.1em] text-faint border-b border-line-subtle`}>
        <span className="select-none">SEGMENT</span>
        <span className="select-none">BEST TIME</span>
        <span className="select-none">STATUS</span>
        <button
          onClick={onSortAttempts}
          className="flex items-center gap-1 select-none bg-transparent border-none cursor-pointer text-left font-mono text-ink"
        >
          ATTEMPTS
          {sortDir === "asc" ? <ArrowUp size={11} aria-hidden /> : <ArrowDown size={11} aria-hidden />}
        </button>
        <span />
      </div>

      {rows.map((r) => (
        <button
          key={r.id}
          onClick={() => onOpen(r.id)}
          className={`${grid} w-full text-left px-[18px] py-4 rounded-[11px] bg-transparent border-none cursor-pointer hover:bg-surface-inset`}
        >
          <div className="flex items-center gap-[13px] min-w-0">
            <span className={`w-[9px] h-[9px] rounded-full flex-none ${r.isPr ? "bg-ride-green" : "bg-muted5"}`} />
            <div className="min-w-0">
              <div className="text-[14px] font-medium text-ink truncate">{r.name}</div>
              <div className="font-mono text-[10.5px] text-faint mt-[2px]">{r.meta}</div>
            </div>
          </div>
          <span className="font-mono text-[15px] text-ink">{r.bestTime}</span>
          <span className={`font-mono text-[11px] ${r.isPr ? "text-ride-green" : "text-faint"}`}>{r.statusText}</span>
          <span className="font-mono text-[13px] text-body">{r.attemptsLabel}</span>
          <ChevronRight size={16} className="text-faint justify-self-end" aria-hidden />
        </button>
      ))}

      {emptyMessage && (
        <div className="px-[18px] py-12 text-center text-subtle text-[14px]">{emptyMessage}</div>
      )}
    </div>
  );
}
