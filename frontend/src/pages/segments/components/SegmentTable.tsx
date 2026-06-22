// frontend/src/pages/segments/components/SegmentTable.tsx
import { ArrowDown, ArrowUp, ChevronRight } from "lucide-react";
import type { GradeBadge, SegmentRowVM, SortDir } from "@/types/segments";
import { SegmentSparkline } from "./SegmentSparkline";

interface Props {
  rows: SegmentRowVM[];
  sortDir: SortDir;
  onSortAttempts: () => void;
  onOpen: (id: number) => void;
  emptyMessage: string | null;
}

const grid = "grid grid-cols-[2.5fr_0.95fr_1.05fr_0.85fr_36px] gap-3 items-center";

function gradeBadge(grade: GradeBadge) {
  return (
    <span
      className="flex-none font-mono text-[9px] font-medium leading-none px-[7px] py-[2px] rounded-[5px] whitespace-nowrap"
      style={{ color: grade.color, background: grade.bg }}
    >
      {grade.label}
    </span>
  );
}

export function SegmentTable({ rows, sortDir, onSortAttempts, onOpen, emptyMessage }: Props) {
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-2">
      <div className={`${grid} px-[18px] py-[14px] font-mono text-[10px] tracking-[0.1em] text-faint border-b border-line-subtle`}>
        <span className="select-none">SEGMENT</span>
        <span className="select-none">BEST TIME</span>
        <span className="select-none">RECENT TREND</span>
        <button
          onClick={onSortAttempts}
          className="flex items-center gap-1 select-none bg-transparent border-none cursor-pointer text-left font-mono text-faint"
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
          className={`${grid} w-full text-left px-[18px] py-4 rounded-[11px] bg-transparent border-none cursor-pointer hover:bg-surface-panel2`}
        >
          <div className="min-w-0">
            <div className="flex items-center gap-[9px] min-w-0">
              <span className="text-[14px] font-medium text-ink2 truncate">{r.name}</span>
              {gradeBadge(r.grade)}
            </div>
            <div className="font-mono text-[10.5px] text-faint mt-[3px]">{r.meta}</div>
          </div>
          <span className="font-mono text-[16px] font-medium text-strava">{r.bestTime}</span>
          <SegmentSparkline trend={r.trend} />
          <span className="font-mono text-[12px] text-muted2 whitespace-nowrap">{r.attemptsLabel}</span>
          <ChevronRight size={16} className="text-muted5 justify-self-end" aria-hidden />
        </button>
      ))}

      {emptyMessage && (
        <div className="px-[18px] py-12 text-center text-subtle text-[14px]">{emptyMessage}</div>
      )}
    </div>
  );
}
