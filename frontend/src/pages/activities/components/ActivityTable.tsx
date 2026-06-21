import { ArrowDown, ArrowUp, ChevronRight } from "lucide-react";
import type { ActivityRowVM, SortDir, SortField } from "@/types/activities";

interface Props {
  rows: ActivityRowVM[];
  sort: SortField;
  direction: SortDir;
  onSort: (field: SortField) => void;
  emptyMessage: string | null;
}

const COLUMNS: { label: string; field: SortField | null }[] = [
  { label: "ACTIVITY", field: null },
  { label: "DISTANCE", field: "distance" },
  { label: "TIME", field: "time" },
  { label: "ELEVATION", field: "elevation" },
  { label: "AVG SPEED", field: "speed" },
];

const grid = "grid grid-cols-[1.7fr_1fr_1fr_1fr_1fr_36px] gap-3 items-center";

export function ActivityTable({ rows, sort, direction, onSort, emptyMessage }: Props) {
  return (
    <div className="bg-surface-card border border-line rounded-2xl p-2">
      <div className={`${grid} px-[18px] py-[14px] font-mono text-[10px] tracking-[0.1em] text-faint border-b border-line-subtle`}>
        {COLUMNS.map(({ label, field }) =>
          field ? (
            <button
              key={label}
              onClick={() => onSort(field)}
              className={`flex items-center gap-1 select-none bg-transparent border-none cursor-pointer text-left font-mono ${
                sort === field ? "text-ink" : "text-faint"
              }`}
            >
              {label}
              {sort === field &&
                (direction === "asc"
                  ? <ArrowUp size={11} aria-hidden />
                  : <ArrowDown size={11} aria-hidden />)}
            </button>
          ) : (
            <span key={label} className="select-none">{label}</span>
          ),
        )}
        <span />
      </div>

      {rows.map((r) => (
        <div key={r.id} className={`${grid} px-[18px] py-[15px] rounded-[11px]`}>
          <div className="flex items-center gap-[13px] min-w-0">
            <span className="w-[9px] h-[9px] rounded-full bg-strava flex-none" />
            <div className="min-w-0">
              <div className="text-[14px] font-medium text-ink truncate">{r.name}</div>
              <div className="font-mono text-[10.5px] text-faint mt-[2px]">{r.meta}</div>
            </div>
          </div>
          <span className="font-display font-semibold text-[15px] text-ink">{r.distLabel}</span>
          <span className="font-mono text-[13px] text-body">{r.durLabel}</span>
          <span className="font-mono text-[13px] text-body">{r.elevLabel}</span>
          <span className="font-mono text-[13px] text-body">{r.speedLabel}</span>
          <ChevronRight size={16} className="text-faint justify-self-end" aria-hidden />
        </div>
      ))}

      {emptyMessage && (
        <div className="px-[18px] py-12 text-center text-subtle text-[14px]">
          {emptyMessage}
        </div>
      )}
    </div>
  );
}
