import type { Period } from "@/types/overview";

const OPTIONS: { value: Period; label: string }[] = [
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
  { value: "year", label: "Year" },
];

/** Segmented Week/Month/Year control for the Overview header. */
export function PeriodSelector({
  value,
  onChange,
}: {
  value: Period;
  onChange: (period: Period) => void;
}) {
  return (
    <div className="flex gap-[3px] bg-surface-inset border border-line rounded-[10px] p-[3px]">
      {OPTIONS.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(o.value)}
            className={`px-[13px] h-[30px] rounded-[7px] font-mono text-[11px] cursor-pointer transition-colors ${
              active ? "bg-surface-card text-ink" : "text-subtle hover:text-ink"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
