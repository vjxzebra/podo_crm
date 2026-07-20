import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { App } from "./App";
import { AuthBoundary } from "./app/AuthBoundary";
import { routeRegistry } from "./app/routes";

function renderApp(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("responsive application shell", () => {
  it("renders the overview and all responsive navigation contracts", () => {
    renderApp();

    expect(screen.getByRole("heading", { name: "Добрий день" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Основна навігація" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Мобільна навігація" })).toBeInTheDocument();
    expect(screen.getByText(/реальну сесію та рольову навігацію/i)).toBeInTheDocument();
  });

  it("opens the touch-first mobile more sheet", () => {
    renderApp();

    fireEvent.click(screen.getByRole("button", { name: "Ще" }));

    expect(screen.getByRole("dialog", { name: "Робочий простір" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Додаткові розділи" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Глобальний пошук" })).toBeInTheDocument();
  });

  it.each([
    ["/previews/loading", "Готуємо робочий простір"],
    ["/previews/empty", "Тут ще немає даних"],
    ["/previews/error", "Не вдалося завантажити дані"],
    ["/previews/forbidden", "Цей розділ недоступний"],
    ["/missing-route", "Такої сторінки немає"],
  ])("renders the %s shell state", (path, heading) => {
    renderApp(path);

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

describe("auth boundary interface", () => {
  it("renders checking and forbidden states without role decisions", () => {
    const { rerender } = render(
      <MemoryRouter>
        <AuthBoundary state={{ status: "checking" }}>
          <p>Protected shell</p>
        </AuthBoundary>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Готуємо робочий простір" })).toBeInTheDocument();

    rerender(
      <MemoryRouter>
        <AuthBoundary state={{ status: "forbidden" }}>
          <p>Protected shell</p>
        </AuthBoundary>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Цей розділ недоступний" })).toBeInTheDocument();
    expect(screen.queryByText("Protected shell")).not.toBeInTheDocument();
  });
});
