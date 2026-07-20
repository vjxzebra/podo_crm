import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { routeRegistry } from "./app/routes";
import {
  adminSession,
  anonymousProblem,
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
    expect(routeRegistry).toHaveLength(10);
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
});
