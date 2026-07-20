import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

export const adminSession = {
  user: {
    id: 1,
    email: "admin@example.test",
    display_name: "Тест Адміністратор",
    role: "admin",
  },
  route_ids: [
    "overview",
    "calendar",
    "patients",
    "work-items",
    "finance",
    "inventory",
    "analytics",
    "notifications",
    "settings",
    "password-resets",
    "contracts",
  ],
  must_change_password: false,
  temporary_password_expires_at: null,
  temporary_password_expired: false,
} as const;

export const receptionSession = {
  user: {
    id: 2,
    email: "reception@example.test",
    display_name: "Тест Рецепція",
    role: "reception",
  },
  route_ids: ["overview", "calendar", "patients", "work-items", "finance", "notifications"],
  must_change_password: false,
  temporary_password_expires_at: null,
  temporary_password_expired: false,
} as const;

export const forcedPasswordSession = {
  user: {
    id: 3,
    email: "olena@example.test",
    display_name: "Олена Мельник",
    role: "podologist",
  },
  route_ids: [],
  must_change_password: true,
  temporary_password_expires_at: "2026-07-21T12:00:00+03:00",
  temporary_password_expired: false,
} as const;

export const anonymousProblem = {
  code: "authentication_required",
  message: "Потрібна автентифікація.",
  fields: {},
  correlation_id: "test-request",
};

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input.toString();
      const method = input instanceof Request ? input.method : (init?.method ?? "GET");
      if (url.includes("/api/v1/auth/logout") && method === "POST") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      return Promise.resolve(jsonResponse(adminSession));
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
