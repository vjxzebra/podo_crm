import createClient from "openapi-fetch";

import type { paths } from "./schema";
import { isProtectedUnauthorized, SESSION_EXPIRED_EVENT } from "../auth/sessionEvents";

export async function sessionAwareFetch(request: Request): Promise<Response> {
  const response = await window.fetch(request);
  if (isProtectedUnauthorized(request, response)) {
    window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
  }
  return response;
}

export const apiClient = createClient<paths>({
  baseUrl: window.location.origin,
  fetch: sessionAwareFetch,
});
