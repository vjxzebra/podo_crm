import { apiClient } from "../api/client";
import type { GlobalSearchApiResult } from "./searchTypes";

export async function searchGlobally(
  query: string,
  signal: AbortSignal,
): Promise<GlobalSearchApiResult> {
  const { data, error, response } = await apiClient.GET("/api/v1/search", {
    params: { query: { q: query } },
    signal,
  });
  return data === undefined
    ? {
        ok: false,
        error,
        status: response.status,
      }
    : { ok: true, data };
}
