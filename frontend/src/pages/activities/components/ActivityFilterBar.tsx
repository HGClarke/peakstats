import { Search } from "lucide-react";

interface Props {
  q: string;
  minDist: string;
  minTime: string;
  minElev: string;
  onQ: (v: string) => void;
  onMinDist: (v: string) => void;
  onMinTime: (v: string) => void;
  onMinElev: (v: string) => void;
  onClear: () => void;
}

const numberBox =
  "flex items-center gap-2 h-10 bg-surface-card border border-line rounded-[10px] px-3";
const numberInput =
  "w-12 bg-transparent border-none outline-none text-ink font-mono text-[13px]";
const label = "font-mono text-[10px] tracking-[0.08em] text-faint";

export function ActivityFilterBar({
  q, minDist, minTime, minElev,
  onQ, onMinDist, onMinTime, onMinElev, onClear,
}: Props) {
  return (
    <div className="flex items-center gap-[10px] mb-4 flex-wrap">
      <div className="flex items-center gap-[9px] flex-1 min-w-[220px] h-10 bg-surface-card border border-line rounded-[10px] px-[14px]">
        <Search size={15} className="text-faint" aria-hidden />
        <input
          value={q}
          onChange={(e) => onQ(e.target.value)}
          placeholder="Search activities…"
          aria-label="Search activities"
          className="flex-1 bg-transparent border-none outline-none text-ink text-[13.5px]"
        />
      </div>
      <div className={numberBox}>
        <span className={label}>DIST ≥</span>
        <input type="number" min="0" value={minDist} onChange={(e) => onMinDist(e.target.value)}
          placeholder="0" aria-label="Minimum distance (km)" className={numberInput} />
        <span className="text-[11px] text-subtle">km</span>
      </div>
      <div className={numberBox}>
        <span className={label}>TIME ≥</span>
        <input type="number" min="0" value={minTime} onChange={(e) => onMinTime(e.target.value)}
          placeholder="0" aria-label="Minimum time (min)" className={numberInput} />
        <span className="text-[11px] text-subtle">min</span>
      </div>
      <div className={numberBox}>
        <span className={label}>ELEV ≥</span>
        <input type="number" min="0" value={minElev} onChange={(e) => onMinElev(e.target.value)}
          placeholder="0" aria-label="Minimum elevation (m)" className={numberInput} />
        <span className="text-[11px] text-subtle">m</span>
      </div>
      <button
        onClick={onClear}
        className="h-10 px-[14px] rounded-[10px] bg-transparent border border-line text-subtle text-[13px] cursor-pointer hover:text-ink"
      >
        Clear
      </button>
    </div>
  );
}
