interface Option<T extends string> {
  label: string;
  value: T;
}

export function SegmentedControl<T extends string>({
  value, options, onChange, ariaLabel,
}: {
  value: T;
  options: Option<T>[];
  onChange: (value: T) => void;
  ariaLabel: string;
}) {
  return (
    <div role="group" aria-label={ariaLabel} className="inline-flex bg-surface-inset border border-line rounded-[10px] p-1 gap-1">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(o.value)}
            className={`px-[14px] py-[7px] rounded-[7px] text-[13px] font-medium cursor-pointer transition-colors ${active ? "bg-surface-card text-ink" : "text-subtle hover:text-ink"}`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
