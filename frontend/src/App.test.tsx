import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { routeRegistry } from "./app/routes";
import {
  adminSession,
  arrivedAppointmentDetailFixture,
  appointmentDetailFixture,
  appointmentFixture,
  availabilityFixture,
  anonymousProblem,
  cashShiftFixture,
  financeOperationsFixture,
  financePaidOperation,
  forcedPasswordSession,
  clinicProfile,
  clinicRoom,
  clinicService,
  clinicStatuses,
  clinicWorkdays,
  healthyInventoryMaterial,
  inactiveInventorySupplier,
  inventoryLots,
  inventoryMaterial,
  inventorySupplier,
  inventoryReceiptOperation,
  inventoryWriteoffOperation,
  inventoryMovementJournal,
  calendarFixture,
  jsonResponse,
  medicalPatientDetailFixture,
  overviewFixture,
  patientFixture,
  podologistSession,
  receptionSession,
  receptionPatientDetailFixture,
  stocktakeDraft,
  stocktakePosted,
  stocktakePreview,
  stocktakeOperationDetail,
  workItemFixture,
  workItemListFixture,
  visitFixture,
  visitPhotoAfterFixture,
  visitPhotoBeforeFixture,
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

    const moreTrigger = screen.getByRole("button", { name: "Ще" });
    fireEvent.click(moreTrigger);

    expect(screen.getByRole("dialog", { name: "Тест Адміністратор" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Додаткові розділи" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Вийти із системи" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Закрити додаткове меню" })).toHaveFocus();
    });
    expect(document.body).toHaveStyle({ overflow: "hidden" });

    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Тест Адміністратор" })).not.toBeInTheDocument();
      expect(moreTrigger).toHaveFocus();
    });
    expect(document.body.style.overflow).toBe("");
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
    expect(routeRegistry).toHaveLength(14);
    for (const route of routeRegistry) {
      expect(route.requiresSession).toBe(true);
      expect(Object.keys(route)).not.toContain("roles");
      expect(Object.keys(route)).not.toContain("permissions");
      expect(Object.keys(route)).not.toContain("allowedRoles");
    }
  });
});

