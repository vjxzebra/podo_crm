import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { App } from "../App";
import {
  adminSession,
  auditEventDetailFixture,
  auditEventFixture,
  auditEventListFixture,
  jsonResponse,
  overviewFixture,
  receptionSession,
} from "../test/setup";

const apiFailure = {
  code: "temporary_failure",
  message: "Сервіс тимчасово недоступний.",
  fields: {},
  correlation_id: "audit-test",
} as const;

function auditCsvResponse(): Response {
  return new Response("\ufeffrow_type,event_count\r\nREPORT_SUMMARY,1\r\n", {
    status: 200,
    headers: {
      "Content-Disposition": 'attachment; filename="audit-events-20260723-100000.csv"',
      "Content-Type": "text/csv; charset=utf-8",
    },
  });
}

const actorFixture = {
  id: 1,
  first_name: "Тест",
  last_name: "Адміністратор",
  display_name: "Тест Адміністратор",
  phone: "+380671112233",
  email: "admin@example.test",
  role: "admin",
  is_active: true,
  must_change_password: false,
  temporary_password_expires_at: null,
  last_login: "2026-07-22T08:00:00Z",
} as const;

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="audit-location">{`${location.pathname}${location.search}`}</output>;
}

function renderAudit(path = "/audit", width = 1024) {
  Object.defineProperty(window, "innerWidth", { configurable: true, value: width });
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
      <LocationProbe />
    </MemoryRouter>,
  );
}

function requestDetails(input: RequestInfo | URL, init?: RequestInit) {
  const request = input instanceof Request ? input : new Request(input, init);
  return { method: request.method, url: new URL(request.url) };
}

