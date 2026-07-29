import axe from "axe-core";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { App } from "../App";
import {
  adminSession,
  bookingRequestFixture,
  clinicService,
  financeOperationsFixture,
  financePaidOperation,
  jsonResponse,
  visitFixture,
  visitPhotoAfterFixture,
  visitPhotoBeforeFixture,
} from "../test/setup";

describe("application shell accessibility", () => {
  it("has no detectable violations in the expired-session login state", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({
      code: "session_expired",
      message: "Сесію завершено. Увійдіть знову, щоб продовжити роботу.",
      fields: {},
      correlation_id: "tp-902-a11y",
    }, 401));
    const { container } = render(
      <MemoryRouter initialEntries={["/inventory"]}>
        <App />
      </MemoryRouter>,
    );
    await screen.findByRole("status");

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });

    expect(results.violations).toEqual([]);
  });

  it.each(["/", "/calendar", "/calendar?compose=appointment", "/patients", "/patients/c49d72c2-689d-4f54-91df-9a63845a02e7/overview", "/patients/c49d72c2-689d-4f54-91df-9a63845a02e7/visits", "/patients/c49d72c2-689d-4f54-91df-9a63845a02e7/photos", "/patients/c49d72c2-689d-4f54-91df-9a63845a02e7/recommendations", "/work-items", "/booking-requests", `/booking-requests?request=${bookingRequestFixture.id}`, "/notifications", "/audit", "/analytics", "/finance", "/inventory", `/visits/${visitFixture.id}`, "/team", "/settings", "/previews/empty", "/previews/error", "/previews/forbidden", "/missing-route"])(
    "has no detectable accessibility violations at %s",
    async (path) => {
      const { container } = render(
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>,
      );

      await screen.findByTestId("desktop-sidebar");
      if (path === "/team") {
        await screen.findByText("Працівників не знайдено");
      }
      if (path === "/patients") {
        await screen.findByText("Марія Бондар");
      }
      if (path.startsWith("/patients/")) {
        await screen.findByRole("heading", { name: "Марія Бондар", level: 1 });
      }
      if (path.endsWith("/visits")) {
        await screen.findByText("Шкіра спокійна, загоєння без ускладнень.");
      }
      if (path.endsWith("/photos")) {
        await screen.findByRole("button", { name: "Відкрити «До процедури», фото 1 у слайдері" });
      }
      if (path.endsWith("/recommendations")) {
        await screen.findByText("Обробляти ділянку двічі на день та уникати тиску.");
      }
      if (path === "/work-items") {
        await screen.findByText("Уточнити самопочуття після візиту");
      }
      if (path.startsWith("/booking-requests")) {
        await screen.findAllByText("Ірина Шевченко");
      }
      if (path.includes("?request=")) {
        await screen.findByRole("dialog", { name: bookingRequestFixture.public_number });
      }
      if (path === "/notifications") {
        await screen.findByRole("heading", { name: "Сповіщень ще немає" });
      }
      if (path === "/inventory") {
        await screen.findByText("Каполін, 1 см");
      }
      if (path === "/finance") {
        await screen.findByRole("heading", { name: "Поточна касова зміна" });
      }
      if (path === "/analytics") {
        await screen.findByText("Чистий виторг");
      }
      if (path.startsWith("/visits/")) {
        await screen.findByRole("heading", { name: visitFixture.patient.display_name, level: 1 });
      }
      if (path.startsWith("/calendar")) {
        await screen.findByRole("heading", { name: "Розклад клініки" });
      }
      if (path === "/calendar?compose=appointment") {
        await screen.findByRole("dialog", { name: "Новий запис" });
      }
      if (path === "/settings") {
        await screen.findByRole("heading", { name: "Профіль кабінету" });
      }

      const results = await axe.run(container, {
        rules: {
          "color-contrast": { enabled: false },
        },
      });

      expect(results.violations).toEqual([]);
    },
  );

  it("has no detectable violations in grouped global-search results", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );
    await screen.findByRole("heading", { name: "Добрий день" });
    fireEvent.click(screen.getByRole("button", { name: "Відкрити глобальний пошук" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Пошуковий запит" }), { target: { value: "Марія" } });
    await screen.findAllByRole("option");

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(results.violations).toEqual([]);
  });

  it("has no detectable violations in the open calendar date picker", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/calendar"]}>
        <App />
      </MemoryRouter>,
    );
    await screen.findByRole("heading", { name: "Розклад клініки" });
    fireEvent.click(screen.getByRole("button", { name: /Обрати дату:/ }));
    await screen.findByRole("dialog", { name: "Вибір дати календаря" });

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });

    expect(results.violations).toEqual([]);
  });

  it("has no detectable violations in the open cash-shift confirmation", async () => {
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (url.pathname === "/api/v1/cash-shifts/current") return Promise.resolve(jsonResponse({ shift: null }));
      if (url.pathname === "/api/v1/finance/operations") return Promise.resolve(jsonResponse(financeOperationsFixture));
      return Promise.resolve(jsonResponse({ code: "not_found", message: "Not found", fields: {}, correlation_id: "a11y" }, 404));
    });
    const { container } = render(
      <MemoryRouter initialEntries={["/finance"]}>
        <App />
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByRole("button", { name: "Відкрити касову зміну" }));
    await screen.findByRole("dialog", { name: "Відкрити касову зміну?" });

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });

    expect(results.violations).toEqual([]);
  });

  it("has no detectable violations in the finance operation detail", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/finance"]}>
        <App />
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByRole("button", { name: `Відкрити деталі ${financePaidOperation.payment.public_number} — ${financePaidOperation.patient.display_name}` }));
    await screen.findByRole("dialog", { name: financePaidOperation.payment.public_number });

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });

    expect(results.violations).toEqual([]);
  });

  it("has no detectable violations in the full-payment dialog", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/finance"]}>
        <App />
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByRole("button", { name: /^Оплатити / }));
    await screen.findByRole("dialog", { name: "Провести оплату прийому" });

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });

    expect(results.violations).toEqual([]);
  });

  it("has no detectable violations in the full-refund picker and destructive review", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/finance"]}>
        <App />
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByRole("button", { name: "Повернення" }));
    const dialog = await screen.findByRole("dialog", { name: "Оформити повернення" });
    fireEvent.click(await within(dialog).findByRole("option", { name: /Наталія Коваль/ }));
    fireEvent.change(within(dialog).getByLabelText("Причина повернення"), { target: { value: "Погоджене повернення" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Перейти до підтвердження" }));
    await within(dialog).findByRole("heading", { name: "Підтвердити повне повернення?" });

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });

    expect(results.violations).toEqual([]);
  });

  it.each([
    ["+ Внесення", "Внести готівку"],
    ["− Вилучення", "Вилучити готівку"],
  ])("has no detectable violations in the %s cash-movement form", async (triggerName, dialogName) => {
    const { container } = render(
      <MemoryRouter initialEntries={["/finance"]}>
        <App />
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByRole("button", { name: triggerName }));
    await screen.findByRole("dialog", { name: dialogName });

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });

    expect(results.violations).toEqual([]);
  });

  it("has no detectable violations in the patient photo archive carousel", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/patients/c49d72c2-689d-4f54-91df-9a63845a02e7/photos"]}>
        <App />
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByRole("button", { name: "Відкрити «До процедури», фото 1 у слайдері" }));
    await screen.findByRole("dialog", { name: "Первинна консультація" });

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });

    expect(results.violations).toEqual([]);
  });

  it("has no detectable violations in the recommendation editor", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/patients/c49d72c2-689d-4f54-91df-9a63845a02e7/recommendations"]}>
        <App />
      </MemoryRouter>,
    );
    await screen.findByText("Обробляти ділянку двічі на день та уникати тиску.");
    fireEvent.click(screen.getByRole("button", { name: "Додати рекомендацію" }));
    await screen.findByRole("dialog", { name: "Нова рекомендація" });

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });

    expect(results.violations).toEqual([]);
  });

  it("has no detectable violations in the appointment detail dialog", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/calendar"]}>
        <App />
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByRole("button", { name: /Марія Бондар, Підтверджено/ }));
    await screen.findByRole("dialog", { name: "Деталі запису" });

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });

    expect(results.violations).toEqual([]);
  });

  it("has no detectable violations in the inventory receipt dialog", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/inventory"]}>
        <App />
      </MemoryRouter>,
    );
    await screen.findByText("Каполін, 1 см");
    fireEvent.click(screen.getByRole("button", { name: "Нове надходження" }));
    await screen.findByRole("dialog", { name: "Нове надходження" });

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });

    expect(results.violations).toEqual([]);
  });

  it("has no detectable violations in the manual write-off dialog", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/inventory"]}>
        <App />
      </MemoryRouter>,
    );
    fireEvent.click(await screen.findByRole("button", { name: "Відкрити Каполін, 1 см" }));
    fireEvent.click(await screen.findByRole("button", { name: "Ручне списання" }));
    await screen.findByRole("dialog", { name: "Ручне списання" });

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });

    expect(results.violations).toEqual([]);
  });

  it("has no detectable violations in the physical stocktake dialog", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/inventory"]}>
        <App />
      </MemoryRouter>,
    );
    await screen.findByText("Каполін, 1 см");
    fireEvent.click(screen.getByRole("button", { name: "Інвентаризація" }));
    await screen.findByRole("dialog", { name: "Нова інвентаризація" });
    expect(await screen.findAllByLabelText(/Фактичний залишок, Каполін/)).toHaveLength(2);

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });

    expect(results.violations).toEqual([]);
  });

  it("has no detectable violations in the movement journal and operation detail", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/inventory"]}>
        <App />
      </MemoryRouter>,
    );
    await screen.findByText("Каполін, 1 см");
    fireEvent.click(screen.getByRole("button", { name: "Журнал рухів" }));
    fireEvent.click(await screen.findByRole("button", { name: /Відкрити операцію INV-/ }));
    await screen.findByRole("dialog", { name: /INV-/ });

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });

    expect(results.violations).toEqual([]);
  });

  it("has no detectable violations in the unsaved visit warning", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={[`/visits/${visitFixture.id}`]}>
        <App />
      </MemoryRouter>,
    );
    await screen.findByRole("heading", { name: visitFixture.patient.display_name, level: 1 });
    fireEvent.change(screen.getByLabelText("Об’єктивний огляд"), {
      target: { value: "Незбережений огляд" },
    });
    fireEvent.click(screen.getByRole("button", { name: "До календаря" }));
    await screen.findByRole("dialog", { name: "Вийти без останніх змін?" });

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });

    expect(results.violations).toEqual([]);
  });

  it("has no detectable violations in the visit material picker", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={[`/visits/${visitFixture.id}`]}>
        <App />
      </MemoryRouter>,
    );
    await screen.findByRole("heading", { name: visitFixture.patient.display_name, level: 1 });
    fireEvent.click(screen.getByRole("button", { name: "Далі: послуги й матеріали" }));
    fireEvent.click(screen.getByRole("button", { name: "Додати матеріал" }));
    await screen.findByRole("dialog", { name: "Додати матеріал" });

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });

    expect(results.violations).toEqual([]);
  });

  it("has no detectable violations in the private visit photo step", async () => {
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input.toString();
      const method = input instanceof Request ? input.method : (init?.method ?? "GET");
      if (url.includes("/api/v1/session")) return Promise.resolve(jsonResponse(adminSession));
      if (url.includes(`/api/v1/visits/${visitFixture.id}`) && method === "GET") {
        return Promise.resolve(jsonResponse({
          ...visitFixture,
          photos: [visitPhotoBeforeFixture, visitPhotoAfterFixture],
        }));
      }
      if (url.includes("/api/v1/services") && method === "GET") {
        return Promise.resolve(jsonResponse({ services: [clinicService] }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    const { container } = render(
      <MemoryRouter initialEntries={[`/visits/${visitFixture.id}`]}>
        <App />
      </MemoryRouter>,
    );
    await screen.findByRole("heading", { name: visitFixture.patient.display_name, level: 1 });
    fireEvent.click(screen.getByRole("button", { name: "Далі: послуги й матеріали" }));
    fireEvent.click(screen.getByRole("button", { name: "Далі: фото" }));
    await screen.findByRole("heading", { name: "Фото до та після процедури", level: 2 });
    fireEvent.click(screen.getByRole("button", {
      name: `Відкрити до процедури 1: ${visitPhotoBeforeFixture.original_name} у слайдері`,
    }));
    await screen.findByRole("dialog", { name: "Перегляд фото" });

    const results = await axe.run(container, {
      rules: { region: { enabled: false } },
    });

    expect(results.violations).toEqual([]);
  });

  it("has no detectable violations in the atomic visit finish summary", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={[`/visits/${visitFixture.id}`]}>
        <App />
      </MemoryRouter>,
    );
    await screen.findByRole("heading", { name: visitFixture.patient.display_name, level: 1 });
    fireEvent.click(screen.getByRole("button", { name: "Далі: послуги й матеріали" }));
    fireEvent.click(screen.getByRole("button", { name: "Далі: фото" }));
    fireEvent.click(screen.getByRole("button", { name: "Далі: завершення" }));
    await screen.findByRole("heading", { name: "Перевірка та завершення", level: 2 });

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });

    expect(results.violations).toEqual([]);
  });
});
