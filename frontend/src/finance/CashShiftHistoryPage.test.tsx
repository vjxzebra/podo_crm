import axe from "axe-core";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import {
  adminSession,
  cashShiftFixture,
  jsonResponse,
  receptionSession,
} from "../test/setup";
import type { CashShiftProjection, CashShiftSummary } from "./cashShiftTypes";

type ResponseFactory = (request: Request) => Promise<Response>;

const closedShift = {
  ...cashShiftFixture,
  entries: cashShiftFixture.entries.map((entry) => ({ ...entry })),
  status: "CLOSED",
  closed_at: "2026-07-22T16:15:00Z",
  reconciliation: {
    expected_cash_minor: 50000,
    actual_cash_minor: 49500,
    discrepancy_minor: -500,
    comment: "Нестача підтверджена повторним перерахунком.",
    closed_by: cashShiftFixture.employee,
  },
} satisfies CashShiftProjection;

const openShift = {
  ...cashShiftFixture,
  entries: cashShiftFixture.entries.map((entry) => ({ ...entry })),
  id: "840f933c-5a86-468a-8862-010166bca113",
  public_number: "CS-20260722-0002",
  closed_at: null,
  reconciliation: null,
} satisfies CashShiftProjection;

function summarize(shift: CashShiftProjection): CashShiftSummary {
  return {
    id: shift.id,
    public_number: shift.public_number,
    status: shift.status,
    employee: shift.employee,
    drawer_key: shift.drawer_key,
    opening_cash_minor: shift.opening_cash_minor,
    opening_basis: shift.opening_basis,
    opening_source_shift: shift.opening_source_shift,
    permissions: shift.permissions,
    opened_at: shift.opened_at,
    closed_at: shift.closed_at,
    totals: shift.totals,
    reconciliation: shift.reconciliation,
  };
}

const closedSummary = summarize(closedShift);
const openSummary = summarize(openShift);
const summaries = [closedSummary, openSummary] satisfies readonly CashShiftSummary[];

const employees = [{
  id: 1,
  email: "admin@example.test",
  first_name: "Тест",
  last_name: "Адміністратор",
  display_name: "Тест Адміністратор",
  phone: "+380671112233",
  role: "admin",
  is_active: true,
  last_login: "2026-07-22T07:00:00Z",
  must_change_password: false,
  temporary_password_expires_at: null,
}, {
  id: 9,
  email: "former@example.test",
  first_name: "Колишня",
  last_name: "Касирка",
  display_name: "Колишня Касирка",
  phone: "+380672223344",
  role: "reception",
  is_active: false,
  last_login: null,
  must_change_password: false,
  temporary_password_expires_at: null,
}] as const;

function response(body: unknown, status = 200): ResponseFactory {
  return () => Promise.resolve(jsonResponse(body, status));
}

function csvResponse(filename = "cash-shift-CS-20260722-0001-20260723-100000.csv"): ResponseFactory {
  return () => Promise.resolve(new Response("\ufeffrow_type,shift_number\r\nSHIFT_SUMMARY,CS-20260722-0001\r\n", {
    headers: {
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Content-Type": "text/csv; charset=utf-8",
      "X-Export-Entry-Count": "0",
      "X-Export-Row-Count": "1",
    },
  }));
}

function historyCsvResponse(filename = "cash-shift-history-20260723-100000.csv"): ResponseFactory {
  return () => Promise.resolve(new Response("\ufeffrow_type,shift_count\r\nREPORT_SUMMARY,2\r\n", {
    headers: {
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Content-Type": "text/csv; charset=utf-8",
      "X-Export-Row-Count": "3",
      "X-Export-Shift-Count": "2",
    },
  }));
}

