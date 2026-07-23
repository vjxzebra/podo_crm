export const SESSION_EXPIRED_EVENT = "podoria:session-expired";

export function isProtectedUnauthorized(request: Request, response: Response): boolean {
  if (response.status !== 401) return false;
  const path = new URL(request.url).pathname;
  if (path === "/api/v1/session" || path === "/api/v1/auth/login") return false;
  return !(path === "/api/v1/password-reset-requests" && request.method === "POST");
}