describe("admin audit journal", () => {
  it("opens a reload-stable redacted diff and returns focus on close", async () => {
    renderAudit();

    const row = await screen.findByRole("button", { name: /Скасовано запис/ });
    fireEvent.click(row);

    expect(await screen.findByRole("heading", { name: "Скасовано запис", level: 2 })).toBeInTheDocument();
    expect(screen.getByText("Що змінилося")).toBeInTheDocument();
    expect(screen.getAllByText("Було")).toHaveLength(2);
    expect(screen.getByText("CONFIRMED")).toBeInTheDocument();
    expect(screen.getByText("CANCELED")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Відкрити об’єкт/ })).toHaveAttribute(
      "href",
      `/calendar?appointment=${auditEventFixture.object.id}`,
    );
    expect(screen.getByTestId("audit-location")).toHaveTextContent(`/audit?event=${auditEventFixture.id}`);

    fireEvent.click(screen.getByRole("button", { name: "Закрити деталі події" }));
    expect(screen.getByTestId("audit-location")).toHaveTextContent(/^\/audit$/);
    await waitFor(() => { expect(row).toHaveFocus(); });
  });

  it("submits employee, section, date and search filters and resets a filtered empty state", async () => {
    const auditRequests: URL[] = [];
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const { method, url } = requestDetails(input, init);
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (url.pathname === "/api/v1/users") return Promise.resolve(jsonResponse({ users: [actorFixture] }));
      if (url.pathname === "/api/v1/audit-events" && method === "GET") {
        auditRequests.push(url);
        return Promise.resolve(jsonResponse(url.search === "" ? auditEventListFixture : { events: [], next_cursor: null }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    renderAudit();

    await screen.findByRole("button", { name: /Скасовано запис/ });
    fireEvent.change(screen.getByRole("textbox", { name: "Пошук у журналі" }), { target: { value: "Коваль" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Працівник" }), { target: { value: "1" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Розділ журналу" }), { target: { value: "scheduling" } });
    fireEvent.change(screen.getByLabelText("Дата події"), { target: { value: "2026-07-22" } });
    fireEvent.click(screen.getByRole("button", { name: "Застосувати" }));

    expect(await screen.findByRole("heading", { name: "Подій за фільтрами не знайдено" })).toBeInTheDocument();
    const filtered = auditRequests.at(-1);
    expect(filtered?.searchParams.get("search")).toBe("Коваль");
    expect(filtered?.searchParams.get("actor_id")).toBe("1");
    expect(filtered?.searchParams.get("section")).toBe("scheduling");
    expect(filtered?.searchParams.get("date_from")).toContain("2026-07-21T21:00:00.000Z");
    expect(filtered?.searchParams.get("date_to")).toContain("2026-07-22T20:59:59.999Z");

    const resetFilters = screen.getAllByRole("button", { name: "Скинути фільтри" }).at(-1);
    expect(resetFilters).toBeDefined();
    if (resetFilters !== undefined) fireEvent.click(resetFilters);
    expect(await screen.findByRole("button", { name: /Скасовано запис/ })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Пошук у журналі" })).toHaveValue("");
  });

  it("recovers from list failure and appends an older cursor page", async () => {
    const older = {
      ...auditEventFixture,
      id: "80300000-0000-4000-8000-000000000002",
      action: "billing.payment_posted",
      section: "billing",
      object: { type: "payment", id: "70150000-0000-4000-8000-000000000002", label: "Оплата TXN-7016" },
      occurred_at: "2026-07-21T09:00:00Z",
    } as const;
    let listRequests = 0;
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const { method, url } = requestDetails(input, init);
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (url.pathname === "/api/v1/users") return Promise.resolve(jsonResponse({ users: [] }));
      if (url.pathname === "/api/v1/audit-events" && method === "GET") {
        listRequests += 1;
        if (listRequests === 1) return Promise.resolve(jsonResponse(apiFailure, 503));
        if (url.searchParams.get("cursor") !== null) return Promise.resolve(jsonResponse({ events: [older], next_cursor: null }));
        return Promise.resolve(jsonResponse({ ...auditEventListFixture, next_cursor: auditEventFixture.id }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    renderAudit();

    expect(await screen.findByRole("alert")).toHaveTextContent("Сервіс тимчасово недоступний");
    fireEvent.click(screen.getByRole("button", { name: "Повторити" }));
    expect(await screen.findByRole("button", { name: /Скасовано запис/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Показати старіші" }));
    expect(await screen.findByRole("button", { name: /Проведено оплату/ })).toBeInTheDocument();
    await waitFor(() => { expect(screen.queryByRole("button", { name: "Показати старіші" })).not.toBeInTheDocument(); });
  });

  it("retries a detail failure and explains an event without changed fields", async () => {
    let detailRequests = 0;
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const { method, url } = requestDetails(input, init);
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (url.pathname === "/api/v1/users") return Promise.resolve(jsonResponse({ users: [] }));
      if (url.pathname === "/api/v1/audit-events") return Promise.resolve(jsonResponse(auditEventListFixture));
      if (url.pathname === `/api/v1/audit-events/${auditEventFixture.id}` && method === "GET") {
        detailRequests += 1;
        return detailRequests === 1
          ? Promise.resolve(jsonResponse(apiFailure, 503))
          : Promise.resolve(jsonResponse({ ...auditEventDetailFixture, changes: [], description: "", note: "" }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    renderAudit();

    fireEvent.click(await screen.findByRole("button", { name: /Скасовано запис/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Сервіс тимчасово недоступний");
    fireEvent.click(screen.getByRole("button", { name: "Повторити" }));

    expect(await screen.findByText("Змінені поля не зафіксовані")).toBeInTheDocument();
    expect(screen.getByText("Додатковий опис не вказано.")).toBeInTheDocument();
    expect(screen.getByText("Службову примітку не додано.")).toBeInTheDocument();
  });

  it("uses a fullscreen mobile detail with focus trap, Escape and focus return", async () => {
    document.body.style.overflow = "";
    renderAudit(`/audit?event=${auditEventFixture.id}`, 390);

    const close = await screen.findByRole("button", { name: "Закрити деталі події" });
    await screen.findByText("Що змінилося");
    await waitFor(() => { expect(close).toHaveFocus(); });
    expect(document.body.style.overflow).toBe("hidden");

    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(screen.getByRole("link", { name: /Відкрити об’єкт/ })).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.getByTestId("audit-location")).toHaveTextContent(/^\/audit$/);
    expect(document.body.style.overflow).toBe("");
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Скасовано запис/ })).toHaveFocus();
    });
  });

  it("exports only applied filters with pending, server filename and content preservation", async () => {
    let resolveFilteredList: ((response: Response) => void) | undefined;
    let resolveExport: ((response: Response) => void) | undefined;
    let downloadedFilename = "";
    const exportRequests: Request[] = [];
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function captureDownload(this: HTMLAnchorElement) {
        downloadedFilename = this.download;
      });
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (url.pathname === "/api/v1/users") return Promise.resolve(jsonResponse({ users: [actorFixture] }));
      if (url.pathname === "/api/v1/audit-events" && request.method === "GET") {
        if (url.search === "") return Promise.resolve(jsonResponse(auditEventListFixture));
        return new Promise<Response>((resolve) => { resolveFilteredList = resolve; });
      }
      if (url.pathname === "/api/v1/audit-events/export" && request.method === "GET") {
        exportRequests.push(request);
        return new Promise<Response>((resolve) => { resolveExport = resolve; });
      }
      return Promise.resolve(jsonResponse({}));
    });
    renderAudit();

    await screen.findByRole("button", { name: /Скасовано запис/ });
    const exportButton = screen.getByRole("button", { name: "Експортувати CSV" });
    fireEvent.change(screen.getByRole("textbox", { name: "Пошук у журналі" }), { target: { value: "Коваль" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Працівник" }), { target: { value: "1" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Розділ журналу" }), { target: { value: "scheduling" } });
    fireEvent.change(screen.getByLabelText("Дата події"), { target: { value: "2026-07-22" } });
    fireEvent.click(screen.getByRole("button", { name: "Застосувати" }));
    expect(exportButton).toBeDisabled();
    resolveFilteredList?.(jsonResponse(auditEventListFixture));
    await waitFor(() => { expect(exportButton).toBeEnabled(); });

    fireEvent.change(screen.getByRole("textbox", { name: "Пошук у журналі" }), {
      target: { value: "ще-не-застосовано" },
    });
    fireEvent.click(exportButton);
    expect(screen.getByRole("button", { name: "Готуємо CSV…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Скасовано запис/ })).toBeInTheDocument();
    resolveExport?.(auditCsvResponse());

    expect(await screen.findByText("Завантаження CSV журналу дій розпочато.")).toBeInTheDocument();
    expect(exportRequests).toHaveLength(1);
    const exportUrl = new URL(exportRequests[0]?.url ?? "http://invalid");
    expect([...exportUrl.searchParams.keys()].sort()).toEqual(
      ["actor_id", "date_from", "date_to", "search", "section"],
    );
    expect(exportUrl.searchParams.get("search")).toBe("Коваль");
    expect(exportUrl.searchParams.get("actor_id")).toBe("1");
    expect(exportUrl.searchParams.get("section")).toBe("scheduling");
    expect(exportUrl.searchParams.get("date_from")).toContain("2026-07-21T21:00:00.000Z");
    expect(exportUrl.searchParams.get("date_to")).toContain("2026-07-22T20:59:59.999Z");
    expect(exportUrl.href).not.toContain(encodeURIComponent("ще-не-застосовано"));
    expect(exportRequests[0]?.headers.get("Accept")).toBe("text/csv");
    expect(downloadedFilename).toBe("audit-events-20260723-100000.csv");
    anchorClick.mockRestore();
  });

  it("keeps the journal visible after export error and retries the same query", async () => {
    const exportRequests: Request[] = [];
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (url.pathname === "/api/v1/users") return Promise.resolve(jsonResponse({ users: [] }));
      if (url.pathname === "/api/v1/audit-events") return Promise.resolve(jsonResponse(auditEventListFixture));
      if (url.pathname === "/api/v1/audit-events/export") {
        exportRequests.push(request);
        return exportRequests.length === 1
          ? Promise.resolve(jsonResponse({
            code: "audit_export_too_large",
            message: "Експорт містить забагато подій. Звузьте фільтри.",
            fields: { filters: ["Максимум 5000 подій за один файл."] },
            correlation_id: "tp-1007-test",
          }, 422))
          : Promise.resolve(auditCsvResponse());
      }
      return Promise.resolve(jsonResponse({}));
    });
    renderAudit();

    await screen.findByRole("button", { name: /Скасовано запис/ });
    fireEvent.click(screen.getByRole("button", { name: "Експортувати CSV" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Експорт містить забагато подій.");
    expect(screen.getByRole("button", { name: /Скасовано запис/ })).toBeInTheDocument();
    expect(anchorClick).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Повторити export" }));

    expect(await screen.findByText("Завантаження CSV журналу дій розпочато.")).toBeInTheDocument();
    expect(exportRequests).toHaveLength(2);
    expect(new URL(exportRequests[0]?.url ?? "http://invalid").search).toBe(
      new URL(exportRequests[1]?.url ?? "http://invalid").search,
    );
    expect(anchorClick).toHaveBeenCalledTimes(1);
    anchorClick.mockRestore();
  });

  it("keeps audit navigation and direct route unavailable to reception", async () => {
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = new URL(input instanceof Request ? input.url : input.toString());
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(receptionSession));
      if (url.pathname === "/api/v1/overview") return Promise.resolve(jsonResponse(overviewFixture));
      return Promise.resolve(jsonResponse({}));
    });
    renderAudit();

    expect(await screen.findByRole("heading", { name: "Добрий день" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Журнал дій" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Експортувати CSV" })).not.toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.some(([input]) => new URL(input instanceof Request ? input.url : input.toString()).pathname === "/api/v1/audit-events")).toBe(false);
  });
});
