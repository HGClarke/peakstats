import type { StatTile } from "@/types/ride";

export function StatTiles({ stats }: { stats: StatTile[] }) {
  return (
    <div className="grid grid-cols-3 gap-[10px] my-4">
      {stats.map(({ label, value, unit }) => (
        <div
          key={label}
          className="bg-surface-inset border border-line-subtle rounded-[12px] px-[14px] py-[13px]"
        >
          <div className="font-mono text-[9.5px] tracking-[0.1em] text-subtle mb-[7px]">
            {label}
          </div>
          <div className="font-display font-semibold text-[19px] text-ink">
            {value}
            {unit && (
              <span className="text-[11px] font-normal text-subtle"> {unit}</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
