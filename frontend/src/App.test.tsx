import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { routeRegistry } from "./app/routes";
import {
  adminSession,
  anonymousProblem,
  forcedPasswordSession,
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
      expect(routeRegistry).toHaveLength(11);
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
});
