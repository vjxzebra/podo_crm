import createClient from "openapi-fetch";

import type { paths } from "./schema";
import { isProtectedUnauthorized, SESSION_EXPIRED_EVENT } from "../auth/sessionEvents";

export const apiClient = createClient<paths>({
  baseUrl: window.location.origin,
  fetch: async (request) => {
    const response = await window.fetch(request);
    if (isProtectedUnauthorized(request, response)) {
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
    return response;
  },
});