describe("TP-801 global search and canonical deep links", () => {
  it("opens with Ctrl/Cmd+K, traps focus, and restores focus on Escape", async () => {
    renderApp();
    await screen.findByRole("heading", { name: "Добрий день" });
    const trigger = screen.getByRole("button", { name: "Відкрити глобальний пошук" });
    trigger.focus();

    fireEvent.keyDown(document, { key: "k", code: "KeyK", ctrlKey: true });
    const dialog = await screen.findByRole("dialog", { name: "Глобальний пошук" });
    expect(within(dialog).getByRole("combobox", { name: "Пошуковий запит" })).toHaveFocus();
    expect(document.body).toHaveStyle({ overflow: "hidden" });

    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => { expect(screen.queryByRole("dialog", { name: "Глобальний пошук" })).not.toBeInTheDocument(); });
    expect(trigger).toHaveFocus();
    expect(document.body.style.overflow).toBe("");
  });

  it("opens from mobile More and returns focus to that navigation trigger", async () => {
    renderApp();
    await screen.findByRole("heading", { name: "Добрий день" });
    const more = screen.getByRole("button", { name: "Ще" });
    fireEvent.click(more);
    fireEvent.click(screen.getByRole("button", { name: "Глобальний пошук" }));

    expect(await screen.findByRole("dialog", { name: "Глобальний пошук" })).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Тест Адміністратор" })).not.toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => { expect(more).toHaveFocus(); });
  });

  it("navigates a server-returned appointment result to an exact scoped detail fetch", async () => {
    renderApp();
    await screen.findByRole("heading", { name: "Добрий день" });
    fireEvent.click(screen.getByRole("button", { name: "Відкрити глобальний пошук" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Пошуковий запит" }), { target: { value: "Марія" } });
    fireEvent.click(await screen.findByRole("option", { name: /Первинна консультація/ }));

    const detail = await screen.findByRole("dialog", { name: "Деталі запису" });
    expect(await within(detail).findByText(appointmentDetailFixture.public_number)).toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.some(([input]) => input instanceof Request
      && input.url.endsWith(`/api/v1/appointments/${appointmentDetailFixture.id}`))).toBe(true);
  });

  it("opens and cleans the patient create query action", async () => {
    renderApp("/patients?compose=patient");
    const dialog = await screen.findByRole("dialog", { name: "Новий пацієнт" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Скасувати" }));
    expect(screen.queryByRole("dialog", { name: "Новий пацієнт" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Каталог пацієнтів" })).toBeInTheDocument();
  });

  it("resolves exact finance and material query deep links independently of list pagination", async () => {
    const finance = renderApp(`/finance?operation=PAYMENT:${financePaidOperation.id}`);
    expect(await screen.findByRole("dialog", { name: financePaidOperation.payment.public_number })).toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.some(([input]) => input instanceof Request
      && input.url.endsWith(`/api/v1/finance/operations/PAYMENT/${financePaidOperation.id}`))).toBe(true);
    finance.unmount();

    renderApp(`/inventory?material=${inventoryMaterial.id}`);
    expect(await screen.findByRole("dialog", { name: inventoryMaterial.name })).toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.some(([input]) => input instanceof Request
      && input.url.endsWith(`/api/v1/inventory/materials/${inventoryMaterial.id}`))).toBe(true);
  });
});

describe("TP-501 inventory material and lot catalog", () => {
  it("filters the admin catalog and opens FEFO lot details", async () => {
    renderApp("/inventory");

    expect(await screen.findByRole("heading", { name: "Склад і матеріали" })).toBeInTheDocument();
    expect(await screen.findByText("Каполін, 1 см")).toBeInTheDocument();
    expect(screen.getByText("Рукавички нітрилові M")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Категорія"), { target: { value: "Захист" } });
    expect(screen.queryByText("Каполін, 1 см")).not.toBeInTheDocument();
    expect(screen.getByText("Рукавички нітрилові M")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Скинути фільтри" }));
    fireEvent.click(await screen.findByRole("button", { name: "Відкрити Каполін, 1 см" }));

    const dialog = await screen.findByRole("dialog", { name: "Каполін, 1 см" });
    expect(within(dialog).getByText("Партії та терміни")).toBeInTheDocument();
    expect(within(dialog).getByText("№N-038 / 03")).toBeInTheDocument();
    expect(within(dialog).getByText("FEFO · першою")).toBeInTheDocument();
    expect(within(dialog).getAllByText("12 шт.")).toHaveLength(2);
  });

  it("creates a normalized material card and keeps the typed request explicit", async () => {
    const fetchMock = vi.mocked(fetch);
    const created = {
      ...healthyInventoryMaterial,
      id: "c8aeb535-e61f-4dd7-bdac-9822b2626532",
      sku: "ANT-014",
      name: "Octenisept, 250 мл",
      category: "Антисептики",
      unit: "мл",
      minimum_quantity: "1000.000",
      total_quantity: "0.000",
      available_quantity: "0.000",
      nearest_expiry: null,
      stock_status: "out_of_stock",
      lots_count: 0,
    } as const;
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse({ materials: [inventoryMaterial, healthyInventoryMaterial] }))
      .mockResolvedValueOnce(jsonResponse(created, 201));
    renderApp("/inventory");

    await screen.findByText("Каполін, 1 см");
    fireEvent.click(screen.getByRole("button", { name: "Додати матеріал" }));
    const editor = await screen.findByRole("dialog", { name: "Новий матеріал" });
    fireEvent.change(within(editor).getByLabelText("Артикул"), { target: { value: "ANT-014" } });
    fireEvent.change(within(editor).getByLabelText("Назва"), { target: { value: "Octenisept, 250 мл" } });
    fireEvent.change(within(editor).getByLabelText("Категорія"), { target: { value: "Антисептики" } });
    fireEvent.change(within(editor).getByLabelText("Одиниця виміру"), { target: { value: "мл" } });
    fireEvent.change(within(editor).getByLabelText("Мінімальний залишок"), { target: { value: "1000" } });
    fireEvent.click(within(editor).getByRole("button", { name: "Створити матеріал" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Матеріал додано до каталогу");
    expect(screen.getByText("Octenisept, 250 мл")).toBeInTheDocument();
    const request = fetchMock.mock.calls.find(([input]) => input instanceof Request && input.method === "POST")?.[0];
    expect(await (request as Request).clone().json()).toEqual({
      sku: "ANT-014",
      name: "Octenisept, 250 мл",
      category: "Антисептики",
      unit: "мл",
      minimum_quantity: "1000",
      is_active: true,
    });
  });

  it("locks the unit field after the first lot while keeping other settings editable", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse({ materials: [inventoryMaterial] }))
      .mockResolvedValueOnce(jsonResponse(inventoryMaterial))
      .mockResolvedValueOnce(jsonResponse({ lots: inventoryLots }));
    renderApp("/inventory");

    fireEvent.click(await screen.findByRole("button", { name: "Відкрити Каполін, 1 см" }));
    fireEvent.click(await screen.findByRole("button", { name: "Редагувати картку" }));

    const editor = await screen.findByRole("dialog", { name: "Редагувати матеріал" });
    expect(within(editor).getByLabelText(/Одиниця виміру/)).toBeDisabled();
    expect(within(editor).getByText("Захищено після першої партії.")).toBeInTheDocument();
    expect(within(editor).getByLabelText("Мінімальний залишок")).toBeEnabled();
  });

  it("protects unsaved material changes before closing the editor", async () => {
    renderApp("/inventory");

    await screen.findByText("Каполін, 1 см");
    fireEvent.click(screen.getByRole("button", { name: "Додати матеріал" }));
    const editor = await screen.findByRole("dialog", { name: "Новий матеріал" });
    fireEvent.change(within(editor).getByLabelText("Назва"), { target: { value: "Новий матеріал" } });
    fireEvent.click(within(editor).getByRole("button", { name: "Скасувати" }));

    expect(within(editor).getByRole("alert")).toHaveTextContent("Є незбережені зміни");
    fireEvent.click(within(editor).getByRole("button", { name: "Продовжити" }));
    expect(within(editor).queryByRole("alert")).not.toBeInTheDocument();
    fireEvent.click(within(editor).getByRole("button", { name: "Скасувати" }));
    fireEvent.click(within(editor).getByRole("button", { name: "Відкинути" }));
    expect(screen.queryByRole("dialog", { name: "Новий матеріал" })).not.toBeInTheDocument();
  });
});

describe("TP-1001 supplier directory", () => {
  it("filters suppliers and protects unsaved edits", async () => {
    renderApp("/inventory");

    await screen.findByText("Каполін, 1 см");
    fireEvent.click(screen.getByRole("button", { name: "Постачальники" }));
    expect(await screen.findByRole("heading", { name: "Постачальники" })).toBeInTheDocument();
    expect(screen.getByText(inventorySupplier.name)).toBeInTheDocument();
    expect(screen.getByText(inactiveInventorySupplier.name)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Статус"), { target: { value: "active" } });
    expect(screen.getByText(inventorySupplier.name)).toBeInTheDocument();
    expect(screen.queryByText(inactiveInventorySupplier.name)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: `Редагувати ${inventorySupplier.name}` }));

    const editor = await screen.findByRole("dialog", { name: "Редагувати постачальника" });
    fireEvent.change(within(editor).getByLabelText("Телефон"), { target: { value: "+380 50 000 00 00" } });
    fireEvent.click(within(editor).getByRole("button", { name: "Скасувати" }));
    expect(within(editor).getByRole("alert")).toHaveTextContent("Є незбережені зміни");
    fireEvent.click(within(editor).getByRole("button", { name: "Відкинути" }));
    expect(screen.queryByRole("dialog", { name: "Редагувати постачальника" })).not.toBeInTheDocument();
  });

  it("creates a typed supplier record", async () => {
    const fetchMock = vi.mocked(fetch);
    const created = {
      ...inventorySupplier,
      id: "2ecab7cc-2762-4c82-87ac-09094335133e",
      name: "Foot Care Supply",
      contact_name: "Ірина Савчук",
      email: "supply@example.test",
      phone: "+380 50 555 55 55",
      address: "Львів",
      note: "",
      lots_count: 0,
    } as const;
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse({ materials: [inventoryMaterial] }))
      .mockResolvedValueOnce(jsonResponse({ suppliers: [] }))
      .mockResolvedValueOnce(jsonResponse(created, 201));
    renderApp("/inventory");

    await screen.findByText("Каполін, 1 см");
    fireEvent.click(screen.getByRole("button", { name: "Постачальники" }));
    expect(await screen.findByText("Постачальників ще немає")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Створити постачальника" }));
    const editor = await screen.findByRole("dialog", { name: "Новий постачальник" });
    fireEvent.change(within(editor).getByLabelText("Назва"), { target: { value: created.name } });
    fireEvent.change(within(editor).getByLabelText("Контактна особа"), { target: { value: created.contact_name } });
    fireEvent.change(within(editor).getByLabelText("Телефон"), { target: { value: created.phone } });
    fireEvent.change(within(editor).getByLabelText("Email"), { target: { value: created.email } });
    fireEvent.change(within(editor).getByLabelText("Адреса"), { target: { value: created.address } });
    fireEvent.click(within(editor).getByRole("button", { name: "Створити постачальника" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Постачальника додано");
    expect(screen.getByText(created.name)).toBeInTheDocument();
    const request = fetchMock.mock.calls.find(([input]) => input instanceof Request
      && input.method === "POST"
      && input.url.endsWith("/api/v1/inventory/suppliers"))?.[0] as Request;
    expect(await request.clone().json()).toEqual({
      name: created.name,
      contact_name: created.contact_name,
      phone: created.phone,
      email: created.email,
      address: created.address,
      note: "",
      is_active: true,
    });
  });
});

describe("TP-502 receipt and locked manual write-off", () => {
  it("posts a typed multi-line receipt with one stable idempotency key", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse({ materials: [inventoryMaterial, healthyInventoryMaterial] }))
      .mockResolvedValueOnce(jsonResponse({ suppliers: [inventorySupplier] }))
      .mockResolvedValueOnce(jsonResponse(inventoryReceiptOperation, 201))
      .mockResolvedValueOnce(jsonResponse({ materials: [inventoryMaterial, healthyInventoryMaterial] }));
    renderApp("/inventory");

    await screen.findByText("Каполін, 1 см");
    fireEvent.click(screen.getByRole("button", { name: "Нове надходження" }));
    const dialog = await screen.findByRole("dialog", { name: "Нове надходження" });
    fireEvent.change(within(dialog).getByLabelText("Пошук матеріалу 1"), { target: { value: "кап" } });
    fireEvent.change(within(dialog).getByLabelText("Матеріал 1"), { target: { value: inventoryMaterial.id } });
    fireEvent.change(within(dialog).getByLabelText("Номер партії 1"), { target: { value: "N-050" } });
    fireEvent.change(within(dialog).getByLabelText("Кількість 1"), { target: { value: "15" } });
    fireEvent.change(within(dialog).getByLabelText("Ціна 1"), { target: { value: "3.25" } });
    fireEvent.change(within(dialog).getByLabelText("Постачальник 1"), { target: { value: inventorySupplier.id } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Додати рядок" }));
    fireEvent.change(within(dialog).getByLabelText("Матеріал 2"), { target: { value: healthyInventoryMaterial.id } });
    fireEvent.change(within(dialog).getByLabelText("Номер партії 2"), { target: { value: "G-118" } });
    fireEvent.change(within(dialog).getByLabelText("Кількість 2"), { target: { value: "40" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Провести надходження" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Надходження проведено");
    expect(screen.getByRole("status")).toHaveTextContent(inventoryReceiptOperation.public_number);
    const request = fetchMock.mock.calls.find(([input]) => input instanceof Request
      && input.method === "POST"
      && input.url.endsWith("/api/v1/inventory/receipts"))?.[0] as Request;
    expect(request.headers.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
    expect(await request.clone().json()).toMatchObject({
      comment: "",
      lines: [
        {
          material_id: inventoryMaterial.id,
          lot_number: "N-050",
          quantity: "15",
          purchase_price_minor: 325,
          supplier_id: inventorySupplier.id,
          supplier_name: "",
          allow_existing_lot: false,
        },
        {
          material_id: healthyInventoryMaterial.id,
          lot_number: "G-118",
          quantity: "40",
          purchase_price_minor: null,
          allow_existing_lot: false,
        },
      ],
    });
  });

  it("preserves receipt fields and the idempotency key through duplicate-lot recovery", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse({ materials: [inventoryMaterial] }))
      .mockResolvedValueOnce(jsonResponse({ suppliers: [inventorySupplier] }))
      .mockResolvedValueOnce(jsonResponse({
        code: "material_lot_already_exists",
        message: "Партія з таким номером уже існує для матеріалу.",
        fields: { "lines.0.lot_number": ["Підтвердьте поповнення існуючої партії."] },
        correlation_id: "inventory-test",
      }, 409))
      .mockResolvedValueOnce(jsonResponse({ ...inventoryReceiptOperation, replayed: false }, 201))
      .mockResolvedValueOnce(jsonResponse({ materials: [inventoryMaterial] }));
    renderApp("/inventory");

    await screen.findByText("Каполін, 1 см");
    fireEvent.click(screen.getByRole("button", { name: "Нове надходження" }));
    const dialog = await screen.findByRole("dialog", { name: "Нове надходження" });
    fireEvent.change(within(dialog).getByLabelText("Матеріал 1"), { target: { value: inventoryMaterial.id } });
    fireEvent.change(within(dialog).getByLabelText("Номер партії 1"), { target: { value: inventoryLots[0].lot_number } });
    fireEvent.change(within(dialog).getByLabelText("Строк придатності 1"), { target: { value: inventoryLots[0].expires_on } });
    fireEvent.change(within(dialog).getByLabelText("Кількість 1"), { target: { value: "3" } });
    fireEvent.change(within(dialog).getByLabelText("Ціна 1"), { target: { value: "3.20" } });
    fireEvent.change(within(dialog).getByLabelText("Постачальник 1"), { target: { value: inventorySupplier.id } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Провести надходження" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Партія з таким номером уже існує");
    fireEvent.click(within(dialog).getByRole("checkbox"));
    fireEvent.click(within(dialog).getByRole("button", { name: "Провести надходження" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Надходження проведено");
    const receiptRequests = fetchMock.mock.calls
      .map(([input]) => input)
      .filter((input): input is Request => input instanceof Request
        && input.method === "POST"
        && input.url.endsWith("/api/v1/inventory/receipts"));
    expect(receiptRequests).toHaveLength(2);
    const firstRequest = receiptRequests[0];
    const secondRequest = receiptRequests[1];
    if (firstRequest === undefined || secondRequest === undefined) {
      throw new Error("Expected two receipt requests.");
    }
    expect(firstRequest.headers.get("Idempotency-Key")).toBe(
      secondRequest.headers.get("Idempotency-Key"),
    );
    expect(await secondRequest.clone().json()).toMatchObject({
      lines: [{ allow_existing_lot: true }],
    });
  });

  it("posts a manual write-off from material details with explicit lot and reason", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse({ materials: [inventoryMaterial] }))
      .mockResolvedValueOnce(jsonResponse(inventoryMaterial))
      .mockResolvedValueOnce(jsonResponse({ lots: inventoryLots }))
      .mockResolvedValueOnce(jsonResponse(inventoryWriteoffOperation, 201))
      .mockResolvedValueOnce(jsonResponse({ materials: [inventoryMaterial] }));
    renderApp("/inventory");

    fireEvent.click(await screen.findByRole("button", { name: "Відкрити Каполін, 1 см" }));
    fireEvent.click(await screen.findByRole("button", { name: "Ручне списання" }));
    const dialog = await screen.findByRole("dialog", { name: "Ручне списання" });
    expect(within(dialog).getByText("4 шт.")).toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText("Кількість списання"), { target: { value: "2" } });
    fireEvent.change(within(dialog).getByLabelText("Причина"), { target: { value: "Пошкодження" } });
    fireEvent.change(within(dialog).getByLabelText("Коментар"), { target: { value: "Пошкоджене пакування" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Підтвердити списання" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Списання проведено");
    const request = fetchMock.mock.calls.find(([input]) => input instanceof Request
      && input.method === "POST"
      && input.url.endsWith("/api/v1/inventory/write-offs"))?.[0] as Request;
    expect(request.headers.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
    expect(await request.clone().json()).toEqual({
      reason: "Пошкодження",
      comment: "Пошкоджене пакування",
      lines: [{ lot_id: inventoryLots[0].id, quantity: "2" }],
    });
  });

  it("blocks an over-stock write-off locally and protects the unsaved form", async () => {
    renderApp("/inventory");

    fireEvent.click(await screen.findByRole("button", { name: "Відкрити Каполін, 1 см" }));
    fireEvent.click(await screen.findByRole("button", { name: "Ручне списання" }));
    const dialog = await screen.findByRole("dialog", { name: "Ручне списання" });
    fireEvent.change(within(dialog).getByLabelText("Кількість списання"), { target: { value: "99" } });
    fireEvent.change(within(dialog).getByLabelText("Причина"), { target: { value: "Пошкодження" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Підтвердити списання" }));

    expect(within(dialog).getByRole("alert")).toHaveTextContent("Доступно лише 4 шт.");
    fireEvent.click(within(dialog).getByRole("button", { name: "Скасувати" }));
    expect(within(dialog).getByText("Є незбережене списання")).toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.some(([input]) => input instanceof Request
      && input.method === "POST"
      && input.url.endsWith("/api/v1/inventory/write-offs"))).toBe(false);
  });
});

describe("TP-503 stocktake and append-only movement journal", () => {
  it("freezes a typed physical count and posts the same immutable draft", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse({ materials: [inventoryMaterial, healthyInventoryMaterial] }))
      .mockResolvedValueOnce(jsonResponse(stocktakePreview))
      .mockResolvedValueOnce(jsonResponse(stocktakeDraft, 201))
      .mockResolvedValueOnce(jsonResponse(stocktakePosted))
      .mockResolvedValueOnce(jsonResponse({ materials: [inventoryMaterial, healthyInventoryMaterial] }));
    renderApp("/inventory");

    await screen.findByText("Каполін, 1 см");
    fireEvent.click(screen.getByRole("button", { name: "Інвентаризація" }));
    const dialog = await screen.findByRole("dialog", { name: "Нова інвентаризація" });
    fireEvent.change(within(dialog).getByLabelText(
      `Фактичний залишок, ${inventoryMaterial.name}, партія ${inventoryLots[0].lot_number}`,
    ), { target: { value: "6" } });
    fireEvent.change(within(dialog).getByLabelText("Коментар"), {
      target: { value: "Щомісячний контроль" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Зафіксувати підрахунок" }));

    expect(await screen.findByText("Підрахунок зафіксовано")).toBeInTheDocument();
    expect(screen.getByText("Чернетку зафіксовано й більше не можна редагувати.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Провести інвентаризацію" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Інвентаризацію проведено");
    expect(screen.getByRole("status")).toHaveTextContent(stocktakePosted.public_number);

    const requests = fetchMock.mock.calls
      .map(([input]) => input)
      .filter((input): input is Request => input instanceof Request
        && input.method === "POST"
        && input.url.includes("/api/v1/inventory/stocktakes"));
    expect(requests).toHaveLength(2);
    const draftRequest = requests[0];
    const postRequest = requests[1];
    if (draftRequest === undefined || postRequest === undefined) {
      throw new Error("Expected stocktake draft and post requests.");
    }
    expect(draftRequest.headers.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
    expect(postRequest.headers.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
    expect(draftRequest.headers.get("Idempotency-Key")).not.toBe(
      postRequest.headers.get("Idempotency-Key"),
    );
    expect(await draftRequest.clone().json()).toEqual({
      comment: "Щомісячний контроль",
      lines: [
        { lot_id: inventoryLots[0].id, actual_quantity: "6" },
        { lot_id: inventoryLots[1].id, actual_quantity: "8.000" },
      ],
    });
    expect(postRequest.url).toContain(`/stocktakes/${stocktakeDraft.id}/post`);
  });

  it("blocks an invalid physical count locally and protects unsaved values", async () => {
    renderApp("/inventory");

    await screen.findByText("Каполін, 1 см");
    fireEvent.click(screen.getByRole("button", { name: "Інвентаризація" }));
    const dialog = await screen.findByRole("dialog", { name: "Нова інвентаризація" });
    fireEvent.change(within(dialog).getByLabelText(
      `Фактичний залишок, ${inventoryMaterial.name}, партія ${inventoryLots[0].lot_number}`,
    ), { target: { value: "-1" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Зафіксувати підрахунок" }));

    expect(within(dialog).getByRole("alert")).toHaveTextContent("має бути числом від нуля");
    expect(vi.mocked(fetch).mock.calls.some(([input]) => input instanceof Request
      && input.method === "POST"
      && input.url.endsWith("/api/v1/inventory/stocktakes"))).toBe(false);
    fireEvent.click(within(dialog).getByRole("button", { name: "Скасувати" }));
    expect(within(dialog).getByText("Є незбережений підрахунок")).toBeInTheDocument();
  });

  it("searches movement history and opens immutable operation detail", async () => {
    const fetchMock = vi.mocked(fetch);
    renderApp("/inventory");

    await screen.findByText("Каполін, 1 см");
    fireEvent.click(screen.getByRole("button", { name: "Журнал рухів" }));
    expect(await screen.findByText(inventoryMovementJournal.movements[0].operation_public_number))
      .toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Пошук"), { target: { value: "KAP-001" } });
    fireEvent.change(screen.getByLabelText("Тип руху"), {
      target: { value: "STOCKTAKE_ADJUSTMENT" },
    });
    fireEvent.change(screen.getByLabelText("Працівник"), { target: { value: "admin@" } });
    fireEvent.click(screen.getByRole("button", { name: "Застосувати" }));

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([input]) => input instanceof Request
        && input.method === "GET"
        && input.url.includes("/api/v1/inventory/movements?")
        && input.url.includes("search=KAP-001")
        && input.url.includes("kind=STOCKTAKE_ADJUSTMENT")
        && input.url.includes("actor=admin%40"))).toBe(true);
    });
    fireEvent.click(screen.getByRole("button", {
      name: `Відкрити операцію ${inventoryMovementJournal.movements[0].operation_public_number}`,
    }));
    const detail = await screen.findByRole("dialog", {
      name: stocktakeOperationDetail.public_number,
    });
    expect(within(detail).getByText("Append-only записи")).toBeInTheDocument();
    expect(within(detail).getByText("Операцію та рухи неможливо змінити або видалити."))
      .toBeInTheDocument();
  });

  it("downloads the server-named CSV with only the last applied movement filters", async () => {
    const fetchMock = vi.mocked(fetch);
    let downloadedFilename = "";
    let downloadedHref = "";
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function captureDownload(this: HTMLAnchorElement) {
        downloadedFilename = this.download;
        downloadedHref = this.href;
      });
    renderApp("/inventory");

    await screen.findByText("Каполін, 1 см");
    fireEvent.click(screen.getByRole("button", { name: "Журнал рухів" }));
    await screen.findByText(inventoryMovementJournal.movements[0].operation_public_number);
    fireEvent.change(screen.getByLabelText("Пошук"), { target: { value: "KAP-001" } });
    fireEvent.change(screen.getByLabelText("Тип руху"), {
      target: { value: "STOCKTAKE_ADJUSTMENT" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Застосувати" }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([input]) => input instanceof Request
        && input.url.includes("/api/v1/inventory/movements?")
        && input.url.includes("search=KAP-001"))).toBe(true);
    });
    fireEvent.change(screen.getByLabelText("Пошук"), {
      target: { value: "ще-не-застосовано" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Експортувати CSV" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Завантаження CSV розпочато.",
    );
    const exportRequest = fetchMock.mock.calls
      .map(([input]) => input)
      .find((input): input is Request => input instanceof Request
        && input.url.includes("/api/v1/inventory/movements/export"));
    expect(exportRequest).toBeDefined();
    expect(exportRequest?.headers.get("Accept")).toBe("text/csv");
    expect(exportRequest?.url).toContain("search=KAP-001");
    expect(exportRequest?.url).toContain("kind=STOCKTAKE_ADJUSTMENT");
    expect(exportRequest?.url).not.toContain(encodeURIComponent("ще-не-застосовано"));
    expect(downloadedFilename).toBe("inventory-movements-20260723-100000.csv");
    expect(downloadedHref).toBe("blob:inventory-export");
    anchorClick.mockRestore();
  });

  it("keeps journal rows and applied filters after an export error", async () => {
    const fetchMock = vi.mocked(fetch);
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    renderApp("/inventory");

    await screen.findByText("Каполін, 1 см");
    fireEvent.click(screen.getByRole("button", { name: "Журнал рухів" }));
    await screen.findByText(inventoryMovementJournal.movements[0].operation_public_number);
    fetchMock.mockResolvedValueOnce(jsonResponse({
      code: "export_too_large",
      message: "Експорт містить забагато рядків. Звузьте фільтри.",
      fields: { filters: ["Максимум 5000 рядків за один файл."] },
      correlation_id: "tp-1002-test",
    }, 422));
    fireEvent.click(screen.getByRole("button", { name: "Експортувати CSV" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Експорт містить забагато рядків. Звузьте фільтри.",
    );
    expect(screen.getByText(inventoryMovementJournal.movements[0].operation_public_number))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Повторити export" })).toBeInTheDocument();
    expect(anchorClick).not.toHaveBeenCalled();
    anchorClick.mockRestore();
  });
});

describe("TP-401 role-scoped calendar", () => {
  it("renders concurrent appointments in separate specialist columns", async () => {
    renderApp("/calendar");

    expect(await screen.findByRole("heading", { name: "Розклад клініки" })).toBeInTheDocument();
    expect(await screen.findByText("Марія Бондар")).toBeInTheDocument();
    expect(screen.getByText("Ірина Коваль")).toBeInTheDocument();
    expect(screen.getAllByTestId("calendar-event")).toHaveLength(2);
    expect(screen.getAllByText("Олена Подолог").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Ірина Савчук").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Перерва").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Вільно").length).toBeGreaterThan(0);
  });

  it("switches to the seven-day overview and filters a specialist locally", async () => {
    const weekFixture = {
      ...calendarFixture,
      days: Array.from({ length: 7 }, (_, index) => ({
        ...calendarFixture.days[0],
        date: `2026-07-${String(20 + index).padStart(2, "0")}`,
      })),
    };
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse(calendarFixture))
      .mockResolvedValueOnce(jsonResponse(weekFixture));
    renderApp("/calendar");
    await screen.findByText("Марія Бондар");

    fireEvent.click(screen.getByRole("button", { name: "Тиждень" }));
    expect(await screen.findByRole("region", { name: "Тижневий календар" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Спеціаліст"), { target: { value: "4" } });

    expect(screen.getAllByText("Марія Бондар").length).toBeGreaterThan(0);
    expect(screen.queryByText("Ірина Коваль")).not.toBeInTheDocument();
    const request = vi.mocked(fetch).mock.calls.at(-1)?.[0];
    expect(request).toBeInstanceOf(Request);
    expect((request as Request).url).toContain("from=");
    expect((request as Request).url).toContain("to=");
  });

  it("opens the styled date picker and loads a day from another month", async () => {
    renderApp("/calendar");
    await screen.findByText("Марія Бондар");

    const trigger = screen.getByRole("button", { name: /Обрати дату:/ });
    fireEvent.click(trigger);
    const picker = screen.getByRole("dialog", { name: "Вибір дати календаря" });
    const selectedDay = picker.querySelector<HTMLButtonElement>(
      "[data-calendar-date][aria-pressed='true']",
    );
    expect(selectedDay).not.toBeNull();
    expect(selectedDay).toHaveFocus();
    const selectedDate = selectedDay?.dataset.calendarDate;
    expect(selectedDate).toBeDefined();
    const [year = 0, month = 0] = (selectedDate ?? "").split("-").map(Number);
    const targetDate = new Date(Date.UTC(year, month, 5)).toISOString().slice(0, 10);
    const requestsBeforeSelection = vi.mocked(fetch).mock.calls.filter(([input]) =>
      input instanceof Request && input.url.includes("/api/v1/calendar")).length;

    fireEvent.click(within(picker).getByRole("button", { name: "Наступний місяць" }));
    const targetDay = picker.querySelector<HTMLButtonElement>(
      `[data-calendar-date="${targetDate}"]`,
    );
    expect(targetDay).not.toBeNull();
    if (targetDay === null) throw new Error("Target calendar day was not rendered.");
    fireEvent.click(targetDay);

    await waitFor(() => {
      const calendarRequests = vi.mocked(fetch).mock.calls.filter(([input]) =>
        input instanceof Request && input.url.includes("/api/v1/calendar"));
      expect(calendarRequests.length).toBeGreaterThan(requestsBeforeSelection);
    });
    const calendarRequest = vi.mocked(fetch).mock.calls
      .map(([input]) => input)
      .filter((input): input is Request =>
        input instanceof Request && input.url.includes("/api/v1/calendar"))
      .at(-1);
    const from = new URL(calendarRequest?.url ?? "http://localhost").searchParams.get("from");
    const kyivDate = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Europe/Kyiv",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    expect(kyivDate.format(new Date(from ?? ""))).toBe(targetDate);
    expect(screen.queryByRole("dialog", { name: "Вибір дати календаря" }))
      .not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("selects a week in the date picker and closes it with Escape", async () => {
    renderApp("/calendar");
    await screen.findByText("Марія Бондар");

    const trigger = screen.getByRole("button", { name: /Обрати дату:/ });
    fireEvent.click(trigger);
    const picker = screen.getByRole("dialog", { name: "Вибір дати календаря" });
    const selectedDay = picker.querySelector<HTMLButtonElement>(
      "[data-calendar-date][aria-pressed='true']",
    );
    const selectedDate = selectedDay?.dataset.calendarDate ?? "";
    const [year = 0, month = 0, day = 0] = selectedDate.split("-").map(Number);
    const targetDate = new Date(Date.UTC(year, month - 1, day + 7))
      .toISOString()
      .slice(0, 10);
    const targetWeekday = new Date(`${targetDate}T12:00:00Z`).getUTCDay();
    const targetWeekStart = new Date(Date.UTC(
      Number(targetDate.slice(0, 4)),
      Number(targetDate.slice(5, 7)) - 1,
      Number(targetDate.slice(8, 10)) - ((targetWeekday + 6) % 7),
    )).toISOString().slice(0, 10);

    fireEvent.click(within(picker).getByRole("button", { name: "Тиждень" }));
    const targetDay = picker.querySelector<HTMLButtonElement>(
      `[data-calendar-date="${targetDate}"]`,
    );
    expect(targetDay).not.toBeNull();
    if (targetDay === null) throw new Error("Target calendar day was not rendered.");
    fireEvent.click(targetDay);

    const kyivDate = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Europe/Kyiv",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    await waitFor(() => {
      const calendarRequest = vi.mocked(fetch).mock.calls
        .map(([input]) => input)
        .filter((input): input is Request =>
          input instanceof Request && input.url.includes("/api/v1/calendar"))
        .at(-1);
      const from = new URL(calendarRequest?.url ?? "http://localhost")
        .searchParams
        .get("from");
      expect(kyivDate.format(new Date(from ?? ""))).toBe(targetWeekStart);
    });
    expect(trigger).toHaveFocus();

    fireEvent.click(trigger);
    expect(screen.getByRole("dialog", { name: "Вибір дати календаря" }))
      .toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Вибір дати календаря" }))
        .not.toBeInTheDocument();
      expect(trigger).toHaveFocus();
    });
  });

  it("locks a podologist to the server-provided own column", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(podologistSession))
      .mockResolvedValueOnce(jsonResponse({
        ...calendarFixture,
        specialists: [calendarFixture.specialists[0]],
        events: [calendarFixture.events[0]],
      }));
    renderApp("/calendar");

    expect(await screen.findByText("Лише моя колонка")).toBeInTheDocument();
    expect(await screen.findByText("Марія Бондар")).toBeInTheDocument();
    expect(screen.queryByLabelText("Спеціаліст")).not.toBeInTheDocument();
    expect(screen.queryByText("Ірина Коваль")).not.toBeInTheDocument();
  });

  it("keeps a recoverable server error with retry", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse({
        ...anonymousProblem,
        code: "calendar_unavailable",
        message: "Календар тимчасово недоступний.",
      }, 503))
      .mockResolvedValueOnce(jsonResponse(calendarFixture));
    renderApp("/calendar");

    expect(await screen.findByRole("alert")).toHaveTextContent("Календар тимчасово недоступний");
    fireEvent.click(screen.getByRole("button", { name: "Повторити" }));
    expect(await screen.findByText("Марія Бондар")).toBeInTheDocument();
  });
});

describe("TP-404 responsive calendar gate", () => {
  it("keeps concurrent events in separate columns and names both keyboard scrollers", async () => {
    renderApp("/calendar");

    const dayScroller = await screen.findByRole("generic", { name: "Прокручувана сітка спеціалістів" });
    const events = await screen.findAllByTestId("calendar-event");
    expect(dayScroller).toHaveAttribute("tabindex", "0");
    expect(dayScroller).toHaveAccessibleDescription(/Гортайте горизонтально/);
    expect(events[0]?.style.gridRow.split("/")[0]?.trim()).toBe(
      events[1]?.style.gridRow.split("/")[0]?.trim(),
    );
    expect(events[0]?.style.gridColumn).not.toBe(events[1]?.style.gridColumn);
    dayScroller.focus();
    expect(dayScroller).toHaveFocus();

    fireEvent.click(screen.getByRole("button", { name: "Тиждень" }));
    const weekScroller = await screen.findByRole("generic", { name: "Прокручуваний тижневий календар" });
    expect(weekScroller).toHaveAttribute("tabindex", "0");
    expect(weekScroller).toHaveAccessibleDescription(/Гортайте тиждень горизонтально/);
    weekScroller.focus();
    expect(weekScroller).toHaveFocus();
  });

  it("moves focus into appointment details and returns it to the invoking card", async () => {
    renderApp("/calendar");

    const event = await screen.findByRole("button", { name: /Марія Бондар, Підтверджено/ });
    event.focus();
    fireEvent.click(event);

    const close = await screen.findByRole("button", { name: "Закрити деталі запису" });
    expect(close).toHaveFocus();
    fireEvent.click(close);

    await waitFor(() => { expect(event).toHaveFocus(); });
  });
});

describe("TP-402 appointment create", () => {
  it("creates an appointment from the calendar CTA and preserves server-derived fields", async () => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
    const fetchMock = vi.mocked(fetch);
    renderApp("/calendar");
    await screen.findByRole("heading", { name: "Розклад клініки" });

    fireEvent.click(screen.getByRole("button", { name: "Новий запис" }));
    const dialog = await screen.findByRole("dialog", { name: "Новий запис" });
    fireEvent.change(within(dialog).getByLabelText("Спеціаліст"), { target: { value: "4" } });
    await within(dialog).findByRole("option", { name: clinicService.name });
    fireEvent.change(within(dialog).getByLabelText("Послуга"), {
      target: { value: clinicService.id },
    });
    fireEvent.change(within(dialog).getByRole("searchbox", { name: "Знайти пацієнта для запису" }), {
      target: { value: "Марія" },
    });
    fireEvent.click(await within(dialog).findByRole("button", { name: /Марія Бондар/ }));
    await within(dialog).findByRole("option", { name: "11:00–11:45" });
    fireEvent.change(within(dialog).getByLabelText("Вільний час"), {
      target: { value: availabilityFixture.slots[0].starts_at },
    });
    fireEvent.change(within(dialog).getByLabelText("Скарги / причина звернення"), {
      target: { value: "Біль під час ходьби" },
    });
    expect(within(dialog).getByLabelText("Тривалість")).toHaveValue("45 хв");
    expect(within(dialog).getByLabelText("Статус")).toHaveValue("Новий");
    fireEvent.click(within(dialog).getByRole("button", { name: "Створити запис" }));

    expect(await screen.findByRole("status")).toHaveTextContent("A-18DC97694DC6");
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Новий запис" })).not.toBeInTheDocument();
    });
    const request = fetchMock.mock.calls.find(([input]) =>
      input instanceof Request
      && input.method === "POST"
      && input.url.endsWith("/api/v1/appointments"))?.[0];
    expect(request).toBeInstanceOf(Request);
    expect(await (request as Request).clone().json()).toMatchObject({
      patient_id: patientFixture.id,
      specialist_id: 4,
      service_id: clinicService.id,
      room_id: clinicRoom.id,
      starts_at: availabilityFixture.slots[0].starts_at,
      status_code: "NEW",
      complaints: "Біль під час ходьби",
      has_no_complaints: false,
    });
  });

  it("prefills a free calendar cell and keeps the patient locked from a patient card", async () => {
    const detailPath = `/patients/${patientFixture.id}/overview`;
    renderApp(detailPath);
    await screen.findByRole("heading", { name: "Марія Бондар", level: 1 });
    fireEvent.click(screen.getByRole("link", { name: "Записати" }));

    const lockedDialog = await screen.findByRole("dialog", { name: "Новий запис" });
    expect(await within(lockedDialog).findByText("Пацієнта зафіксовано")).toBeInTheDocument();
    expect(within(lockedDialog).getByText(new RegExp(patientFixture.public_number))).toBeInTheDocument();
    expect(within(lockedDialog).queryByRole("searchbox", { name: "Знайти пацієнта для запису" })).not.toBeInTheDocument();
    fireEvent.click(within(lockedDialog).getByRole("button", { name: "Скасувати" }));
    expect(screen.queryByRole("dialog", { name: "Новий запис" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Створити запис на 11:00, Олена Подолог" }));
    const slotDialog = await screen.findByRole("dialog", { name: "Новий запис" });
    expect(within(slotDialog).getByLabelText("Спеціаліст")).toHaveValue("4");
    await within(slotDialog).findByRole("option", { name: clinicService.name });
    fireEvent.change(within(slotDialog).getByLabelText("Послуга"), {
      target: { value: clinicService.id },
    });
    await waitFor(() => {
      expect(within(slotDialog).getByLabelText("Вільний час")).toHaveValue(
        availabilityFixture.slots[0].starts_at,
      );
    });
  });

  it("locks a podologist to self inside the create form", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input.toString();
      const method = input instanceof Request ? input.method : (init?.method ?? "GET");
      if (url.includes("/api/v1/session")) return Promise.resolve(jsonResponse(podologistSession));
      if (url.includes("/api/v1/calendar")) return Promise.resolve(jsonResponse({
        ...calendarFixture,
        specialists: [calendarFixture.specialists[0]],
        events: [calendarFixture.events[0]],
      }));
      if (url.includes("/api/v1/services") && method === "GET") {
        return Promise.resolve(jsonResponse({ services: [clinicService] }));
      }
      return Promise.resolve(jsonResponse(availabilityFixture));
    });
    renderApp("/calendar?compose=appointment");

    const dialog = await screen.findByRole("dialog", { name: "Новий запис" });
    const specialist = within(dialog).getByLabelText("Спеціаліст");
    expect(specialist).toBeDisabled();
    expect(specialist).toHaveValue(String(podologistSession.user.id));
    expect(within(dialog).getByText("Подолог створює запис лише до себе.")).toBeInTheDocument();
  });

  it("creates a missing patient inline without closing the appointment form", async () => {
    const createdPatient = {
      ...medicalPatientDetailFixture,
      id: "7c788006-1c36-458f-84d4-46be30aed58d",
      public_number: "P-7C7880061C36",
      first_name: "Нова",
      last_name: "Пацієнтка",
      display_name: "Нова Пацієнтка",
      phone: "+380 93 100 20 30",
    } as const;
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input.toString();
      const method = input instanceof Request ? input.method : (init?.method ?? "GET");
      if (url.includes("/api/v1/session")) return Promise.resolve(jsonResponse(adminSession));
      if (url.includes("/api/v1/calendar")) return Promise.resolve(jsonResponse(calendarFixture));
      if (url.includes("/api/v1/services")) return Promise.resolve(jsonResponse({ services: [clinicService] }));
      if (url.includes("/api/v1/patients") && method === "POST") {
        return Promise.resolve(jsonResponse({
          patient: createdPatient,
          duplicate_warning: false,
          possible_duplicates: [],
        }, 201));
      }
      if (url.includes("/api/v1/patients")) {
        return Promise.resolve(jsonResponse({ patients: [], next_cursor: null }));
      }
      return Promise.resolve(jsonResponse(availabilityFixture));
    });
    renderApp("/calendar?compose=appointment");
    const appointmentDialog = await screen.findByRole("dialog", { name: "Новий запис" });
    fireEvent.change(within(appointmentDialog).getByRole("searchbox", { name: "Знайти пацієнта для запису" }), {
      target: { value: "Нова" },
    });
    fireEvent.click(await within(appointmentDialog).findByRole("button", { name: "Створити пацієнта" }));
    const patientDialog = screen.getByRole("dialog", { name: "Новий пацієнт" });
    fireEvent.change(within(patientDialog).getByLabelText("Ім’я"), { target: { value: "Нова" } });
    fireEvent.change(within(patientDialog).getByLabelText("Прізвище"), { target: { value: "Пацієнтка" } });
    fireEvent.change(within(patientDialog).getByLabelText("Телефон"), { target: { value: "+380 93 100 20 30" } });
    fireEvent.click(within(patientDialog).getByRole("button", { name: "Створити пацієнта" }));

    expect(await within(appointmentDialog).findByText("Нова Пацієнтка")).toBeInTheDocument();
    expect(within(appointmentDialog).getByText(/P-7C7880061C36/)).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Новий запис" })).toBeInTheDocument();
  });

  it("preserves entered fields after a slot conflict and asks for another time", async () => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input.toString();
      const method = input instanceof Request ? input.method : (init?.method ?? "GET");
      if (url.includes("/api/v1/session")) return Promise.resolve(jsonResponse(adminSession));
      if (url.includes("/api/v1/calendar")) return Promise.resolve(jsonResponse(calendarFixture));
      if (url.includes("/api/v1/services")) return Promise.resolve(jsonResponse({ services: [clinicService] }));
      if (url.includes("/api/v1/patients")) {
        return Promise.resolve(jsonResponse({ patients: [patientFixture], next_cursor: null }));
      }
      if (url.includes("/api/v1/appointments/availability")) {
        return Promise.resolve(jsonResponse(availabilityFixture));
      }
      if (url.endsWith("/api/v1/appointments") && method === "POST") {
        return Promise.resolve(jsonResponse({
          ...anonymousProblem,
          code: "appointment_slot_conflict",
          message: "Кабінет уже зайнятий у цей час. Оберіть інший кабінет або час.",
          fields: { room_id: ["Кабінет уже зайнятий."] },
        }, 409));
      }
      return Promise.resolve(jsonResponse(appointmentFixture));
    });
    renderApp("/calendar?compose=appointment");
    const dialog = await screen.findByRole("dialog", { name: "Новий запис" });
    fireEvent.change(within(dialog).getByLabelText("Спеціаліст"), { target: { value: "4" } });
    await within(dialog).findByRole("option", { name: clinicService.name });
    fireEvent.change(within(dialog).getByLabelText("Послуга"), { target: { value: clinicService.id } });
    fireEvent.change(within(dialog).getByRole("searchbox", { name: "Знайти пацієнта для запису" }), { target: { value: "Марія" } });
    fireEvent.click(await within(dialog).findByRole("button", { name: /Марія Бондар/ }));
    await within(dialog).findByRole("option", { name: "11:00–11:45" });
    fireEvent.change(within(dialog).getByLabelText("Вільний час"), { target: { value: availabilityFixture.slots[0].starts_at } });
    fireEvent.click(within(dialog).getByLabelText("Скарг немає"));
    fireEvent.change(within(dialog).getByLabelText("Коментар · необов’язково"), { target: { value: "Зберегти цей коментар" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Створити запис" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Кабінет уже зайнятий");
    expect(within(dialog).getByText(new RegExp(patientFixture.public_number))).toBeInTheDocument();
    expect(within(dialog).getByLabelText("Послуга")).toHaveValue(clinicService.id);
    expect(within(dialog).getByLabelText("Скарг немає")).toBeChecked();
    expect(within(dialog).getByLabelText("Коментар · необов’язково")).toHaveValue("Зберегти цей коментар");
    expect(within(dialog).getByLabelText("Вільний час")).toHaveValue("");
  });
});

describe("TP-403 appointment detail and workflow", () => {
  it("opens a calendar event and saves audited editable fields with its current version", async () => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
    const updated = {
      ...appointmentDetailFixture,
      comment: "Підготувати рекомендації після прийому",
      version: 5,
    };
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input.toString();
      const method = input instanceof Request ? input.method : (init?.method ?? "GET");
      const path = new URL(url).pathname;
      if (url.includes("/api/v1/session")) return Promise.resolve(jsonResponse(adminSession));
      if (url.includes("/api/v1/calendar")) return Promise.resolve(jsonResponse(calendarFixture));
      if (url.includes("/api/v1/services")) {
        return Promise.resolve(jsonResponse({ services: [clinicService] }));
      }
      if (path.endsWith(`/appointments/${appointmentDetailFixture.id}`) && method === "PATCH") {
        return Promise.resolve(jsonResponse(updated));
      }
      return Promise.resolve(jsonResponse(appointmentDetailFixture));
    });
    renderApp("/calendar");
    fireEvent.click(await screen.findByRole("button", { name: /Марія Бондар, Підтверджено/ }));

    const dialog = await screen.findByRole("dialog", { name: "Деталі запису" });
    expect(within(dialog).getByText(appointmentDetailFixture.public_number)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Пацієнт прийшов" })).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Редагувати" }));
    fireEvent.change(within(dialog).getByLabelText("Коментар · необов’язково"), {
      target: { value: updated.comment },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Зберегти зміни" }));

    const updatedDialog = await screen.findByRole("dialog", { name: "Деталі запису" });
    expect(within(updatedDialog).getByText(updated.comment)).toBeInTheDocument();
    expect(await screen.findByText(`Запис ${updated.public_number} оновлено.`)).toBeInTheDocument();
    const request = fetchMock.mock.calls.find(([input]) =>
      input instanceof Request && input.method === "PATCH")?.[0];
    expect(request).toBeInstanceOf(Request);
    expect(await (request as Request).clone().json()).toMatchObject({
      version: 4,
      complaints: appointmentDetailFixture.complaints,
      has_no_complaints: false,
      comment: updated.comment,
    });
  });

  it("applies a server-allowed status and cancels only with an explicit reason", async () => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
    const arrived = {
      ...appointmentDetailFixture,
      status: { code: "ARRIVED", label: "Пацієнт прийшов", color: "#7C3AED" },
      version: 5,
      allowed_status_transitions: [],
    };
    const canceled = {
      ...arrived,
      status: { code: "CANCELED", label: "Скасовано", color: "#DC2626" },
      cancellation_reason: "Пацієнтка захворіла",
      version: 6,
      can_edit: false,
      can_reschedule: false,
      can_cancel: false,
    };
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input.toString();
      const method = input instanceof Request ? input.method : (init?.method ?? "GET");
      if (url.includes("/api/v1/session")) return Promise.resolve(jsonResponse(adminSession));
      if (url.includes("/api/v1/calendar")) return Promise.resolve(jsonResponse(calendarFixture));
      if (url.includes("/api/v1/services")) {
        return Promise.resolve(jsonResponse({ services: [clinicService] }));
      }
      if (url.endsWith("/status") && method === "POST") return Promise.resolve(jsonResponse(arrived));
      if (url.endsWith("/cancel") && method === "POST") return Promise.resolve(jsonResponse(canceled));
      return Promise.resolve(jsonResponse(appointmentDetailFixture));
    });
    renderApp("/calendar");
    fireEvent.click(await screen.findByRole("button", { name: /Марія Бондар, Підтверджено/ }));
    const dialog = await screen.findByRole("dialog", { name: "Деталі запису" });

    fireEvent.click(within(dialog).getByRole("button", { name: "Пацієнт прийшов" }));
    await screen.findByText("Статус запису змінено на «Пацієнт прийшов».");
    fireEvent.click(within(dialog).getByRole("button", { name: "Скасувати запис" }));
    const cancelButton = within(dialog).getByRole("button", { name: "Скасувати запис" });
    fireEvent.click(cancelButton);
    expect(within(dialog).getByText("Укажіть причину скасування.")).toBeInTheDocument();
    fireEvent.change(within(dialog).getByRole("textbox"), {
      target: { value: canceled.cancellation_reason },
    });
    fireEvent.click(cancelButton);

    const canceledDialog = await screen.findByRole("dialog", { name: "Деталі запису" });
    expect(within(canceledDialog).getByText(canceled.cancellation_reason)).toBeInTheDocument();
    const mutationRequests = fetchMock.mock.calls
      .map(([input]) => input)
      .filter((input): input is Request => input instanceof Request && input.method === "POST");
    expect(mutationRequests).toHaveLength(2);
    const statusRequest = mutationRequests[0];
    const cancelRequest = mutationRequests[1];
    if (statusRequest === undefined || cancelRequest === undefined) {
      throw new Error("Expected status and cancel requests.");
    }
    expect(await statusRequest.clone().json()).toEqual({
      version: 4,
      status_code: "ARRIVED",
    });
    expect(await cancelRequest.clone().json()).toEqual({
      version: 5,
      reason: canceled.cancellation_reason,
    });
  });

  it("keeps reschedule choices after a slot conflict and refreshes available times", async () => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input.toString();
      const method = input instanceof Request ? input.method : (init?.method ?? "GET");
      if (url.includes("/api/v1/session")) return Promise.resolve(jsonResponse(adminSession));
      if (url.includes("/api/v1/calendar")) return Promise.resolve(jsonResponse(calendarFixture));
      if (url.includes("/api/v1/services")) {
        return Promise.resolve(jsonResponse({ services: [clinicService] }));
      }
      if (url.includes("/api/v1/appointments/availability")) {
        return Promise.resolve(jsonResponse(availabilityFixture));
      }
      if (method === "PATCH") {
        return Promise.resolve(jsonResponse({
          ...anonymousProblem,
          code: "appointment_slot_conflict",
          message: "Кабінет уже зайнятий у цей час. Оберіть інший кабінет або час.",
          fields: { room_id: ["Кабінет уже зайнятий."] },
        }, 409));
      }
      return Promise.resolve(jsonResponse(appointmentDetailFixture));
    });
    renderApp("/calendar");
    fireEvent.click(await screen.findByRole("button", { name: /Марія Бондар, Підтверджено/ }));
    const dialog = await screen.findByRole("dialog", { name: "Деталі запису" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Перенести" }));

    await within(dialog).findByRole("option", { name: clinicService.name });
    await within(dialog).findByRole("option", { name: "11:00–11:45" });
    fireEvent.change(within(dialog).getByLabelText("Новий час"), {
      target: { value: availabilityFixture.slots[0].starts_at },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Підтвердити перенесення" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Кабінет уже зайнятий");
    expect(within(dialog).getByLabelText("Послуга для перенесення")).toHaveValue(clinicService.id);
    expect(within(dialog).getByLabelText("Новий час")).toHaveValue("");
    await waitFor(() => {
      const availabilityCalls = fetchMock.mock.calls.filter(([input]) =>
        input instanceof Request && input.url.includes("/api/v1/appointments/availability"));
      expect(availabilityCalls.length).toBeGreaterThanOrEqual(2);
    });
  });
});

describe("TP-601 visit start and examination draft", () => {
  it("starts an arrived appointment and opens the one visit workspace", async () => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input.toString();
      const method = input instanceof Request ? input.method : (init?.method ?? "GET");
      const path = new URL(url).pathname;
      if (url.includes("/api/v1/session")) return Promise.resolve(jsonResponse(adminSession));
      if (url.includes("/api/v1/calendar")) return Promise.resolve(jsonResponse(calendarFixture));
      if (url.includes("/api/v1/services")) {
        return Promise.resolve(jsonResponse({ services: [clinicService] }));
      }
      if (path.endsWith(`/appointments/${arrivedAppointmentDetailFixture.id}`) && method === "GET") {
        return Promise.resolve(jsonResponse(arrivedAppointmentDetailFixture));
      }
      if (url.endsWith("/start-visit") && method === "POST") {
        return Promise.resolve(jsonResponse(visitFixture, 201));
      }
      if (path.endsWith(`/visits/${visitFixture.id}`) && method === "GET") {
        return Promise.resolve(jsonResponse(visitFixture));
      }
      return Promise.resolve(jsonResponse(appointmentDetailFixture));
    });
    renderApp("/calendar");
    fireEvent.click(await screen.findByRole("button", { name: /Марія Бондар, Підтверджено/ }));
    const dialog = await screen.findByRole("dialog", { name: "Деталі запису" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Почати прийом" }));

    expect(await screen.findByRole("heading", { name: visitFixture.patient.display_name, level: 1 }))
      .toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Кроки оформлення прийому" })).toBeInTheDocument();
    expect(screen.getByText("Чернетка не списує матеріали, не створює оплату та не завершує прийом."))
      .toBeInTheDocument();
    const startRequest = fetchMock.mock.calls
      .map(([input]) => input)
      .find((input): input is Request => input instanceof Request && input.url.endsWith("/start-visit"));
    if (startRequest === undefined) throw new Error("Expected a start-visit request.");
    expect(startRequest).toBeInstanceOf(Request);
    expect(await startRequest.clone().json()).toEqual({ version: 5 });
    expect(startRequest.headers.get("X-CSRFToken")).toBe("test-csrf");
  });

  it("saves all examination fields with the current visit version", async () => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
    const updatedVisit = {
      ...visitFixture,
      version: 2,
      objective_examination: "Локальний гіперкератоз правої стопи",
      detected_conditions: ["HYPERKERATOSIS"],
      podologist_notes: "Зменшити навантаження",
    } as const;
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input.toString();
      const method = input instanceof Request ? input.method : (init?.method ?? "GET");
      if (url.includes("/api/v1/session")) return Promise.resolve(jsonResponse(adminSession));
      if (url.includes(`/api/v1/visits/${visitFixture.id}`) && method === "PUT") {
        return Promise.resolve(jsonResponse(updatedVisit));
      }
      return Promise.resolve(jsonResponse(visitFixture));
    });
    renderApp(`/visits/${visitFixture.id}`);
    await screen.findByRole("heading", { name: visitFixture.patient.display_name, level: 1 });
    fireEvent.change(screen.getByLabelText("Об’єктивний огляд"), {
      target: { value: updatedVisit.objective_examination },
    });
    fireEvent.click(screen.getByLabelText("Гіперкератоз"));
    fireEvent.change(screen.getByLabelText("Нотатки подолога · необов’язково"), {
      target: { value: updatedVisit.podologist_notes },
    });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти чернетку" }));

    await screen.findByText("Чернетку збережено");
    expect(screen.getByText("Версія чернетки: 2")).toBeInTheDocument();
    const saveRequest = fetchMock.mock.calls
      .map(([input]) => input)
      .find((input): input is Request => input instanceof Request && input.method === "PUT");
    if (saveRequest === undefined) throw new Error("Expected a visit draft request.");
    expect(saveRequest).toBeInstanceOf(Request);
    expect(await saveRequest.clone().json()).toEqual({
      version: 1,
      complaints: visitFixture.complaints,
      has_no_complaints: false,
      objective_examination: updatedVisit.objective_examination,
      detected_conditions: ["HYPERKERATOSIS"],
      podologist_notes: updatedVisit.podologist_notes,
    });
    expect(saveRequest.headers.get("X-CSRFToken")).toBe("test-csrf");
  });

  it("blocks invalid autosave and protects unsaved fields", async () => {
    renderApp(`/visits/${visitFixture.id}`);
    await screen.findByRole("heading", { name: visitFixture.patient.display_name, level: 1 });
    fireEvent.change(screen.getByLabelText("Скарги / причина звернення"), { target: { value: "" } });

    expect(screen.getByRole("alert")).toHaveTextContent("Укажіть скарги або виберіть");
    expect(screen.getByRole("button", { name: "Зберегти чернетку" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "До календаря" }));
    expect(screen.getByRole("dialog", { name: "Вийти без останніх змін?" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Залишитися" }));
    expect(screen.getByLabelText("Скарги / причина звернення")).toHaveValue("");
  });

  it("hides the medical workspace from reception", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(receptionSession));
    renderApp(`/visits/${visitFixture.id}`);
    expect(await screen.findByRole("heading", { name: "Добрий день" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: visitFixture.patient.display_name, level: 1 }))
      .not.toBeInTheDocument();
  });
});

describe("TP-602 visit service and material draft", () => {
  it("opens the second wizard step with the seeded primary service and projected total", async () => {
    renderApp(`/visits/${visitFixture.id}`);
    await screen.findByRole("heading", { name: visitFixture.patient.display_name, level: 1 });

    fireEvent.click(screen.getByRole("button", { name: "Далі: послуги й матеріали" }));

    expect(screen.getByRole("heading", { name: "Послуги й матеріали", level: 2 })).toBeInTheDocument();
    expect(screen.getByText("Основна із запису")).toBeInTheDocument();
    expect(screen.getByLabelText(`Кількість послуги ${clinicService.name}`)).toHaveValue(1);
    expect(screen.getAllByText("1 200,00 ₴")).toHaveLength(2);
    expect(screen.getByText(/Списання відбудеться під час завершення прийому/)).toBeInTheDocument();
  });

  it("increments a duplicate service and saves one normalized service line", async () => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
    const fetchMock = vi.mocked(fetch);
    renderApp(`/visits/${visitFixture.id}`);
    await screen.findByRole("heading", { name: visitFixture.patient.display_name, level: 1 });
    fireEvent.click(screen.getByRole("button", { name: "Далі: послуги й матеріали" }));

    fireEvent.click(await screen.findByRole("button", { name: "Додати ще" }));
    expect(screen.getByLabelText(`Кількість послуги ${clinicService.name}`)).toHaveValue(2);
    fireEvent.click(screen.getByRole("button", { name: "Зберегти чернетку" }));

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([input]) => input instanceof Request && input.method === "PUT"))
        .toBe(true);
    });
    const request = fetchMock.mock.calls
      .map(([input]) => input)
      .find((input): input is Request => input instanceof Request && input.method === "PUT");
    if (request === undefined) throw new Error("Expected a visit line draft request.");
    expect(await request.clone().json()).toEqual({
      version: 1,
      service_lines: [{ service_id: clinicService.id, quantity: 2 }],
      material_lines: [],
    });
    expect(request.headers.get("X-CSRFToken")).toBe("test-csrf");
  });

  it("adds a FEFO material lot and saves its factual decimal quantity", async () => {
    const fetchMock = vi.mocked(fetch);
    renderApp(`/visits/${visitFixture.id}`);
    await screen.findByRole("heading", { name: visitFixture.patient.display_name, level: 1 });
    fireEvent.click(screen.getByRole("button", { name: "Далі: послуги й матеріали" }));
    fireEvent.click(screen.getByRole("button", { name: "Додати матеріал" }));
    const dialog = await screen.findByRole("dialog", { name: "Додати матеріал" });

    fireEvent.click(await within(dialog).findByRole("button", { name: "Вибрати" }));
    expect(within(dialog).getByLabelText("Доступна партія")).toHaveValue(inventoryLots[0].id);
    fireEvent.change(within(dialog).getByLabelText(`Фактична кількість, ${inventoryMaterial.unit}`), {
      target: { value: "1.250" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Додати до чернетки" }));

    expect(screen.getByText(`партія ${inventoryLots[0].lot_number}`, { exact: false })).toBeInTheDocument();
    expect(screen.getByLabelText(`Кількість матеріалу ${inventoryMaterial.name}, партія ${inventoryLots[0].lot_number}`)).toHaveValue(1.25);
    fireEvent.click(screen.getByRole("button", { name: "Зберегти чернетку" }));

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([input]) => input instanceof Request && input.method === "PUT"))
        .toBe(true);
    });
    const request = fetchMock.mock.calls
      .map(([input]) => input)
      .find((input): input is Request => input instanceof Request && input.method === "PUT");
    if (request === undefined) throw new Error("Expected a material draft request.");
    expect(await request.clone().json()).toEqual({
      version: 1,
      service_lines: [{ service_id: clinicService.id, quantity: 1 }],
      material_lines: [{ lot_id: inventoryLots[0].id, quantity: "1.250" }],
    });
  });

  it("blocks insufficient material quantity and protects the unsaved line", async () => {
    renderApp(`/visits/${visitFixture.id}`);
    await screen.findByRole("heading", { name: visitFixture.patient.display_name, level: 1 });
    fireEvent.click(screen.getByRole("button", { name: "Далі: послуги й матеріали" }));
    fireEvent.click(screen.getByRole("button", { name: "Додати матеріал" }));
    const dialog = await screen.findByRole("dialog", { name: "Додати матеріал" });
    fireEvent.click(await within(dialog).findByRole("button", { name: "Вибрати" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Додати до чернетки" }));

    const quantity = screen.getByLabelText(`Кількість матеріалу ${inventoryMaterial.name}, партія ${inventoryLots[0].lot_number}`);
    fireEvent.change(quantity, { target: { value: "4.001" } });

    expect(screen.getByRole("alert")).toHaveTextContent("Перевірте кількість послуг і матеріалів");
    expect(screen.getByRole("button", { name: "Зберегти чернетку" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "До календаря" }));
    expect(screen.getByRole("dialog", { name: "Вийти без останніх змін?" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Залишитися" }));
    expect(quantity).toHaveValue(4.001);
  });

  it("keeps changed service quantities after a recoverable server error", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input.toString();
      const method = input instanceof Request ? input.method : (init?.method ?? "GET");
      if (url.includes("/api/v1/session")) return Promise.resolve(jsonResponse(adminSession));
      if (url.includes("/api/v1/services") && method === "GET") {
        return Promise.resolve(jsonResponse({ services: [clinicService] }));
      }
      if (url.includes(`/api/v1/visits/${visitFixture.id}`) && method === "GET") {
        return Promise.resolve(jsonResponse(visitFixture));
      }
      if (url.includes(`/api/v1/visits/${visitFixture.id}`) && method === "PUT") {
        return Promise.resolve(jsonResponse({
          code: "visit_version_conflict",
          message: "Чернетка вже змінилася.",
          fields: { version: ["Версія чернетки застаріла."] },
          correlation_id: "test-correlation",
        }, 409));
      }
      return Promise.resolve(jsonResponse({}));
    });
    renderApp(`/visits/${visitFixture.id}`);
    await screen.findByRole("heading", { name: visitFixture.patient.display_name, level: 1 });
    fireEvent.click(screen.getByRole("button", { name: "Далі: послуги й матеріали" }));
    fireEvent.click(await screen.findByRole("button", { name: "Додати ще" }));
    fireEvent.click(screen.getByRole("button", { name: "Зберегти чернетку" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Ваші дані збережені у формі");
    expect(screen.getByLabelText(`Кількість послуги ${clinicService.name}`)).toHaveValue(2);
    expect(screen.getByRole("button", { name: "Зберегти чернетку" })).toBeEnabled();
  });
});

describe("TP-604 atomic visit finish", () => {
  const openFinishStep = async () => {
    await screen.findByRole("heading", { name: visitFixture.patient.display_name, level: 1 });
    fireEvent.click(screen.getByRole("button", { name: "Далі: послуги й матеріали" }));
    fireEvent.click(screen.getByRole("button", { name: "Далі: фото" }));
    fireEvent.click(screen.getByRole("button", { name: "Далі: завершення" }));
    await screen.findByRole("heading", { name: "Перевірка та завершення", level: 2 });
  };

  it("submits recommendations, handoff and one free follow-up slot with a stable key", async () => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
    const completedVisit = {
      ...visitFixture,
      status: "COMPLETED",
      version: 2,
      total_minor: visitFixture.services_total_minor,
      payment_handoff_requested: true,
      editable: false,
      appointment: {
        ...visitFixture.appointment,
        status_code: "COMPLETED",
        status_label: "Завершено",
      },
      recommendations: [{
        id: "4cc279e8-6463-42eb-bf58-93894af38b9d",
        author_id: adminSession.user.id,
        author_name: adminSession.user.display_name,
        text: "Щоденний домашній догляд",
        version: 1,
        created_at: "2026-07-22T09:00:00Z",
        updated_at: "2026-07-22T09:00:00Z",
      }],
      completed_at: "2026-07-22T09:00:00Z",
    } as const;
    const finishResponse = {
      replayed: false,
      visit: completedVisit,
      receivable: {
        id: "e4c9910f-2c1f-4294-9d15-782630ee270a",
        amount_minor: visitFixture.services_total_minor,
        status: "OPEN",
        created_at: "2026-07-22T09:00:00Z",
      },
      inventory_operation_id: null,
      movement_ids: [],
      follow_up_appointment_id: "a4ba9395-4381-4fbf-8921-6f98d128f3ae",
    } as const;
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input.toString();
      const method = input instanceof Request ? input.method : (init?.method ?? "GET");
      if (url.includes("/api/v1/session")) return Promise.resolve(jsonResponse(adminSession));
      if (url.includes(`/api/v1/visits/${visitFixture.id}`) && method === "GET") {
        return Promise.resolve(jsonResponse(visitFixture));
      }
      if (url.includes("/api/v1/calendar") && method === "GET") {
        return Promise.resolve(jsonResponse(calendarFixture));
      }
      if (url.includes("/api/v1/appointments/availability") && method === "GET") {
        return Promise.resolve(jsonResponse(availabilityFixture));
      }
      if (url.endsWith("/finish") && method === "POST") {
        return Promise.resolve(jsonResponse(finishResponse, 201));
      }
      if (url.includes("/api/v1/services") && method === "GET") {
        return Promise.resolve(jsonResponse({ services: [clinicService] }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    renderApp(`/visits/${visitFixture.id}`);
    await openFinishStep();

    expect(screen.getByText("Послуги та сума")).toBeInTheDocument();
    expect(screen.getByText("0 партій")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Рекомендації пацієнту/), {
      target: { value: "Щоденний домашній догляд" },
    });
    fireEvent.click(screen.getByLabelText(/Записати на наступний прийом/));
    fireEvent.change(screen.getByLabelText("Дата"), { target: { value: "2026-07-27" } });
    await screen.findByRole("option", { name: "11:00–11:45" });
    fireEvent.change(screen.getByLabelText("Вільний час"), {
      target: { value: availabilityFixture.slots[0].starts_at },
    });
    fireEvent.click(screen.getByLabelText(/Підтверджую підсумок прийому/));
    fireEvent.click(screen.getByRole("button", { name: "Завершити й передати на оплату" }));

    expect(await screen.findByRole("heading", { name: "Передано ресепшну на оплату" }))
      .toBeInTheDocument();
    expect(screen.getByText("Очікує повної оплати")).toBeInTheDocument();
    expect(screen.getByText("Оплату ще не проведено: це окрема касова дія наступного пакета."))
      .toBeInTheDocument();
    const finishRequest = fetchMock.mock.calls
      .map(([input]) => input)
      .find((input): input is Request => input instanceof Request && input.url.endsWith("/finish"));
    if (finishRequest === undefined) throw new Error("Expected a visit finish request.");
    expect(finishRequest.headers.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
    expect(finishRequest.headers.get("X-CSRFToken")).toBe("test-csrf");
    expect(await finishRequest.clone().json()).toEqual({
      version: visitFixture.version,
      recommendations: "Щоденний домашній догляд",
      payment_handoff_requested: true,
      follow_up: {
        starts_at: availabilityFixture.slots[0].starts_at,
        service_id: clinicService.id,
        specialist_id: visitFixture.specialist.id,
        room_id: clinicRoom.id,
      },
    });
  });

  it("refreshes availability and requires confirmation again after a slot conflict", async () => {
    let finishAttempts = 0;
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input.toString();
      const method = input instanceof Request ? input.method : (init?.method ?? "GET");
      if (url.includes("/api/v1/session")) return Promise.resolve(jsonResponse(adminSession));
      if (url.includes(`/api/v1/visits/${visitFixture.id}`) && method === "GET") {
        return Promise.resolve(jsonResponse(visitFixture));
      }
      if (url.includes("/api/v1/calendar")) return Promise.resolve(jsonResponse(calendarFixture));
      if (url.includes("/api/v1/appointments/availability")) {
        return Promise.resolve(jsonResponse(availabilityFixture));
      }
      if (url.endsWith("/finish") && method === "POST") {
        finishAttempts += 1;
        return Promise.resolve(jsonResponse({
          ...anonymousProblem,
          code: "appointment_slot_conflict",
          message: "Спеціаліст уже має запис у цей час.",
          fields: { "follow_up.starts_at": ["Час спеціаліста вже зайнятий."] },
        }, 409));
      }
      return Promise.resolve(jsonResponse({ services: [clinicService] }));
    });
    renderApp(`/visits/${visitFixture.id}`);
    await openFinishStep();
    fireEvent.click(screen.getByLabelText(/Записати на наступний прийом/));
    fireEvent.change(screen.getByLabelText("Дата"), { target: { value: "2026-07-27" } });
    await screen.findByRole("option", { name: "11:00–11:45" });
    fireEvent.change(screen.getByLabelText("Вільний час"), {
      target: { value: availabilityFixture.slots[0].starts_at },
    });
    fireEvent.click(screen.getByLabelText(/Підтверджую підсумок прийому/));
    fireEvent.click(screen.getByRole("button", { name: "Завершити й передати на оплату" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("вікно вже зайняли");
    expect(screen.getByLabelText(/Підтверджую підсумок прийому/)).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Завершити й передати на оплату" })).toBeDisabled();
    expect(finishAttempts).toBe(1);
    const availabilityCalls = fetchMock.mock.calls.filter(([input]) =>
      input instanceof Request && input.url.includes("/appointments/availability"));
    expect(availabilityCalls.length).toBeGreaterThanOrEqual(2);
  });
});

describe("TP-603 private visit photos", () => {
  const openPhotoStep = async () => {
    await screen.findByRole("heading", { name: visitFixture.patient.display_name, level: 1 });
    fireEvent.click(screen.getByRole("button", { name: "Далі: послуги й матеріали" }));
    fireEvent.click(screen.getByRole("button", { name: "Далі: фото" }));
    await screen.findByRole("heading", { name: "Фото до та після процедури", level: 2 });
  };

  it("keeps BEFORE and AFTER photos in separate visit-scoped blocks", async () => {
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
    renderApp(`/visits/${visitFixture.id}`);
    await openPhotoStep();

    expect(screen.getByRole("heading", { name: "До процедури", level: 3 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Після процедури", level: 3 })).toBeInTheDocument();
    expect(screen.getByText(visitPhotoBeforeFixture.original_name)).toBeInTheDocument();
    expect(screen.getByText(visitPhotoAfterFixture.original_name)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "До процедури, фото 1" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Після процедури, фото 1" })).toBeInTheDocument();
    expect(screen.getByText("Готуємо мініатюру…")).toBeInTheDocument();
    expect(screen.getByText("Приватні медичні дані")).toBeInTheDocument();

    const beforeTrigger = screen.getByRole("button", {
      name: `Відкрити до процедури 1: ${visitPhotoBeforeFixture.original_name} у слайдері`,
    });
    fireEvent.click(beforeTrigger);
    const viewer = screen.getByRole("dialog", { name: "Перегляд фото" });
    expect(within(viewer).getByRole("button", { name: "Закрити перегляд фото" })).toHaveFocus();
    expect(within(viewer).getByRole("img", {
      name: `До процедури: ${visitPhotoBeforeFixture.original_name}`,
    })).toHaveAttribute("src", visitPhotoBeforeFixture.image_url);
    expect(within(viewer).getByText("1 із 2")).toBeInTheDocument();

    fireEvent.click(within(viewer).getByRole("button", { name: "Наступне фото" }));
    expect(within(viewer).getByRole("img", {
      name: `Після процедури: ${visitPhotoAfterFixture.original_name}`,
    })).toHaveAttribute("src", visitPhotoAfterFixture.image_url);
    expect(within(viewer).getByText("2 із 2")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "ArrowLeft" });
    expect(within(viewer).getByText("1 із 2")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Перегляд фото" })).not.toBeInTheDocument();
      expect(beforeTrigger).toHaveFocus();
    });
  });

  it("creates an intent and finalizes a canonical photo in the chosen BEFORE block", async () => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
    const uploadedPhoto = {
      ...visitPhotoBeforeFixture,
      id: "51ca3b14-26f8-4832-912b-b9325131bf24",
      original_name: "new-before.jpg",
      preview_status: "PROCESSING",
      preview_url: null,
    } as const;
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input.toString();
      const method = input instanceof Request ? input.method : (init?.method ?? "GET");
      const path = new URL(url).pathname;
      if (url.includes("/api/v1/session")) return Promise.resolve(jsonResponse(adminSession));
      if (path === `/api/v1/visits/${visitFixture.id}` && method === "GET") {
        return Promise.resolve(jsonResponse(visitFixture));
      }
      if (path.endsWith("/photos/upload-intents") && method === "POST") {
        return Promise.resolve(jsonResponse({
          id: "3e536598-3a84-47e4-a63f-d4a34fe8ebbd",
          visit_id: visitFixture.id,
          kind: "BEFORE",
          expires_at: "2026-07-21T09:12:00Z",
          max_bytes: 10 * 1024 * 1024,
          allowed_content_types: ["image/jpeg", "image/png", "image/webp"],
          finalize_url: `/api/v1/visits/${visitFixture.id}/photos`,
        }, 201));
      }
      if (path.endsWith("/photos") && method === "POST") {
        return Promise.resolve(jsonResponse(uploadedPhoto, 201));
      }
      if (url.includes("/api/v1/services") && method === "GET") {
        return Promise.resolve(jsonResponse({ services: [clinicService] }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    renderApp(`/visits/${visitFixture.id}`);
    await openPhotoStep();

    const file = new File([new Uint8Array([255, 216, 255, 217])], "new-before.jpg", {
      type: "image/jpeg",
    });
    fireEvent.change(screen.getByLabelText("Файл для блоку «До процедури»"), {
      target: { files: [file] },
    });

    expect(await screen.findByText("Фото new-before.jpg додано до приватної чернетки."))
      .toBeInTheDocument();
    expect(screen.getByRole("img", { name: "До процедури, фото 1" })).toBeInTheDocument();
    const intentRequest = fetchMock.mock.calls
      .map(([input]) => input)
      .find((input): input is Request => input instanceof Request && input.url.endsWith("/photos/upload-intents"));
    const finalizeRequest = fetchMock.mock.calls
      .map(([input]) => input)
      .find((input): input is Request => input instanceof Request && input.url.endsWith("/photos"));
    if (intentRequest === undefined || finalizeRequest === undefined) {
      throw new Error("Expected visit photo intent and finalize requests.");
    }
    expect(await intentRequest.clone().json()).toEqual({ kind: "BEFORE" });
    const multipartBody = await finalizeRequest.clone().text();
    expect(multipartBody).toContain('name="intent_id"');
    expect(multipartBody).toContain("3e536598-3a84-47e4-a63f-d4a34fe8ebbd");
    expect(multipartBody).toContain('name="photo"');
    expect(multipartBody).toContain("Content-Type: image/jpeg");
    expect(finalizeRequest.headers.get("X-CSRFToken")).toBe("test-csrf");
  });

  it("reuses the same intent for a safe retry after a lost response", async () => {
    const fetchMock = vi.mocked(fetch);
    let finalizeAttempts = 0;
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input.toString();
      const method = input instanceof Request ? input.method : (init?.method ?? "GET");
      const path = new URL(url).pathname;
      if (url.includes("/api/v1/session")) return Promise.resolve(jsonResponse(adminSession));
      if (path === `/api/v1/visits/${visitFixture.id}` && method === "GET") {
        return Promise.resolve(jsonResponse(visitFixture));
      }
      if (path.endsWith("/photos/upload-intents") && method === "POST") {
        return Promise.resolve(jsonResponse({
          id: "8da38fc6-f0ac-4f48-8964-85b7d45004f2",
          visit_id: visitFixture.id,
          kind: "AFTER",
          expires_at: "2026-07-21T09:12:00Z",
          max_bytes: 10 * 1024 * 1024,
          allowed_content_types: ["image/jpeg", "image/png", "image/webp"],
          finalize_url: `/api/v1/visits/${visitFixture.id}/photos`,
        }, 201));
      }
      if (path.endsWith("/photos") && method === "POST") {
        finalizeAttempts += 1;
        return finalizeAttempts === 1
          ? Promise.reject(new TypeError("connection lost"))
          : Promise.resolve(jsonResponse(visitPhotoAfterFixture, 200));
      }
      if (url.includes("/api/v1/services") && method === "GET") {
        return Promise.resolve(jsonResponse({ services: [clinicService] }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    renderApp(`/visits/${visitFixture.id}`);
    await openPhotoStep();
    fireEvent.change(screen.getByLabelText("Файл для блоку «Після процедури»"), {
      target: { files: [new File(["webp"], "after-procedure.webp", { type: "image/webp" })] },
    });

    expect(await screen.findByText("Відповідь сервера втрачено. Безпечний повтор не створить дубль."))
      .toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Повторити" }));
    expect(await screen.findByRole("img", { name: "Після процедури, фото 1" }))
      .toBeInTheDocument();
    expect(finalizeAttempts).toBe(2);
    expect(fetchMock.mock.calls.filter(([input]) => input instanceof Request && input.url.endsWith("/photos/upload-intents"))).toHaveLength(1);
  });

  it("rejects HEIC before transmission and requires confirmation before draft delete", async () => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = input instanceof Request ? input.url : input.toString();
      const method = input instanceof Request ? input.method : (init?.method ?? "GET");
      const path = new URL(url).pathname;
      if (url.includes("/api/v1/session")) return Promise.resolve(jsonResponse(adminSession));
      if (path === `/api/v1/visits/${visitFixture.id}` && method === "GET") {
        return Promise.resolve(jsonResponse({ ...visitFixture, photos: [visitPhotoBeforeFixture] }));
      }
      if (path.endsWith(`/photos/${visitPhotoBeforeFixture.id}`) && method === "DELETE") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (url.includes("/api/v1/services") && method === "GET") {
        return Promise.resolve(jsonResponse({ services: [clinicService] }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    renderApp(`/visits/${visitFixture.id}`);
    await openPhotoStep();

    fireEvent.change(screen.getByLabelText("Файл для блоку «Після процедури»"), {
      target: { files: [new File(["heic"], "unsupported.heic", { type: "image/heic" })] },
    });
    expect(screen.getByRole("alert")).toHaveTextContent("HEIC/HEIF");
    expect(fetchMock.mock.calls.some(([input]) => input instanceof Request && input.url.endsWith("/photos/upload-intents"))).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: `Видалити фото ${visitPhotoBeforeFixture.original_name}` }));
    expect(screen.getByText("Видалити фото з чернетки?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Так, видалити" }));
    await waitFor(() => {
      expect(screen.queryByRole("img", { name: "До процедури, фото 1" })).not.toBeInTheDocument();
    });
    const deleteRequest = fetchMock.mock.calls
      .map(([input]) => input)
      .find((input): input is Request => input instanceof Request && input.method === "DELETE");
    if (deleteRequest === undefined) throw new Error("Expected a photo delete request.");
    expect(deleteRequest.headers.get("X-CSRFToken")).toBe("test-csrf");
  });
});

describe("TP-301 patient directory", () => {
  it("renders the safe patient directory and role scope", async () => {
    renderApp("/patients");

    expect(await screen.findByRole("heading", { name: "Каталог пацієнтів" })).toBeInTheDocument();
    expect(await screen.findByText("Марія Бондар")).toBeInTheDocument();
    expect(screen.getByText("P-C49D72C2689D")).toBeInTheDocument();
    expect(screen.getByText("Усі пацієнти кабінету")).toBeInTheDocument();
    expect(screen.getByText("Записів ще немає")).toBeInTheDocument();
    expect(screen.queryByText(/медичн/i)).not.toBeInTheDocument();
  });

  it("shows the own-patient scope for a podologist session", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(podologistSession))
      .mockResolvedValueOnce(jsonResponse({ patients: [patientFixture], next_cursor: null }));
    renderApp("/patients");

    expect(await screen.findByText("Лише мої пацієнти")).toBeInTheDocument();
    expect(screen.getByText("Доступ: Подолог")).toBeInTheDocument();
  });

  it("updates live search results and offers inline create for an empty result", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse({ patients: [patientFixture], next_cursor: null }))
      .mockResolvedValueOnce(jsonResponse({ patients: [], next_cursor: null }));
    renderApp("/patients");
    await screen.findByText("Марія Бондар");

    fireEvent.change(screen.getByRole("searchbox", { name: "Пошук пацієнтів" }), {
      target: { value: "Невідома людина" },
    });

    expect(await screen.findByRole("heading", { name: "Збігів не знайдено" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Створити пацієнта" })).toBeInTheDocument();
    const searchRequest = fetchMock.mock.calls.at(-1)?.[0];
    expect(searchRequest).toBeInstanceOf(Request);
    expect((searchRequest as Request).url).toContain("search=%D0%9D%D0%B5%D0%B2%D1%96%D0%B4%D0%BE%D0%BC%D0%B0");
  });

  it("guards unsaved create fields before closing", async () => {
    renderApp("/patients");
    await screen.findByText("Марія Бондар");
    fireEvent.click(screen.getByRole("button", { name: "Додати пацієнта" }));
    fireEvent.change(screen.getByLabelText("Ім’я"), { target: { value: "Олена" } });
    fireEvent.click(screen.getByRole("button", { name: "Закрити форму пацієнта" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Відкинути введені дані?");
    fireEvent.click(screen.getByRole("button", { name: "Продовжити" }));
    expect(screen.getByRole("heading", { name: "Новий пацієнт" })).toBeInTheDocument();
    expect(screen.getByDisplayValue("Олена")).toBeInTheDocument();
  });

  it("warns about a duplicate phone and still creates the patient", async () => {
    const fetchMock = vi.mocked(fetch);
    const createdPatient = {
      ...patientFixture,
      id: "97fcff39-a069-48f7-99f2-d9e3a45a7f8e",
      public_number: "P-97FCFF39A069",
      first_name: "Марина",
      last_name: "Коваль",
      display_name: "Марина Коваль",
      note: "",
      updated_at: "2026-07-21T12:05:00+03:00",
    } as const;
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse({ patients: [patientFixture], next_cursor: null }))
      .mockResolvedValueOnce(jsonResponse({ patients: [patientFixture], next_cursor: null }))
      .mockResolvedValueOnce(jsonResponse({
        patient: createdPatient,
        duplicate_warning: true,
        possible_duplicates: [patientFixture],
      }, 201))
      .mockResolvedValueOnce(jsonResponse({ patients: [createdPatient, patientFixture], next_cursor: null }));
    renderApp("/patients");
    await screen.findByText("Марія Бондар");
    fireEvent.click(screen.getByRole("button", { name: "Додати пацієнта" }));
    fireEvent.change(screen.getByLabelText("Ім’я"), { target: { value: "Марина" } });
    fireEvent.change(screen.getByLabelText("Прізвище"), { target: { value: "Коваль" } });
    fireEvent.change(screen.getByLabelText("Телефон"), { target: { value: "0671234567" } });

    expect(await screen.findByText("Можливий дублікат телефону")).toBeInTheDocument();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Створити пацієнта" }));

    expect(await screen.findByRole("status")).toHaveTextContent("можливий дублікат телефону");
    expect(await screen.findByText("Марина Коваль")).toBeInTheDocument();
    const createRequest = fetchMock.mock.calls.find(([input]) => input instanceof Request && input.method === "POST")?.[0];
    expect(createRequest).toBeInstanceOf(Request);
    expect(await (createRequest as Request).clone().json()).toMatchObject({
      first_name: "Марина",
      last_name: "Коваль",
      phone: "0671234567",
    });
  });

  it("appends the next cursor page without replacing current results", async () => {
    const secondPatient = {
      ...patientFixture,
      id: "a5dacb1f-bcab-4785-83e9-9ce6af32e52f",
      public_number: "P-A5DACB1FBCAB",
      first_name: "Ірина",
      last_name: "Савчук",
      display_name: "Ірина Савчук",
      phone: "+380 50 222 33 44",
    } as const;
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse({ patients: [patientFixture], next_cursor: "next-page" }))
      .mockResolvedValueOnce(jsonResponse({ patients: [secondPatient], next_cursor: null }));
    renderApp("/patients");
    await screen.findByText("Марія Бондар");

    fireEvent.click(screen.getByRole("button", { name: "Показати ще" }));

    expect(await screen.findByText("Ірина Савчук")).toBeInTheDocument();
    expect(screen.getByText("Марія Бондар")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Показати ще" })).not.toBeInTheDocument();
  });
});

describe("TP-302 patient card and role projections", () => {
  const detailPath = `/patients/${patientFixture.id}/overview`;

  it("opens a directory row and renders the medical overview shells", async () => {
    renderApp("/patients");
    await screen.findByText("Марія Бондар");

    fireEvent.click(screen.getByRole("link", { name: "Відкрити картку Марія Бондар" }));

    expect(await screen.findByRole("heading", { name: "Марія Бондар", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("Латекс")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Історія візитів" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Фото до / після" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Рекомендації" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Історія візитів" }));
    expect(await screen.findByRole("heading", { name: "Історія візитів" })).toBeInTheDocument();
    expect(await screen.findByText("Шкіра спокійна, загоєння без ускладнень.")).toBeInTheDocument();
  });

  it("renders the reception-safe projection without medical or photo content", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(receptionSession))
      .mockResolvedValueOnce(jsonResponse(receptionPatientDetailFixture));
    renderApp(detailPath);

    expect(await screen.findByRole("heading", { name: "Марія Бондар", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Медичні блоки мають обмежений доступ" })).toBeInTheDocument();
    expect(screen.queryByText("Латекс")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Фото до / після" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Рекомендації" })).not.toBeInTheDocument();
  });

  it("updates safe and medical fields through the typed PATCH contract", async () => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
    const updated = {
      ...medicalPatientDetailFixture,
      phone: "+380 50 111 22 33",
      medical_profile: {
        ...medicalPatientDetailFixture.medical_profile,
        allergies: ["Латекс", "Йод"],
      },
    } as const;
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse(medicalPatientDetailFixture))
      .mockResolvedValueOnce(jsonResponse(updated));
    renderApp(detailPath);
    await screen.findByRole("heading", { name: "Марія Бондар", level: 1 });

    fireEvent.click(screen.getByRole("button", { name: "Редагувати" }));
    fireEvent.change(screen.getByLabelText("Телефон"), { target: { value: "050 111 22 33" } });
    fireEvent.change(screen.getByLabelText("Алергії"), { target: { value: "Латекс, Йод" } });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти зміни" }));

    expect(await screen.findByRole("status")).toHaveTextContent("зафіксовано в журналі дій");
    expect(screen.getByText("Латекс, Йод")).toBeInTheDocument();
    const patchRequest = fetchMock.mock.calls.find(([input]) => input instanceof Request && input.method === "PATCH")?.[0];
    expect(patchRequest).toBeInstanceOf(Request);
    expect((patchRequest as Request).headers.get("X-CSRFToken")).toBe("test-csrf");
    expect(await (patchRequest as Request).clone().json()).toMatchObject({
      phone: "050 111 22 33",
      medical_profile: { allergies: ["Латекс", "Йод"] },
    });
    document.cookie = "podoria_csrftoken=; max-age=0; path=/";
  });

  it("guards unsaved patient edits before closing", async () => {
    renderApp(detailPath);
    await screen.findByRole("heading", { name: "Марія Бондар", level: 1 });
    fireEvent.click(screen.getByRole("button", { name: "Редагувати" }));
    fireEvent.change(screen.getByLabelText("Адміністративна нотатка"), { target: { value: "Незбережена зміна" } });
    fireEvent.click(screen.getByRole("button", { name: "Закрити редагування" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Є незбережені зміни");
    fireEvent.click(screen.getByRole("button", { name: "Продовжити" }));
    expect(screen.getByDisplayValue("Незбережена зміна")).toBeInTheDocument();
  });

  it("shows the same safe not-found state for an inaccessible patient id", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(podologistSession))
      .mockResolvedValueOnce(jsonResponse({
        code: "not_found",
        message: "Ресурс не знайдено.",
        fields: {},
        correlation_id: "test-request",
      }, 404));
    renderApp("/patients/00000000-0000-4000-8000-000000000999/overview");

    expect(await screen.findByRole("heading", { name: "Картку пацієнта не знайдено" })).toBeInTheDocument();
    expect(screen.getByText(/не існує або недоступний/)).toBeInTheDocument();
  });
});

describe("TP-303 internal work items", () => {
  it("renders the live work-item summary and safe linked-patient projection", async () => {
    renderApp("/work-items");

    expect(await screen.findByRole("heading", { name: "Внутрішні справи" })).toBeInTheDocument();
    expect(await screen.findByText("Уточнити самопочуття після візиту")).toBeInTheDocument();
    expect(screen.getByText("Відповідальний: Тест Адміністратор")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Марія Бондар/ })).toHaveAttribute(
      "href",
      `/patients/${patientFixture.id}/overview`,
    );
    expect(screen.getByRole("button", { name: "Усі команди" })).toBeInTheDocument();
  });

  it("requests all-team scope for an administrator", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse(workItemListFixture))
      .mockResolvedValueOnce(jsonResponse({ ...workItemListFixture, effective_scope: "all" }));
    renderApp("/work-items");
    await screen.findByText("Уточнити самопочуття після візиту");

    fireEvent.click(screen.getByRole("button", { name: "Усі команди" }));

    await waitFor(() => {
      const request = fetchMock.mock.calls.at(-1)?.[0];
      expect(request).toBeInstanceOf(Request);
      expect((request as Request).url).toContain("scope=all");
    });
  });

  it("locks a podologist to own scope even if the server normalizes it", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(podologistSession))
      .mockResolvedValueOnce(jsonResponse(workItemListFixture));
    renderApp("/work-items");

    expect(await screen.findByText("Лише мої справи")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Усі команди" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Telegram-сповіщення" })).toBeInTheDocument();
  });

  it("creates an internal work item with CSRF protection", async () => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
    const fetchMock = vi.mocked(fetch);
    const created = { ...workItemFixture, kind: "other", kind_label: "Інша справа", title: "Підготувати документи" } as const;
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse(workItemListFixture))
      .mockResolvedValueOnce(jsonResponse(created, 201))
      .mockResolvedValueOnce(jsonResponse({ ...workItemListFixture, work_items: [created] }));
    renderApp("/work-items");
    await screen.findByText("Уточнити самопочуття після візиту");
    fireEvent.click(screen.getByRole("button", { name: "Нова справа" }));
    const dialog = screen.getByRole("dialog", { name: "Нова справа" });
    fireEvent.change(within(dialog).getByLabelText("Назва"), { target: { value: "Підготувати документи" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Створити справу" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Підготувати документи");
    const createRequest = fetchMock.mock.calls.find(([input]) => input instanceof Request && input.method === "POST")?.[0];
    expect(createRequest).toBeInstanceOf(Request);
    expect((createRequest as Request).headers.get("X-CSRFToken")).toBe("test-csrf");
    expect(await (createRequest as Request).clone().json()).toMatchObject({
      title: "Підготувати документи",
      assignee_id: 1,
      kind: "other",
      patient_id: null,
    });
    document.cookie = "podoria_csrftoken=; max-age=0; path=/";
  });

  it("completes a work item explicitly with its current version", async () => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse(workItemListFixture))
      .mockResolvedValueOnce(jsonResponse({
        ...workItemFixture,
        is_completed: true,
        completed_at: "2026-07-21T13:00:00+03:00",
        completed_by: workItemFixture.assignee,
        version: 2,
      }));
    renderApp("/work-items");
    await screen.findByText("Уточнити самопочуття після візиту");

    fireEvent.click(screen.getByRole("button", { name: /Позначити виконаною/ }));

    expect(await screen.findByRole("status")).toHaveTextContent("виконано");
    const patchRequest = fetchMock.mock.calls.find(([input]) => input instanceof Request && input.method === "PATCH")?.[0];
    expect(patchRequest).toBeInstanceOf(Request);
    expect((patchRequest as Request).headers.get("X-CSRFToken")).toBe("test-csrf");
    expect(await (patchRequest as Request).clone().json()).toEqual({ version: 1, is_completed: true });
    document.cookie = "podoria_csrftoken=; max-age=0; path=/";
  });

  it("creates a callback from the patient card without triggering a call", async () => {
    const fetchMock = vi.mocked(fetch);
    const callback = { ...workItemFixture, title: "Перетелефонувати: Марія Бондар" } as const;
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse(medicalPatientDetailFixture))
      .mockResolvedValueOnce(jsonResponse(workItemListFixture))
      .mockResolvedValueOnce(jsonResponse(callback, 201));
    renderApp(`/patients/${patientFixture.id}/overview`);
    await screen.findByRole("heading", { name: "Марія Бондар", level: 1 });
    fireEvent.click(screen.getByRole("button", { name: "Перетелефонувати" }));

    const dialog = await screen.findByRole("dialog", { name: "Нова справа" });
    expect(within(dialog).getByText(`${patientFixture.public_number} · ${patientFixture.phone}`)).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Створити справу" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Автоматичний дзвінок не виконувався");
    const createRequest = fetchMock.mock.calls.find(([input]) => input instanceof Request && input.method === "POST")?.[0];
    expect(await (createRequest as Request).clone().json()).toMatchObject({
      kind: "callback",
      patient_id: patientFixture.id,
    });
  });
});