function mockHistoryApi({
  session = adminSession,
  lists = [response({ shifts: summaries, next_cursor: null })],
  details = [response(closedShift)],
  exports = [csvResponse()],
  historyExports = [historyCsvResponse()],
}: {
  readonly session?: typeof adminSession | typeof receptionSession;
  readonly lists?: readonly ResponseFactory[];
  readonly details?: readonly ResponseFactory[];
  readonly exports?: readonly ResponseFactory[];
  readonly historyExports?: readonly ResponseFactory[];
} = {}) {
  const listQueue = [...lists];
  const detailQueue = [...details];
  const exportQueue = [...exports];
  const historyExportQueue = [...historyExports];
  const requests: Request[] = [];
  vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const request = input instanceof Request ? input : new Request(input, init);
    requests.push(request);
    const url = new URL(request.url);
    if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(session));
    if (url.pathname === "/api/v1/users") return Promise.resolve(jsonResponse({ users: employees }));
    if (url.pathname === "/api/v1/cash-shifts/export" && request.method === "GET") {
      const factory = historyExportQueue.shift() ?? historyExports[historyExports.length - 1];
      return factory?.(request) ?? historyCsvResponse()(request);
    }
    if (url.pathname === "/api/v1/cash-shifts" && request.method === "GET") {
      const factory = listQueue.shift() ?? lists[lists.length - 1];
      return factory?.(request) ?? Promise.resolve(jsonResponse({ shifts: [], next_cursor: null }));
    }
    if (/^\/api\/v1\/cash-shifts\/[0-9a-f-]+\/export$/.test(url.pathname) && request.method === "GET") {
      const factory = exportQueue.shift() ?? exports[exports.length - 1];
      return factory?.(request) ?? csvResponse()(request);
    }
    if (/^\/api\/v1\/cash-shifts\/[0-9a-f-]+$/.test(url.pathname) && request.method === "GET") {
      const factory = detailQueue.shift() ?? details[details.length - 1];
      return factory?.(request) ?? Promise.resolve(jsonResponse(closedShift));
    }
    return Promise.resolve(jsonResponse({ code: "not_found", message: "Not found", fields: {}, correlation_id: "history-test" }, 404));
  });
  return requests;
}

function renderHistory(path = "/finance/shifts") {
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
}

afterEach(() => {
  Object.defineProperty(window, "innerWidth", { configurable: true, value: 1024 });
  window.dispatchEvent(new Event("resize"));
  document.body.style.overflow = "";
});

