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
  clinicStatuses,
  clinicWorkdays,
  jsonResponse,
  medicalPatientDetailFixture,
  patientFixture,
  podologistSession,
  receptionSession,
  receptionPatientDetailFixture,
  workItemFixture,
  workItemListFixture,
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
    fireEvent.click(screen.getByRole("button", { name: "Історія візитів" }));
    expect(screen.getByRole("heading", { name: "Історія візитів порожня" })).toBeInTheDocument();
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
    fireEvent.change(screen.getByLabelText("Понеділок початок"), { target: { value: "08:30" } });
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
