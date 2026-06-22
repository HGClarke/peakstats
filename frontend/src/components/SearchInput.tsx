import { Search } from "lucide-react";

interface Props {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  ariaLabel: string;
  className?: string;
}

export function SearchInput({ value, onChange, placeholder, ariaLabel, className }: Props) {
  return (
    <div
      className={`flex items-center gap-[9px] h-10 bg-surface-card border border-line rounded-[10px] px-[14px] ${className ?? ""}`}
    >
      <Search size={15} className="text-faint" aria-hidden />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={ariaLabel}
        className="flex-1 min-w-0 bg-transparent border-none outline-none text-ink text-[13.5px]"
      />
    </div>
  );
}