describe("TP-704 cash-shift history", () => {
  it("keeps navigation URL-backed and applies admin filters including inactive employees", async () => {
    const requests = mockHistoryApi();
    renderHistory();

    expect(await screen.findByRole("heading", { name: "Історія касових змін", level: 1 })).toBeInTheDocument();
    expect(within(screen.getByRole("main")).getByRole("link", { name: /Історія змін/ })).toHaveClass("finance-subnav__link--active");
    const table = await screen.findByRole("table", { name: "Історія касових змін" });
    expect(table).toHaveAttribute("tabindex", "0");
    expect(table).toHaveAccessibleDescription("Прокрутіть таблицю горизонтально, щоб переглянути всі стовпці.");
    expect(await screen.findByRole("option", { name: "Колишня Касирка" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Експортувати CSV" })).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Номер зміни або працівник"), { target: { value: "  CS-2026  " } });
    fireEvent.change(screen.getByLabelText("Період історії"), { target: { value: "custom" } });
    fireEvent.change(screen.getByLabelText("Від дати"), { target: { value: "2026-07-01" } });
    fireEvent.change(screen.getByLabelText("До дати"), { target: { value: "2026-07-31" } });
    fireEvent.change(screen.getByLabelText("Статус касової зміни"), { target: { value: "CLOSED" } });
    fireEvent.change(screen.getByLabelText("Працівник касової зміни"), { target: { value: "9" } });
    fireEvent.click(screen.getByRole("button", { name: "Застосувати" }));

    await waitFor(() => {
      expect(requests.filter((request) => new URL(request.url).pathname === "/api/v1/cash-shifts")).toHaveLength(2);
    });
    const filtered = new URL(requests.filter((request) => new URL(request.url).pathname === "/api/v1/cash-shifts")[1]?.url ?? "http://invalid");
    expect(filtered.searchParams.get("search")).toBe("CS-2026");
    expect(filtered.searchParams.get("date_from")).toBe("2026-07-01");
    expect(filtered.searchParams.get("date_to")).toBe("2026-07-31");
    expect(filtered.searchParams.get("status")).toBe("CLOSED");
    expect(filtered.searchParams.get("employee_id")).toBe("9");
    expect(requests.some((request) => new URL(request.url).pathname === "/api/v1/users" && new URL(request.url).search === "")).toBe(true);
  });

  it("keeps reception history own-only in the UI and loads the next cursor", async () => {
    const nextShift = {
      ...closedSummary,
      id: "840f933c-5a86-468a-8862-010166bca114",
      public_number: "CS-20260721-0009",
    } satisfies CashShiftSummary;
    const requests = mockHistoryApi({
      session: receptionSession,
      lists: [
        response({ shifts: [closedSummary], next_cursor: "cursor-2" }),
        response({ shifts: [nextShift], next_cursor: null }),
      ],
    });
    renderHistory();

    expect(await screen.findByText(/лише ваші зміни/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Працівник касової зміни")).not.toBeInTheDocument();
    expect(requests.some((request) => new URL(request.url).pathname === "/api/v1/users")).toBe(false);
    fireEvent.click(await screen.findByRole("button", { name: "Показати ще" }));

    expect(await screen.findByText(nextShift.public_number)).toBeInTheDocument();
    const listRequests = requests.filter((request) => new URL(request.url).pathname === "/api/v1/cash-shifts");
    expect(new URL(listRequests[1]?.url ?? "http://invalid").searchParams.get("cursor")).toBe("cursor-2");
  });

  it("exports only the last applied history filters and keeps rows visible", async () => {
    let resolveExport: ((response: Response) => void) | undefined;
    let downloadedFilename = "";
    let downloadedHref = "";
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function captureDownload(this: HTMLAnchorElement) {
        downloadedFilename = this.download;
        downloadedHref = this.href;
      });
    const requests = mockHistoryApi({
      historyExports: [() => new Promise<Response>((resolve) => { resolveExport = resolve; })],
    });
    renderHistory();

    await screen.findByRole("table", { name: "Історія касових змін" });
    fireEvent.change(screen.getByPlaceholderText("Номер зміни або працівник"), { target: { value: "CS-2026" } });
    fireEvent.change(screen.getByLabelText("Статус касової зміни"), { target: { value: "CLOSED" } });
    fireEvent.change(screen.getByLabelText("Працівник касової зміни"), { target: { value: "9" } });
    fireEvent.click(screen.getByRole("button", { name: "Застосувати" }));
    await waitFor(() => {
      expect(requests.filter((request) => new URL(request.url).pathname === "/api/v1/cash-shifts")).toHaveLength(2);
    });
    fireEvent.change(screen.getByPlaceholderText("Номер зміни або працівник"), { target: { value: "ще-не-застосовано" } });
    fireEvent.click(screen.getByRole("button", { name: "Експортувати CSV" }));

    expect(screen.getByRole("button", { name: "Готуємо CSV…" })).toBeDisabled();
    expect(screen.getByRole("table", { name: "Історія касових змін" })).toBeInTheDocument();
    resolveExport?.(await historyCsvResponse()(new Request("http://localhost/export")));

    const history = screen.getByRole("region", { name: "Касові зміни" });
    expect(await within(history).findByRole("status")).toHaveTextContent("Завантаження CSV історії розпочато.");
    const exportRequests = requests.filter((request) => new URL(request.url).pathname === "/api/v1/cash-shifts/export");
    expect(exportRequests).toHaveLength(1);
    const exportUrl = new URL(exportRequests[0]?.url ?? "http://invalid");
    expect(exportUrl.searchParams.get("search")).toBe("CS-2026");
    expect(exportUrl.searchParams.get("status")).toBe("CLOSED");
    expect(exportUrl.searchParams.get("employee_id")).toBe("9");
    expect(exportUrl.searchParams.has("cursor")).toBe(false);
    expect(exportUrl.href).not.toContain(encodeURIComponent("ще-не-застосовано"));
    expect(exportRequests[0]?.headers.get("Accept")).toBe("text/csv");
    expect(downloadedFilename).toBe("cash-shift-history-20260723-100000.csv");
    expect(downloadedHref).toBe("blob:inventory-export");
    anchorClick.mockRestore();
  });

  it("keeps history rows after an export error and retries with the same filters", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 480 });
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const requests = mockHistoryApi({
      session: receptionSession,
      historyExports: [
        response({
          code: "cash_shift_history_export_too_large",
          message: "Експорт історії містить забагато касових змін. Звузьте фільтри.",
          fields: { filters: ["Максимум 5000 змін за один файл."] },
          correlation_id: "tp-1004-test",
        }, 422),
        historyCsvResponse(),
      ],
    });
    renderHistory();

    await screen.findByRole("list", { name: "Історія касових змін" });
    fireEvent.click(screen.getByRole("button", { name: "Експортувати CSV" }));

    const history = screen.getByRole("region", { name: "Касові зміни" });
    expect(await within(history).findByRole("alert")).toHaveTextContent("Експорт історії містить забагато касових змін.");
    expect(within(history).getByRole("list", { name: "Історія касових змін" })).toBeInTheDocument();
    expect(anchorClick).not.toHaveBeenCalled();
    fireEvent.click(within(history).getByRole("button", { name: "Повторити export" }));

    expect(await within(history).findByRole("status")).toHaveTextContent("Завантаження CSV історії розпочато.");
    expect(requests.filter((request) => new URL(request.url).pathname === "/api/v1/cash-shifts/export")).toHaveLength(2);
    expect(anchorClick).toHaveBeenCalledTimes(1);
    anchorClick.mockRestore();
  });

  it("recovers a row detail failure and shows full immutable ledger detail", async () => {
    mockHistoryApi({
      details: [
        response({ code: "server_error", message: "Тимчасова помилка деталей.", fields: {}, correlation_id: "detail" }, 500),
        response(closedShift),
      ],
    });
    const { container } = renderHistory();
    const detailTrigger = await screen.findByRole("button", { name: `Відкрити деталі ${closedShift.public_number}` });
    fireEvent.click(detailTrigger);

    expect(await screen.findByRole("alert")).toHaveTextContent("Тимчасова помилка деталей");
    fireEvent.click(screen.getByRole("button", { name: "Повторити деталі" }));
    const dialog = await screen.findByRole("dialog", { name: closedShift.public_number });
    expect(within(dialog).getByRole("table", { name: `Операції ${closedShift.public_number}` })).toBeInTheDocument();
    expect(within(dialog).getByText("Нестача підтверджена повторним перерахунком.")).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "Закрити зміну" })).not.toBeInTheDocument();

    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
    fireEvent.click(within(dialog).getByRole("button", { name: "Готово" }));
    await waitFor(() => { expect(detailTrigger).toHaveFocus(); });
  });

  it("downloads the exact shift CSV with the server filename and keeps the detail visible", async () => {
    let resolveExport: ((response: Response) => void) | undefined;
    let downloadedFilename = "";
    let downloadedHref = "";
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function captureDownload(this: HTMLAnchorElement) {
        downloadedFilename = this.download;
        downloadedHref = this.href;
      });
    const requests = mockHistoryApi({
      exports: [() => new Promise<Response>((resolve) => { resolveExport = resolve; })],
    });
    renderHistory();

    fireEvent.click(await screen.findByRole("button", { name: `Відкрити деталі ${closedShift.public_number}` }));
    const dialog = await screen.findByRole("dialog", { name: closedShift.public_number });
    fireEvent.click(within(dialog).getByRole("button", { name: "Експортувати CSV" }));

    expect(within(dialog).getByRole("button", { name: "Готуємо CSV…" })).toBeDisabled();
    expect(within(dialog).getByRole("table", { name: `Операції ${closedShift.public_number}` })).toBeInTheDocument();
    resolveExport?.(await csvResponse()(new Request("http://localhost/export")));

    expect(await within(dialog).findByRole("status")).toHaveTextContent("Завантаження CSV зміни розпочато.");
    const exportRequests = requests.filter((request) => new URL(request.url).pathname === `/api/v1/cash-shifts/${closedShift.id}/export`);
    expect(exportRequests).toHaveLength(1);
    expect(new URL(exportRequests[0]?.url ?? "http://invalid").search).toBe("");
    expect(exportRequests[0]?.headers.get("Accept")).toBe("text/csv");
    expect(downloadedFilename).toBe("cash-shift-CS-20260722-0001-20260723-100000.csv");
    expect(downloadedHref).toBe("blob:inventory-export");
    expect(dialog).toBeInTheDocument();
    anchorClick.mockRestore();
  });

  it("keeps the immutable ledger visible after an export error and retries in place", async () => {
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const requests = mockHistoryApi({
      exports: [
        response({
          code: "cash_shift_export_too_large",
          message: "Експорт зміни містить забагато касових записів.",
          fields: { shift: ["Максимум 5000 записів за один файл."] },
          correlation_id: "tp-1003-test",
        }, 422),
        csvResponse(),
      ],
    });
    renderHistory();

    fireEvent.click(await screen.findByRole("button", { name: `Відкрити деталі ${closedShift.public_number}` }));
    const dialog = await screen.findByRole("dialog", { name: closedShift.public_number });
    fireEvent.click(within(dialog).getByRole("button", { name: "Експортувати CSV" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Експорт зміни містить забагато касових записів.");
    expect(within(dialog).getByRole("table", { name: `Операції ${closedShift.public_number}` })).toBeInTheDocument();
    expect(anchorClick).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole("button", { name: "Повторити export" }));

    expect(await within(dialog).findByRole("status")).toHaveTextContent("Завантаження CSV зміни розпочато.");
    expect(requests.filter((request) => new URL(request.url).pathname === `/api/v1/cash-shifts/${closedShift.id}/export`)).toHaveLength(2);
    expect(anchorClick).toHaveBeenCalledTimes(1);
    anchorClick.mockRestore();
  });

  it("retries a failed deep-linked detail and renders required mobile card facts", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 480 });
    const requests = mockHistoryApi({
      details: [
        () => Promise.reject(new Error("offline")),
        response(closedShift),
      ],
    });
    renderHistory(`/finance/shifts?shift=${closedShift.id}`);

    expect(await screen.findByRole("list", { name: "Історія касових змін" })).toBeInTheDocument();
    expect(screen.getAllByText("Відкрито / закрито").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Очік. / факт.").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Розбіжність").length).toBeGreaterThan(0);
    expect(await screen.findByRole("alert")).toHaveTextContent("Не вдалося відкрити зміну");
    fireEvent.click(screen.getByRole("button", { name: "Повторити деталі" }));

    expect(await screen.findByRole("dialog", { name: closedShift.public_number })).toBeInTheDocument();
    expect(requests.filter((request) => new URL(request.url).pathname === `/api/v1/cash-shifts/${closedShift.id}`)).toHaveLength(2);
  });

  it("shows recoverable loading, filter validation and empty states", async () => {
    let resolveList: ((response: Response) => void) | undefined;
    mockHistoryApi({ lists: [() => new Promise<Response>((resolve) => { resolveList = resolve; })] });
    renderHistory();
    await screen.findByRole("heading", { name: "Історія касових змін", level: 1 });
    expect(screen.getByRole("status", { name: "Завантаження історії касових змін" })).toBeInTheDocument();
    resolveList?.(jsonResponse({ shifts: [], next_cursor: null }));
    expect(await screen.findByText("Касових змін ще немає")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Період історії"), { target: { value: "custom" } });
    fireEvent.change(screen.getByLabelText("Від дати"), { target: { value: "2026-08-01" } });
    fireEvent.change(screen.getByLabelText("До дати"), { target: { value: "2026-07-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Застосувати" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Дата «Від» не може бути пізнішою");
  });
});
