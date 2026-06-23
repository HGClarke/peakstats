import { useCallback } from "react";
import { useSearchParams } from "react-router";

/** A set of query-param updates; `null` or `""` removes the key (keeps URLs clean). */
export type ParamPatch = Record<string, string | number | null>;

/**
 * Read/write a page's list state in the URL query string, making the URL the
 * single source of truth. Updates use `replace`, so the list stays one history
 * entry — clicking into a detail then pressing Back restores the exact state.
 */
export function useUrlQueryState(): [URLSearchParams, (patch: ParamPatch) => void] {
  const [params, setSearchParams] = useSearchParams();

  const setParams = useCallback(
    (patch: ParamPatch) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [key, value] of Object.entries(patch)) {
            if (value === null || value === "") next.delete(key);
            else next.set(key, String(value));
          }
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  return [params, setParams];
}
