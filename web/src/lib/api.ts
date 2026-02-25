/**
 * API client utilities for server-side and client-side API calls.
 */

/** Internal API URL used by server components (Docker service name). */
export const API_INTERNAL_URL =
  process.env.API_INTERNAL_URL || "http://api:8000";

/** Public API base path used by client components (proxied via nginx). */
export const API_PUBLIC = "/api";

/**
 * Return the appropriate API base URL depending on execution context.
 * Server components call the internal Docker URL directly.
 * Client components go through the nginx reverse proxy.
 */
export function getApiUrl(server: boolean): string {
  return server ? API_INTERNAL_URL : API_PUBLIC;
}

/**
 * Typed fetch wrapper for API calls from server components.
 * Throws on non-2xx responses.
 */
export async function fetchApi<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_INTERNAL_URL}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText} (${path})`);
  }

  return res.json() as Promise<T>;
}
