import { afterEach, vi } from "vitest";
import { apiFetch, ApiError } from "./client";
import { config } from "@/lib/config";

afterEach(() => {
  vi.restoreAllMocks();
});

it("returns parsed JSON on a successful response", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(
      new Response(JSON.stringify({ hello: "world" }), { status: 200 })
    );

  const result = await apiFetch<{ hello: string }>("/ping");

  expect(result).toEqual({ hello: "world" });
  expect(fetchMock).toHaveBeenCalledWith(
    `${config.apiBaseUrl}/ping`,
    expect.objectContaining({ headers: expect.any(Object) })
  );
});

it("throws an ApiError carrying the status on a failed response", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response("nope", { status: 503, statusText: "Service Unavailable" })
  );

  await expect(apiFetch("/ping")).rejects.toBeInstanceOf(ApiError);
  await expect(apiFetch("/ping")).rejects.toMatchObject({ status: 503 });
});
