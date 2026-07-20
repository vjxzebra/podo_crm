import createClient from "openapi-fetch";

import type { paths } from "./schema";

export const apiClient = createClient<paths>({
  baseUrl: window.location.origin,
  fetch: (request) => window.fetch(request),
});
