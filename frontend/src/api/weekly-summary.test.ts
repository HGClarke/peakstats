import { renderHook, waitFor } from "@testing-library/react";
import { useWeeklySummary, fetchWeeklySummary } from "./weekly-summary";

it("fetchWeeklySummary resolves a fully-formed summary", async () => {
  const summary = await fetchWeeklySummary();
  expect(summary.totalDistanceKm).toBeGreaterThan(0);
  expect(summary.week).toHaveLength(7);
  expect(summary.stats.length).toBeGreaterThan(0);
  expect(summary.recentRides.length).toBeGreaterThan(0);
});

it("useWeeklySummary starts loading then resolves with data", async () => {
  const { result } = renderHook(() => useWeeklySummary());

  expect(result.current.isLoading).toBe(true);
  expect(result.current.data).toBeNull();

  await waitFor(() => expect(result.current.data).not.toBeNull());

  expect(result.current.isLoading).toBe(false);
  expect(result.current.error).toBeNull();
  expect(result.current.data?.recentRides[0]?.name).toBe("Morning commute");
});
