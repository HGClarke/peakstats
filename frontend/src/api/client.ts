import { config } from "@/lib/config";

/** Error thrown for non-2xx responses, carrying the HTTP status. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * Thin typed wrapper around `fetch`, scoped to the configured API base URL.
 * Resolves with parsed JSON, or rejects with an {@link ApiError} on failure.
 */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new ApiError(
      response.status,
      `Request to ${path} failed: ${response.status} ${response.statusText}`
    );
  }

  return (await response.json()) as T;
}
