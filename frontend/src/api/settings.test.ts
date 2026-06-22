import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { patchSettings } from "./settings";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(
    JSON.stringify({
      id: 7, name: "Ada", avatar_url: null,
      settings: { units: "imperial", theme: "dark", default_period: "week" },
    }),
    { status: 200, headers: { "content-type": "application/json" } },
  )));
});
afterEach(() => vi.unstubAllGlobals());

it("PATCHes /athlete/settings with the partial body", async () => {
  const athlete = await patchSettings({ units: "imperial" });
  const [url, init] = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
  expect(String(url)).toContain("/athlete/settings");
  expect(init.method).toBe("PATCH");
  expect(JSON.parse(init.body)).toEqual({ units: "imperial" });
  expect(athlete.settings.units).toBe("imperial");
});