describe("session boundary and role-safe routes", () => {
  it("replaces the finance preview with the reception-safe current cash shift", async () => {
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(receptionSession));
      if (url.pathname === "/api/v1/cash-shifts/current") return Promise.resolve(jsonResponse({ shift: cashShiftFixture }));
      if (url.pathname === "/api/v1/finance/operations") return Promise.resolve(jsonResponse(financeOperationsFixture));
      return Promise.resolve(jsonResponse({ code: "not_found", message: "Not found", fields: {}, correlation_id: "finance-route" }, 404));
    });
    renderApp("/finance");

    expect(await screen.findByRole("heading", { name: "Оплати та каса" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Поточна касова зміна" })).toBeInTheDocument();
    expect(screen.queryByText("Модуль · preview")).not.toBeInTheDocument();
  });

  it("redirects a podologist away from the direct finance URL", async () => {
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/session") return Promise.resolve(jsonResponse(podologistSession));
      if (path === "/api/v1/overview") return Promise.resolve(jsonResponse(overviewFixture));
      if (path === "/api/v1/work-items") return Promise.resolve(jsonResponse(workItemListFixture));
      return Promise.resolve(jsonResponse({ code: "not_found", message: "Not found", fields: {}, correlation_id: "role-route" }, 404));
    });
    renderApp("/finance");

    expect(await screen.findByRole("heading", { name: "Добрий день" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Цей розділ недоступний");
    expect(screen.queryByRole("link", { name: "Фінанси" })).not.toBeInTheDocument();
  });

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
    expect(await screen.findByRole("heading", { name: "Склад і матеріали" })).toBeInTheDocument();
  });

  it("redirects a forbidden direct URL and hides unavailable navigation", async () => {
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/session") return Promise.resolve(jsonResponse(receptionSession));
      if (path === "/api/v1/overview") return Promise.resolve(jsonResponse(overviewFixture));
      if (path === "/api/v1/work-items") return Promise.resolve(jsonResponse(workItemListFixture));
      return Promise.resolve(jsonResponse({ code: "not_found", message: "Not found", fields: {}, correlation_id: "role-route" }, 404));
    });
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
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (path === "/api/v1/overview") return Promise.resolve(jsonResponse(overviewFixture));
      if (path === "/api/v1/work-items") return Promise.resolve(jsonResponse(workItemListFixture));
      if (path === "/api/v1/auth/change-password") {
        return Promise.resolve(jsonResponse({
          ...adminSession,
          user: { ...adminSession.user, display_name: "Тест Адміністратор" },
        }));
      }
      return Promise.resolve(jsonResponse({ code: "not_found", message: "Not found", fields: {}, correlation_id: "password-change" }, 404));
    });
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

  it("generates the first booking-request API token and clears it on dialog close", async () => {
    const fetchMock = vi.mocked(fetch);
    const token = "podo_br_example-one-time-token";
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse(clinicProfile))
      .mockResolvedValueOnce(jsonResponse({ rooms: [clinicRoom] }))
      .mockResolvedValueOnce(jsonResponse({
        is_configured: false,
        token_hint: "",
        rotated_at: null,
        rotated_by_display_name: "",
        version: 0,
      }))
      .mockResolvedValueOnce(jsonResponse({
        is_configured: true,
        token_hint: "token",
        rotated_at: "2026-07-28T10:00:00Z",
        rotated_by_display_name: "Тест Адміністратор",
        version: 1,
        token,
      }));
    renderApp("/settings");

    await screen.findByRole("heading", { name: "Налаштування кабінету" });
    fireEvent.click(screen.getByTestId("settings-integrations-tab"));
    expect(await screen.findByRole("heading", { name: "API заявок на запис" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Згенерувати токен" }));

    const dialog = await screen.findByRole("dialog", { name: "Новий API-токен" });
    expect(within(dialog).getByDisplayValue(token)).toBeInTheDocument();
    const rotateRequest = fetchMock.mock.calls.at(-1)?.[0];
    expect(rotateRequest).toBeInstanceOf(Request);
    expect(await (rotateRequest as Request).clone().json()).toEqual({ version: 0, confirm: true });
    fireEvent.click(within(dialog).getByRole("button", { name: "Я зберіг токен" }));

    expect(screen.queryByDisplayValue(token)).not.toBeInTheDocument();
    expect(screen.getByText("••••••token")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Згенерувати новий" })).toHaveFocus();
    });
  });

  it("warns before token rotation and supports one-time clipboard copy", async () => {
    const fetchMock = vi.mocked(fetch);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const token = "podo_br_rotated-example-token";
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse(clinicProfile))
      .mockResolvedValueOnce(jsonResponse({ rooms: [clinicRoom] }))
      .mockResolvedValueOnce(jsonResponse({
        is_configured: true,
        token_hint: "before",
        rotated_at: "2026-07-28T09:00:00Z",
        rotated_by_display_name: "Тест Адміністратор",
        version: 2,
      }))
      .mockResolvedValueOnce(jsonResponse({
        is_configured: true,
        token_hint: "token",
        rotated_at: "2026-07-28T10:00:00Z",
        rotated_by_display_name: "Тест Адміністратор",
        version: 3,
        token,
      }));
    renderApp("/settings");

    await screen.findByRole("heading", { name: "Налаштування кабінету" });
    fireEvent.click(screen.getByTestId("settings-integrations-tab"));
    await screen.findByRole("heading", { name: "API заявок на запис" });
    fireEvent.click(screen.getByRole("button", { name: "Згенерувати новий" }));
    const confirmation = screen.getByRole("alertdialog", { name: "Згенерувати новий токен?" });
    expect(confirmation).toHaveTextContent("Поточний токен припинить діяти негайно");
    expect(fetchMock).toHaveBeenCalledTimes(4);
    fireEvent.click(within(confirmation).getByRole("button", { name: "Згенерувати новий" }));

    const dialog = await screen.findByRole("dialog", { name: "Новий API-токен" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Копіювати токен" }));
    expect(await within(dialog).findByRole("status")).toHaveTextContent("Токен скопійовано");
    expect(writeText).toHaveBeenCalledWith(token);
    fireEvent.click(within(dialog).getByRole("button", { name: "Я зберіг токен" }));
    expect(screen.queryByDisplayValue(token)).not.toBeInTheDocument();
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
    await within(screen.getByTestId("settings-rooms-tab")).findByText("1 активних");
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
    await within(screen.getByTestId("settings-rooms-tab")).findByText("1 активних");
    fireEvent.click(screen.getByTestId("settings-services-tab"));
    await screen.findByText("Первинна консультація");
    fireEvent.click(screen.getByRole("button", { name: "Редагувати Первинна консультація" }));
    fireEvent.click(screen.getByRole("button", { name: "Зберегти зміни" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Послуга з таким кодом уже існує");
    expect(screen.getByRole("heading", { name: "Редагувати послугу" })).toBeInTheDocument();
    expect(screen.getByText("Укажіть інший унікальний код послуги.")).toBeInTheDocument();
    expect(screen.getByDisplayValue("CONSULT")).toBeInTheDocument();
  });

  it("edits one of eight protected status configs without exposing the system code", async () => {
    const fetchMock = vi.mocked(fetch);
    const arrived = clinicStatuses.find((item) => item.code === "ARRIVED");
    if (arrived === undefined) throw new Error("ARRIVED fixture is missing");
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse(clinicProfile))
      .mockResolvedValueOnce(jsonResponse({ rooms: [clinicRoom] }))
      .mockResolvedValueOnce(jsonResponse({ statuses: clinicStatuses }))
      .mockResolvedValueOnce(jsonResponse({
        ...arrived,
        label: "У клініці",
        manual_reception: false,
        version: 2,
      }));
    renderApp("/settings");

    await screen.findByRole("heading", { name: "Налаштування кабінету" });
    fireEvent.click(screen.getByTestId("settings-statuses-tab"));
    expect(await screen.findByRole("heading", { name: "Системні статуси" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Налаштувати / })).toHaveLength(8);
    fireEvent.click(screen.getByRole("button", { name: "Налаштувати Пацієнт прийшов" }));
    expect(screen.getByText("Системний код · ARRIVED")).toBeInTheDocument();
    expect(screen.queryByLabelText("Код статусу")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Зрозуміла назва"), { target: { value: "У клініці" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /Рецепція/ }));
    expect(screen.getByRole("status")).toHaveTextContent("Є незбережені зміни");
    fireEvent.click(screen.getByRole("button", { name: "Зберегти статус" }));

    expect(await screen.findByText("Статус «У клініці» збережено.")).toBeInTheDocument();
    const updateRequest = fetchMock.mock.calls.at(-1)?.[0];
    expect(updateRequest).toBeInstanceOf(Request);
    const body: unknown = await (updateRequest as Request).clone().json();
    expect(body).toMatchObject({ label: "У клініці", manual_reception: false, version: 1 });
    expect(body).not.toHaveProperty("code");
  });

  it("saves one clinic-wide seven-day schedule and retains server validation", async () => {
    const fetchMock = vi.mocked(fetch);
    const updatedWorkdays = clinicWorkdays.map((item) => item.weekday === 0 ? {
      ...item,
      start_time: "08:30",
      version: 2,
    } : { ...item, version: 2 });
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse(clinicProfile))
      .mockResolvedValueOnce(jsonResponse({ rooms: [clinicRoom] }))
      .mockResolvedValueOnce(jsonResponse({ timezone: "Europe/Kyiv", workdays: clinicWorkdays }))
      .mockResolvedValueOnce(jsonResponse({ timezone: "Europe/Kyiv", workdays: updatedWorkdays }));
    renderApp("/settings");

    await screen.findByRole("heading", { name: "Налаштування кабінету" });
    fireEvent.click(screen.getByTestId("settings-schedule-tab"));
    expect(await screen.findByRole("heading", { name: "Робочий час клініки" })).toBeInTheDocument();
    expect(screen.getByText("Europe/Kyiv")).toBeInTheDocument();
    expect(screen.queryByText(/індивідуальний графік/i)).not.toBeInTheDocument();
    fireEvent.change(await screen.findByLabelText("Понеділок початок"), {
      target: { value: "08:30" },
    });
    expect(screen.getByText("Є незбережені зміни")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Зберегти графік" }));

    expect(await screen.findByText("Єдиний графік клініки збережено.")).toBeInTheDocument();
    const updateRequest = fetchMock.mock.calls.at(-1)?.[0];
    expect(updateRequest).toBeInstanceOf(Request);
    const body: unknown = await (updateRequest as Request).clone().json();
    expect(body).toMatchObject({
      workdays: [
        { weekday: 0, start_time: "08:30", version: 1 },
        { weekday: 1 },
        { weekday: 2 },
        { weekday: 3 },
        { weekday: 4 },
        { weekday: 5 },
        { weekday: 6 },
      ],
    });
    expect(JSON.stringify(body)).not.toMatch(/specialist|holiday|vacation/);
  });

  it("keeps an overlapping-break validation error on the schedule form", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse(adminSession))
      .mockResolvedValueOnce(jsonResponse(clinicProfile))
      .mockResolvedValueOnce(jsonResponse({ rooms: [clinicRoom] }))
      .mockResolvedValueOnce(jsonResponse({ timezone: "Europe/Kyiv", workdays: clinicWorkdays }))
      .mockResolvedValueOnce(jsonResponse({
        ...anonymousProblem,
        code: "validation_error",
        message: "Дані запиту не пройшли перевірку.",
        fields: { "workdays.0.non_field_errors": ["Перерви не можуть накладатися одна на одну."] },
      }, 422));
    renderApp("/settings");

    await screen.findByRole("heading", { name: "Налаштування кабінету" });
    fireEvent.click(screen.getByTestId("settings-schedule-tab"));
    await screen.findByRole("heading", { name: "Робочий час клініки" });
    fireEvent.change(screen.getByLabelText("Понеділок початок"), { target: { value: "08:30" } });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти графік" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Перерви не можуть накладатися");
    expect(screen.getByDisplayValue("08:30")).toBeInTheDocument();
  });
});
