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
    "team",
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

export const clinicProfile = {
  name: "Podoria Clinic",
  phone: "+380 67 111 22 33",
  email: "clinic@podoria.test",
  address: "Київ, вул. Прикладна, 10",
  description: "Професійний догляд за стопами та нігтями.",
  has_logo: false,
  logo_url: null,
  logo_content_type: "",
  logo_size: null,
  version: 1,
  updated_at: "2026-07-21T12:00:00+03:00",
} as const;

export const clinicRoom = {
  id: "8b169a0d-ff81-45b7-ab3f-ed91031d3b5e",
  name: "Кабінет 1",
  is_active: true,
  version: 1,
  created_at: "2026-07-21T12:00:00+03:00",
  updated_at: "2026-07-21T12:00:00+03:00",
} as const;

export const clinicService = {
  id: "2f811768-f227-4b3b-896b-31b0960b8a20",
  code: "CONSULT",
  name: "Первинна консультація",
  duration_minutes: 45,
  price_minor: 120000,
  color: "#0F766E",
  is_active: true,
  version: 1,
  created_at: "2026-07-21T12:00:00+03:00",
  updated_at: "2026-07-21T12:00:00+03:00",
} as const;

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
      if (url.includes("/api/v1/users") && method === "GET") {
        return Promise.resolve(jsonResponse({ users: [] }));
      }
      if (url.includes("/api/v1/clinic-profile") && method === "GET") {
        return Promise.resolve(jsonResponse(clinicProfile));
      }
      if (url.includes("/api/v1/rooms") && method === "GET") {
        return Promise.resolve(jsonResponse({ rooms: [clinicRoom] }));
      }
      if (url.includes("/api/v1/services") && method === "GET") {
        return Promise.resolve(jsonResponse({ services: [clinicService] }));
      }
      return Promise.resolve(jsonResponse(adminSession));
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
