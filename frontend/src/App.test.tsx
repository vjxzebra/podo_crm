import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { routeRegistry } from "./app/routes";
import {
  adminSession,
  anonymousProblem,
  forcedPasswordSession,
  clinicProfile,
  clinicRoom,
  clinicService,
  jsonResponse,
  receptionSession,
} from "./test/setup";

function renderApp(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("authenticated application shell", () => {
  it("renders the session-backed overview and responsive navigation", async () => {
    renderApp();

    expect(await screen.findByRole("heading", { name: "Добрий день" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Основна навігація" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Мобільна навігація" })).toBeInTheDocument();
    expect(screen.getAllByText("Адміністратор")).not.toHaveLength(0);
    expect(screen.queryByText(/реальну сесію та рольову навігацію/i)).not.toBeInTheDocument();
  });

  it("opens the role-safe mobile more sheet", async () => {
    renderApp();
    await screen.findByRole("heading", { name: "Добрий день" });

    fireEvent.click(screen.getByRole("button", { name: "Ще" }));

    expect(screen.getByRole("dialog", { name: "Тест Адміністратор" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Додаткові розділи" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Вийти із системи" })).toBeInTheDocument();
  });

  it.each([
    ["/previews/loading", "Готуємо робочий простір"],
    ["/previews/empty", "Тут ще немає даних"],
    ["/previews/error", "Не вдалося завантажити дані"],
    ["/previews/forbidden", "Цей розділ недоступний"],
    ["/missing-route", "Такої сторінки немає"],
  ])("renders the %s shell state", async (path, heading) => {
    renderApp(path);
    await screen.findByTestId("desktop-sidebar");
    expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
  });

  it("keeps authorization claims out of the route registry", () => {
    expect(routeRegistry).toHaveLength(12);
    for (const route of routeRegistry) {
      expect(route.requiresSession).toBe(true);
      expect(Object.keys(route)).not.toContain("roles");
      expect(Object.keys(route)).not.toContain("permissions");
      expect(Object.keys(route)).not.toContain("allowedRoles");
    }
  });
});

describe("session boundary and role-safe routes", () => {
  it("shows login, reports a generic error, and can establish a session", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(anonymousProblem, 401))
      .mockResolvedValueOnce(
        jsonResponse({
          ...anonymousProblem,
          code: "invalid_credentials",
          message: "Неправильний email або пароль.",
        }, 401),
      )
      .mockResolvedValueOnce(jsonResponse(adminSession));
    renderApp("/inventory");
    await screen.findByRole("heading", { name: "Вхід до кабінету" });

    fireEvent.change(screen.getByRole("textbox", { name: "Email" }), {
      target: { value: "admin@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: "Увійти" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Неправильний email або пароль.");

    fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "correct" } });
    fireEvent.click(screen.getByRole("button", { name: "Увійти" }));
    expect(await screen.findByRole("heading", { name: "Склад" })).toBeInTheDocument();
  });

  it("redirects a forbidden direct URL and hides unavailable navigation", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(receptionSession));
    renderApp("/inventory");

    expect(await screen.findByRole("heading", { name: "Добрий день" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Цей розділ недоступний");
    expect(screen.queryByRole("link", { name: "Склад" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Команда" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Фінанси" })).not.toHaveLength(0);
  });

  it("logs out and returns to the login screen", async () => {
    renderApp();
    await screen.findByRole("heading", { name: "Добрий день" });
    fireEvent.click(screen.getByRole("button", { name: /Тест Адміністратор/ }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Вийти" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Вхід до кабінету" })).toBeInTheDocument();
    });
  });

  it("blocks the workspace until a first-login password is created", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(forcedPasswordSession))
      .mockResolvedValueOnce(jsonResponse(adminSession));
    renderApp("/patients");

    expect(await screen.findByRole("heading", { name: "Створіть власний пароль" })).toBeInTheDocument();
    expect(screen.queryByTestId("desktop-sidebar")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Новий пароль"), {
      target: { value: "new correct horse battery staple" },
    });
    fireEvent.change(screen.getByLabelText("Повторіть новий пароль"), {
      target: { value: "new correct horse battery staple" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти й продовжити" }));

    expect(await screen.findByRole("heading", { name: "Добрий день" })).toBeInTheDocument();
  });

  it("submits an enumeration-safe forgot-password request", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(anonymousProblem, 401))
      .mockResolvedValueOnce(jsonResponse({
        message: "Якщо активний обліковий запис із таким email існує, запит уже доступний адміністратору.",
      }, 202));
    renderApp("/login");
    await screen.findByRole("heading", { name: "Вхід до кабінету" });

    fireEvent.click(screen.getByRole("button", { name: "Забули пароль?" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Робочий email" }), {
      target: { value: "unknown@example.test" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Створити запит" }));

    expect(await screen.findByRole("heading", { name: "Запит прийнято" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Якщо активний обліковий запис");
  });

  it("offers a reset request when the temporary password is expired", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({
        ...forcedPasswordSession,
        temporary_password_expired: true,
      }))
      .mockResolvedValueOnce(jsonResponse({
        message: "Якщо активний обліковий запис із таким email існує, запит уже доступний адміністратору.",
      }, 202));
    renderApp("/first-login");

    expect(await screen.findByRole("heading", { name: "Тимчасовий пароль більше не діє" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Створити запит на відновлення" }));
    expect(await screen.findByRole("status")).toHaveTextContent("запит уже доступний адміністратору");
  });

  it("changes the current user's password from the profile menu", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse({
        ...adminSession,
        user: { ...adminSession.user, display_name: "Тест Адміністратор" },
      }));
    renderApp();
    await screen.findByRole("heading", { name: "Добрий день" });
    fireEvent.click(screen.getByRole("button", { name: /Тест Адміністратор/ }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Змінити пароль" }));

    fireEvent.change(screen.getByLabelText("Поточний пароль"), { target: { value: "old password" } });
    fireEvent.change(screen.getByLabelText("Новий пароль"), { target: { value: "new correct horse battery staple" } });
    fireEvent.change(screen.getByLabelText("Повторіть новий пароль"), { target: { value: "new correct horse battery staple" } });
    fireEvent.click(screen.getByRole("button", { name: "Змінити пароль" }));

    expect(await screen.findByRole("heading", { name: "Пароль змінено" })).toBeInTheDocument();
  });

  it("lets an administrator resolve a reset request with a temporary password", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse({
        requests: [{
          id: 41,
          requested_at: "2026-07-21T09:30:00+03:00",
          user: {
            id: 7,
            email: "olena@example.test",
            display_name: "Олена Мельник",
            role: "podologist",
          },
        }],
      }))
      .mockResolvedValueOnce(jsonResponse({
        user_id: 7,
        must_change_password: true,
        temporary_password_expires_at: "2026-07-22T09:30:00+03:00",
      }));
    renderApp("/password-resets");

    expect(await screen.findByRole("heading", { name: "Запити на відновлення доступу" })).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: /Олена Мельник/ }));
    fireEvent.change(screen.getByLabelText("Тимчасовий пароль"), {
      target: { value: "temporary correct horse battery staple" },
    });
    fireEvent.change(screen.getByLabelText("Повторіть тимчасовий пароль"), {
      target: { value: "temporary correct horse battery staple" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Встановити пароль" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Усі попередні сесії відкликано");
    expect(screen.getByText("Нових запитів немає")).toBeInTheDocument();
  });

  it("lets an administrator create a team member with a role access summary", async () => {
    const fetchMock = vi.mocked(fetch);
    const adminUser = {
      id: 1,
      first_name: "Тест",
      last_name: "Адміністратор",
      display_name: "Тест Адміністратор",
      phone: "+380 50 100 20 30",
      email: "admin@example.test",
      role: "admin",
      is_active: true,
      must_change_password: false,
      temporary_password_expires_at: null,
      last_login: "2026-07-21T10:00:00+03:00",
    } as const;
    const createdUser = {
      id: 8,
      first_name: "Марія",
      last_name: "Бондар",
      display_name: "Марія Бондар",
      phone: "+380 93 555 66 77",
      email: "maria@example.test",
      role: "podologist",
      is_active: true,
      must_change_password: true,
      temporary_password_expires_at: "2026-07-22T10:00:00+03:00",
      last_login: null,
    } as const;
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse({ users: [adminUser] }))
      .mockResolvedValueOnce(jsonResponse(createdUser, 201));
    renderApp("/team");

    expect(await screen.findByRole("heading", { name: "Команда" })).toBeInTheDocument();
    expect(await screen.findAllByText("Тест Адміністратор")).not.toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Додати працівника" }));
    expect(screen.getByRole("heading", { name: "Новий працівник" })).toBeInTheDocument();
    expect(screen.getByText(/Власний календар, доступ до медичних даних/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Ім’я"), { target: { value: "Марія" } });
    fireEvent.change(screen.getByLabelText("Прізвище"), { target: { value: "Бондар" } });
    fireEvent.change(screen.getByLabelText("Робочий email"), { target: { value: "maria@example.test" } });
    fireEvent.change(screen.getByLabelText("Телефон"), { target: { value: "+380 93 555 66 77" } });
    fireEvent.change(screen.getByLabelText("Тимчасовий пароль"), { target: { value: "temporary correct horse battery staple" } });
    fireEvent.change(screen.getByLabelText("Повторіть пароль"), { target: { value: "temporary correct horse battery staple" } });
    fireEvent.click(screen.getByRole("button", { name: "Створити працівника" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Профіль Марія Бондар створено");
    expect(screen.getByText("maria@example.test")).toBeInTheDocument();
  });

  it("shows the server last-admin guard inside the edit dialog", async () => {
    const fetchMock = vi.mocked(fetch);
    const adminUser = {
      id: 1,
      first_name: "Тест",
      last_name: "Адміністратор",
      display_name: "Тест Адміністратор",
      phone: "",
      email: "admin@example.test",
      role: "admin",
      is_active: true,
      must_change_password: false,
      temporary_password_expires_at: null,
      last_login: null,
    } as const;
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse({ users: [adminUser] }))
      .mockResolvedValueOnce(jsonResponse({
        ...anonymousProblem,
        code: "last_admin_protected",
        message: "Не можна деактивувати або змінити роль останнього адміністратора.",
      }, 409));
    renderApp("/team");

    await screen.findByRole("heading", { name: "Команда" });
    fireEvent.click(await screen.findByRole("button", { name: "Редагувати Тест Адміністратор" }));
    fireEvent.change(screen.getByLabelText("Роль"), { target: { value: "reception" } });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти зміни" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("останнього адміністратора");
    expect(screen.getByRole("heading", { name: "Редагувати працівника" })).toBeInTheDocument();
  });

  it("loads and saves every required clinic profile field", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse(clinicProfile))
      .mockResolvedValueOnce(jsonResponse({ rooms: [clinicRoom] }))
      .mockResolvedValueOnce(jsonResponse({
        ...clinicProfile,
        name: "Podoria Подологія",
        phone: "+380 93 100 20 30",
        version: 2,
      }));
    renderApp("/settings");

    expect(await screen.findByRole("heading", { name: "Налаштування кабінету" })).toBeInTheDocument();
    expect(await screen.findByDisplayValue("Київ, вул. Прикладна, 10")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Філія/)).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Назва кабінету"), { target: { value: "Podoria Подологія" } });
    fireEvent.change(screen.getByLabelText("Телефон"), { target: { value: "+380 93 100 20 30" } });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти профіль" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Профіль кабінету збережено");
    expect(screen.getByDisplayValue("Podoria Подологія")).toBeInTheDocument();
  });

  it("creates a room from the empty state and preserves a duplicate-name conflict", async () => {
    const fetchMock = vi.mocked(fetch);
    const createdRoom = { ...clinicRoom, name: "Процедурна", version: 1 };
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse(clinicProfile))
      .mockResolvedValueOnce(jsonResponse({ rooms: [] }))
      .mockResolvedValueOnce(jsonResponse(createdRoom, 201))
      .mockResolvedValueOnce(jsonResponse({
        ...anonymousProblem,
        code: "room_name_already_exists",
        message: "Кімната з такою назвою вже існує.",
        fields: { name: ["Укажіть іншу назву кімнати."] },
      }, 409));
    renderApp("/settings");

    await screen.findByRole("heading", { name: "Налаштування кабінету" });
    fireEvent.click(await screen.findByRole("button", { name: /Кімнати/ }));
    expect(screen.getByRole("heading", { name: "Кімнат ще немає" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Створити кімнату" }));
    fireEvent.change(screen.getByLabelText("Назва кімнати"), { target: { value: "Процедурна" } });
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Створити кімнату" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Кімнату «Процедурна» створено");

    fireEvent.click(screen.getByRole("button", { name: "Додати кімнату" }));
    fireEvent.change(screen.getByLabelText("Назва кімнати"), { target: { value: "процедурна" } });
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Створити кімнату" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Кімната з такою назвою вже існує");
    expect(screen.getByRole("heading", { name: "Нова кімната" })).toBeInTheDocument();
    expect(screen.getByText("Укажіть іншу назву кімнати.")).toBeInTheDocument();
  });

  it("keeps a stale room conflict in the editor for a safe retry", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse(clinicProfile))
      .mockResolvedValueOnce(jsonResponse({ rooms: [clinicRoom] }))
      .mockResolvedValueOnce(jsonResponse({
        ...anonymousProblem,
        code: "stale_version",
        message: "Кімнату уже змінено в іншій сесії. Оновіть дані та повторіть дію.",
      }, 409));
    renderApp("/settings");

    await screen.findByRole("heading", { name: "Налаштування кабінету" });
    fireEvent.click(await screen.findByRole("button", { name: /Кімнати/ }));
    fireEvent.click(screen.getByRole("button", { name: "Налаштувати" }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Активна кімната/ }));
    fireEvent.click(screen.getByRole("button", { name: "Зберегти зміни" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("змінено в іншій сесії");
    expect(screen.getByRole("heading", { name: "Налаштувати кімнату" })).toBeInTheDocument();
  });

  it("searches the service catalog and creates a color-coded service in minor money units", async () => {
    const fetchMock = vi.mocked(fetch);
    const createdService = {
      ...clinicService,
      id: "8487d46c-e741-4a09-bd3f-123c14fb4e21",
      code: "NAIL-CARE",
      name: "Обробка нігтів",
      duration_minutes: 60,
      price_minor: 85050,
      color: "#7C3AED",
    } as const;
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse(clinicProfile))
      .mockResolvedValueOnce(jsonResponse({ rooms: [clinicRoom] }))
      .mockResolvedValueOnce(jsonResponse({ services: [clinicService] }))
      .mockResolvedValueOnce(jsonResponse(createdService, 201));
    renderApp("/settings");

    await screen.findByRole("heading", { name: "Налаштування кабінету" });
    fireEvent.click(screen.getByTestId("settings-services-tab"));
    expect(await screen.findByRole("heading", { name: "Послуги кабінету" })).toBeInTheDocument();
    expect(await screen.findByText("Первинна консультація")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Пошук"), { target: { value: "неіснуюча" } });
    expect(screen.getByRole("heading", { name: "Послуг не знайдено" })).toBeInTheDocument();
    fireEvent.click(screen.getByText("Скинути фільтри"));
    fireEvent.click(screen.getByRole("button", { name: "Додати послугу" }));
    fireEvent.change(screen.getByLabelText("Код послуги"), { target: { value: "nail-care" } });
    fireEvent.change(screen.getByLabelText("Назва"), { target: { value: "Обробка нігтів" } });
    fireEvent.change(screen.getByLabelText("Тривалість, хв"), { target: { value: "60" } });
    fireEvent.change(screen.getByLabelText("Ціна, ₴"), { target: { value: "850,50" } });
    fireEvent.click(screen.getByRole("radio", { name: "Фіолетовий" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Створити послугу" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Послугу «Обробка нігтів» створено");
    expect(screen.getByText("Обробка нігтів")).toBeInTheDocument();
    const createRequest = fetchMock.mock.calls.at(-1)?.[0];
    expect(createRequest).toBeInstanceOf(Request);
    expect(await (createRequest as Request).clone().json()).toMatchObject({
      code: "NAIL-CARE",
      duration_minutes: 60,
      price_minor: 85050,
      color: "#7C3AED",
    });
  });

  it("keeps a duplicate service-code conflict inside the editor", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse(clinicProfile))
      .mockResolvedValueOnce(jsonResponse({ rooms: [clinicRoom] }))
      .mockResolvedValueOnce(jsonResponse({ services: [clinicService] }))
      .mockResolvedValueOnce(jsonResponse({
        ...anonymousProblem,
        code: "service_code_already_exists",
        message: "Послуга з таким кодом уже існує.",
        fields: { code: ["Укажіть інший унікальний код послуги."] },
      }, 409));
    renderApp("/settings");

    await screen.findByRole("heading", { name: "Налаштування кабінету" });
    fireEvent.click(screen.getByTestId("settings-services-tab"));
    await screen.findByText("Первинна консультація");
    fireEvent.click(screen.getByRole("button", { name: "Редагувати Первинна консультація" }));
    fireEvent.click(screen.getByRole("button", { name: "Зберегти зміни" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Послуга з таким кодом уже існує");
    expect(screen.getByRole("heading", { name: "Редагувати послугу" })).toBeInTheDocument();
    expect(screen.getByText("Укажіть інший унікальний код послуги.")).toBeInTheDocument();
    expect(screen.getByDisplayValue("CONSULT")).toBeInTheDocument();
  });
});
