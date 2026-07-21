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

export const podologistSession = {
  user: {
    id: 4,
    email: "podologist@example.test",
    display_name: "Олена Подолог",
    role: "podologist",
  },
  route_ids: ["overview", "calendar", "patients", "work-items", "notifications"],
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

export const clinicStatuses = [
  ["NEW", "Новий", "#64748B", true, true, false],
  ["PENDING_CONFIRMATION", "Очікує підтвердження", "#F59E0B", true, true, false],
  ["CONFIRMED", "Підтверджено", "#2563EB", true, true, false],
  ["ARRIVED", "Пацієнт прийшов", "#7C3AED", true, true, true],
  ["IN_PROGRESS", "Прийом триває", "#0F766E", true, false, true],
  ["COMPLETED", "Завершено", "#16A34A", true, false, true],
  ["CANCELED", "Скасовано", "#DC2626", true, true, false],
  ["NO_SHOW", "Неявка", "#475569", true, true, false],
].map(([code, label, color, manualAdmin, manualReception, manualPodologist]) => ({
  code: code as string,
  label: label as string,
  color: color as string,
  manual_admin: manualAdmin as boolean,
  manual_reception: manualReception as boolean,
  manual_podologist: manualPodologist as boolean,
  version: 1,
  updated_at: "2026-07-21T12:00:00+03:00",
}));

export const clinicWorkdays = Array.from({ length: 7 }, (_, weekday) => ({
  weekday,
  is_working: weekday < 5,
  start_time: weekday < 5 ? "09:00" : null,
  end_time: weekday < 5 ? "18:00" : null,
  breaks: weekday < 5 ? [{
    id: `00000000-0000-4000-8000-00000000000${String(weekday)}`,
    start_time: "13:00",
    end_time: "14:00",
  }] : [],
  version: 1,
  updated_at: "2026-07-21T12:00:00+03:00",
}));

export const patientFixture = {
  id: "c49d72c2-689d-4f54-91df-9a63845a02e7",
  public_number: "P-C49D72C2689D",
  first_name: "Марія",
  last_name: "Бондар",
  display_name: "Марія Бондар",
  phone: "+380 67 123 45 67",
  birth_date: "1990-06-14",
  email: "maria@example.test",
  primary_podologist: null,
  appointment_summary: null,
  state_label: "Новий пацієнт",
  created_at: "2026-07-21T12:00:00+03:00",
} as const;

export const medicalPatientDetailFixture = {
  ...patientFixture,
  note: "Телефонувати після 16:00.",
  updated_at: "2026-07-21T12:00:00+03:00",
  age: 36,
  service_started_at: "2026-07-21T12:00:00+03:00",
  projection: "medical",
  upcoming_appointment: null,
  visit_history: [],
  medical_profile: {
    allergies: ["Латекс"],
    chronic_conditions: ["Цукровий діабет"],
    notes: "Контроль чутливості нігтьової пластини.",
    updated_at: "2026-07-21T12:00:00+03:00",
  },
  photo_archive: [],
} as const;

export const receptionPatientDetailFixture = {
  ...patientFixture,
  note: "Телефонувати після 16:00.",
  updated_at: "2026-07-21T12:00:00+03:00",
  age: 36,
  service_started_at: "2026-07-21T12:00:00+03:00",
  projection: "reception",
  upcoming_appointment: null,
  visit_history: [],
} as const;

export const workItemAssignees = [
  { id: 1, display_name: "Тест Адміністратор", role: "admin" },
  { id: 4, display_name: "Олена Подолог", role: "podologist" },
] as const;

export const workItemFixture = {
  id: "fe76f846-c0aa-4ee1-84e3-d9b91f0f3926",
  kind: "callback",
  kind_label: "Перетелефонувати",
  title: "Уточнити самопочуття після візиту",
  due_at: "2026-07-22T09:30:00+03:00",
  assignee: workItemAssignees[0],
  patient: {
    id: patientFixture.id,
    public_number: patientFixture.public_number,
    display_name: patientFixture.display_name,
    phone: patientFixture.phone,
  },
  comment: "Зателефонувати після 16:00.",
  is_important: true,
  is_completed: false,
  completed_at: null,
  completed_by: null,
  is_overdue: false,
  version: 1,
  created_by: workItemAssignees[0],
  created_at: "2026-07-21T12:00:00+03:00",
  updated_at: "2026-07-21T12:00:00+03:00",
} as const;

export const workItemListFixture = {
  work_items: [workItemFixture],
  summary: { open: 1, completed: 0, overdue: 0, important: 1 },
  assignees: workItemAssignees,
  effective_scope: "own",
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
      if (url.includes("/api/v1/appointment-status-configs") && method === "GET") {
        return Promise.resolve(jsonResponse({ statuses: clinicStatuses }));
      }
      if (url.includes("/api/v1/clinic-workdays") && method === "GET") {
        return Promise.resolve(jsonResponse({ timezone: "Europe/Kyiv", workdays: clinicWorkdays }));
      }
      if (url.includes("/api/v1/work-items") && method === "GET") {
        return Promise.resolve(jsonResponse(workItemListFixture));
      }
      if (/\/api\/v1\/patients\/[0-9a-f-]+$/.test(new URL(url).pathname) && method === "GET") {
        return Promise.resolve(jsonResponse(medicalPatientDetailFixture));
      }
      if (url.includes("/api/v1/patients") && method === "GET") {
        return Promise.resolve(jsonResponse({ patients: [patientFixture], next_cursor: null }));
      }
      return Promise.resolve(jsonResponse(adminSession));
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
