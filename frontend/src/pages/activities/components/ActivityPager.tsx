import { makePager } from "@/lib/pager";

interface Props {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPage: (page: number) => void;
}

const edgeBtn =
  "h-[34px] px-3 rounded-[8px] border border-line bg-transparent text-subtle text-[13px] font-medium disabled:opacity-40 disabled:cursor-default enabled:cursor-pointer";

export function ActivityPager({ page, totalPages, total, pageSize, onPage }: Props) {
  if (totalPages <= 1) return null;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(total, page * pageSize);

  return (
    <div className="flex items-center justify-between mt-[18px]">
      <span className="font-mono text-[11px] text-faint">
        Showing {start}–{end} of {total} activities
      </span>
      <div className="flex items-center gap-[6px]">
        <button className={edgeBtn} disabled={page === 1} onClick={() => onPage(page - 1)}>
          ‹ Prev
        </button>
        {makePager(page, totalPages).map((t, i) =>
          t.kind === "gap" ? (
            <span key={`gap-${i}`} className="w-[34px] text-center text-faint font-mono text-[13px]">
              …
            </span>
          ) : (
            <button
              key={t.page}
              onClick={() => onPage(t.page)}
              className={`min-w-[34px] h-[34px] px-[10px] rounded-[8px] font-mono text-[13px] cursor-pointer border ${
                t.active
                  ? "bg-strava text-white border-strava"
                  : "bg-transparent text-subtle border-line"
              }`}
            >
              {t.label}
            </button>
          ),
        )}
        <button className={edgeBtn} disabled={page >= totalPages} onClick={() => onPage(page + 1)}>
          Next ›
        </button>
      </div>
    </div>
  );
}
