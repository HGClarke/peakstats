/** Peakstats wordmark + glyph. Shared across pages (nav, footer, auth). */
export function Logo() {
  return (
    <div className="flex items-center gap-[11px]">
      <div className="w-[30px] h-[30px] rounded-[9px] bg-surface-elevated border border-line flex items-center justify-center">
        <svg width="20" height="20" viewBox="0 0 100 100" fill="none" aria-hidden>
          <polyline
            points="16,70 44,34 64,56 84,30"
            stroke="#fc4c02"
            strokeWidth="10"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
          <line
            x1="16" y1="86" x2="84" y2="86"
            stroke="currentColor"
            className="text-[#6b7280]"
            strokeWidth="8"
            strokeLinecap="round"
          />
        </svg>
      </div>
      <span className="font-display font-semibold text-[18px] text-ink tracking-[-0.01em]">
        peakstats
      </span>
    </div>
  );
}
