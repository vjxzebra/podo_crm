import { act, fireEvent, render as testingLibraryRender, screen, waitFor, within } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  adminSession,
  cashShiftFixture,
  emptyCashShiftFixture,
  financeCrossShiftRefundOperation,
  financeDepositResult,
  financeOpenOperation,
  financeOperationsFixture,
  financePaidOperation,
  financePaymentResult,
  financeReceptionDiscount,
  financeRefundResult,
  financeWithdrawalResult,
  jsonResponse,
  receptionSession,
} from "../test/setup";
import { AuthProvider } from "../auth/AuthContext";
import { FinancePage } from "./FinancePage";

function render(ui: ReactElement) {
  return testingLibraryRender(<MemoryRouter><AuthProvider>{ui}</AuthProvider></MemoryRouter>);
}

type ResponseFactory = (request: Request) => Promise<Response>;

function responseFactory(body: unknown, status = 200): ResponseFactory {
  return () => Promise.resolve(jsonResponse(body, status));
}

function csvResponse(filename = "finance-operations-20260723-100000.csv"): ResponseFactory {
  return () => Promise.resolve(new Response("\ufeffrow_type,operation_number\r\nREPORT_SUMMARY,\r\n", {
    headers: {
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Content-Type": "text/csv; charset=utf-8",
      "X-Export-Operation-Count": "0",
      "X-Export-Row-Count": "1",
    },
  }));
}

function pdfResponse(filename = "payment-receipt-TXN-701600000000.pdf"): ResponseFactory {
  return () => Promise.resolve(new Response("%PDF-1.7 test", {
    headers: {
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Content-Type": "application/pdf",
    },
  }));
}

function rejectedFactory(message = "offline"): ResponseFactory {
  return () => Promise.reject(new Error(message));
}

function mockFinanceApi({
  current = [responseFactory({ shift: cashShiftFixture })],
  openShift = responseFactory(emptyCashShiftFixture, 201),
  operations,
  operationExports = [csvResponse()],
  discounts = responseFactory({ discounts: [financeReceptionDiscount] }),
  payment = responseFactory(financePaymentResult, 201),
  receipt = pdfResponse(),
  refund = responseFactory(financeRefundResult, 201),
  cashMovement,
  session = adminSession,
}: {
  readonly current?: readonly ResponseFactory[];
  readonly openShift?: ResponseFactory;
  readonly operations?: ResponseFactory;
  readonly operationExports?: readonly ResponseFactory[];
  readonly discounts?: ResponseFactory;
  readonly payment?: ResponseFactory;
  readonly receipt?: ResponseFactory;
  readonly refund?: ResponseFactory;
  readonly cashMovement?: ResponseFactory;
  readonly session?: typeof adminSession | typeof receptionSession;
} = {}) {
  const currentQueue = [...current];
  const exportQueue = [...operationExports];
  const fetchMock = vi.mocked(fetch);
  fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const request = input instanceof Request ? input : new Request(input, init);
    const url = new URL(request.url);
    if (url.pathname === "/api/v1/session" && request.method === "GET") {
      return Promise.resolve(jsonResponse(session));
    }
    if (url.pathname === "/api/v1/cash-shifts/current" && request.method === "GET") {
      const factory = currentQueue.shift() ?? current[current.length - 1];
      return factory?.(request) ?? Promise.resolve(jsonResponse({ shift: null }));
    }
    if (url.pathname === "/api/v1/cash-shifts" && request.method === "POST") {
      return openShift(request);
    }
    if (url.pathname === "/api/v1/finance/operations" && request.method === "GET") {
      if (operations !== undefined) return operations(request);
      if (url.searchParams.get("refundable_only") === "true") {
        return Promise.resolve(jsonResponse({ operations: [financePaidOperation], next_cursor: null }));
      }
      return Promise.resolve(jsonResponse(url.searchParams.get("status") === "OPEN"
        ? { operations: [financeOpenOperation], next_cursor: null }
        : financeOperationsFixture));
    }
    if (url.pathname === "/api/v1/finance/operations/export" && request.method === "GET") {
      const factory = exportQueue.shift() ?? operationExports[operationExports.length - 1];
      return factory?.(request) ?? Promise.resolve(jsonResponse({
        code: "not_found",
        message: "Not found",
        fields: {},
        correlation_id: "test",
      }, 404));
    }
    if (url.pathname === "/api/v1/discounts" && request.method === "GET") {
      return discounts(request);
    }
    if (url.pathname === "/api/v1/payments" && request.method === "POST") {
      return payment(request);
    }
    if (/^\/api\/v1\/payments\/[0-9a-f-]+\/receipt$/.test(url.pathname) && request.method === "GET") {
      return receipt(request);
    }
    if (/^\/api\/v1\/payments\/[0-9a-f-]+\/refunds$/.test(url.pathname) && request.method === "POST") {
      return refund(request);
    }
    if (url.pathname === "/api/v1/cash-movements" && request.method === "POST") {
      if (cashMovement !== undefined) return cashMovement(request);
      return request.clone().json().then((body: { type?: string }) => jsonResponse(body.type === "WITHDRAWAL" ? financeWithdrawalResult : financeDepositResult, 201));
    }
    return Promise.resolve(jsonResponse({ code: "not_found", message: "Not found", fields: {}, correlation_id: "test" }, 404));
  });
  return fetchMock;
}

describe("TP-701 current cash shift", () => {
  beforeEach(() => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
  });

  afterEach(() => {
    document.cookie = "podoria_csrftoken=; max-age=0; path=/";
    document.body.style.overflow = "";
  });

  it("shows a loading state and recovers from a failed current-shift request", async () => {
    mockFinanceApi({ current: [rejectedFactory(), responseFactory({ shift: cashShiftFixture })] });
    render(<FinancePage />);

    expect(screen.getByRole("status", { name: "Завантаження поточної касової зміни" })).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("Немає зв’язку із сервером");
    fireEvent.click(screen.getByRole("button", { name: "Повторити" }));

    expect(await screen.findByRole("heading", { name: "Поточна касова зміна" })).toBeInTheDocument();
  });

  it("confirms an automatic carry-forward opening with focus trap, Escape and focus return", async () => {
    mockFinanceApi({ current: [responseFactory({ shift: null })] });
    render(<FinancePage />);

    const trigger = await screen.findByRole("button", { name: "Відкрити касову зміну" });
    fireEvent.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "Відкрити касову зміну?" });
    const cancel = within(dialog).getByRole("button", { name: "Скасувати" });
    const confirm = within(dialog).getByRole("button", { name: "Відкрити зміну" });
    const close = within(dialog).getByRole("button", { name: "Закрити підтвердження" });

    expect(cancel).toHaveFocus();
    expect(document.body.style.overflow).toBe("hidden");
    expect(within(dialog).queryByRole("spinbutton")).not.toBeInTheDocument();
    expect(within(dialog).getByText(/перенесе фактично перераховану готівку/)).toBeInTheDocument();
    close.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(confirm).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("dialog", { name: "Відкрити касову зміну?" })).not.toBeInTheDocument();
    await waitFor(() => { expect(trigger).toHaveFocus(); });
  });

  it("locks the opening dialog while POST is pending and replaces the empty state on success", async () => {
    let resolveOpen: ((response: Response) => void) | undefined;
    mockFinanceApi({
      current: [responseFactory({ shift: null })],
      openShift: () => new Promise<Response>((resolve) => { resolveOpen = resolve; }),
    });
    render(<FinancePage />);
    fireEvent.click(await screen.findByRole("button", { name: "Відкрити касову зміну" }));
    const dialog = screen.getByRole("dialog", { name: "Відкрити касову зміну?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Відкрити зміну" }));

    expect(within(dialog).getByRole("button", { name: "Відкриваємо…" })).toBeDisabled();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("dialog", { name: "Відкрити касову зміну?" })).toBeInTheDocument();

    act(() => { resolveOpen?.(jsonResponse(emptyCashShiftFixture, 201)); });
    expect(await screen.findByRole("status")).toHaveTextContent(`Касову зміну ${emptyCashShiftFixture.public_number} відкрито`);
    expect(screen.getByRole("heading", { name: "Поточна касова зміна" })).toBeInTheDocument();
  });

  it("refreshes the exact current projection after an already-open conflict", async () => {
    mockFinanceApi({
      current: [responseFactory({ shift: null }), responseFactory({ shift: cashShiftFixture })],
      openShift: responseFactory({
        code: "cash_shift_already_open",
        message: "Відкрита касова зміна вже існує.",
        fields: {},
        correlation_id: "cash-shift-conflict",
      }, 409),
    });
    render(<FinancePage />);
    fireEvent.click(await screen.findByRole("button", { name: "Відкрити касову зміну" }));
    fireEvent.click(screen.getByRole("button", { name: "Відкрити зміну" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Відкрита зміна вже існувала");
    expect(screen.getAllByText(cashShiftFixture.public_number).length).toBeGreaterThan(0);
  });

  it("keeps opening confirmation recoverable when the exact refresh after 409 fails", async () => {
    mockFinanceApi({
      current: [responseFactory({ shift: null }), rejectedFactory()],
      openShift: responseFactory({
        code: "cash_shift_already_open",
        message: "Відкрита касова зміна вже існує.",
        fields: {},
        correlation_id: "cash-shift-conflict",
      }, 409),
    });
    render(<FinancePage />);
    fireEvent.click(await screen.findByRole("button", { name: "Відкрити касову зміну" }));
    fireEvent.click(screen.getByRole("button", { name: "Відкрити зміну" }));

    const dialog = await screen.findByRole("dialog", { name: "Відкрити касову зміну?" });
    expect(within(dialog).getByRole("alert")).toHaveTextContent("Не вдалося оновити актуальну касову зміну");
  });

  it("preserves ledger totals while adding the TP-702 read surface", async () => {
    mockFinanceApi();
    const { container } = render(<FinancePage />);

    expect((await screen.findAllByText(cashShiftFixture.public_number)).length).toBeGreaterThan(0);
    expect(screen.getByText("Очікувана готівка")).toBeInTheDocument();
    expect(screen.getAllByText("Переказ").length).toBeGreaterThan(0);
    expect(screen.getByText("Службові рухи")).toBeInTheDocument();
    expect(container.querySelectorAll(".finance-ledger-row")).toHaveLength(2);
    expect(await screen.findByRole("table", { name: "Список фінансових операцій" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Повернення" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Внесення" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "− Вилучення" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Закрити зміну" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Експортувати CSV" })).toBeInTheDocument();
  });

  it("shows the shared shift owner and carried opening while blocking a foreign reception", async () => {
    const sharedShift = {
      ...cashShiftFixture,
      employee: {
        id: adminSession.user.id,
        name: adminSession.user.display_name,
        email: adminSession.user.email,
        role: adminSession.user.role,
      },
      opening_cash_minor: 12_500,
      opening_basis: "CARRY_FORWARD",
      opening_source_shift: {
        id: "840f933c-5a86-468a-8862-010166bca111",
        public_number: "CSH-PREVIOUS",
      },
      permissions: { can_mutate: false, can_close: false },
      totals: { ...cashShiftFixture.totals, expected_cash_minor: 62_500 },
    } as const;
    mockFinanceApi({
      current: [responseFactory({ shift: sharedShift })],
      session: receptionSession,
    });
    render(<FinancePage />);

    expect(await screen.findByText(/CSH-PREVIOUS/)).toBeInTheDocument();
    expect(screen.getByText(`Зміну веде ${adminSession.user.display_name}`)).toBeInTheDocument();
    expect(screen.getByText("Касові операції проводить власник поточної зміни")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Закрити зміну" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Провести оплату" })).not.toBeInTheDocument();
  });
});

describe("TP-702 finance operations and full payment", () => {
  beforeEach(() => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
  });

  afterEach(() => {
    document.cookie = "podoria_csrftoken=; max-age=0; path=/";
    document.body.style.overflow = "";
  });

  it("keeps the operation read surface visible without an open shift", async () => {
    mockFinanceApi({ current: [responseFactory({ shift: null })] });
    render(<FinancePage />);

    expect(await screen.findByRole("table", { name: "Список фінансових операцій" })).toBeInTheDocument();
    expect(screen.getByText("Для касових операцій відкрийте власну зміну")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Провести оплату" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Оплатити / })).not.toBeInTheDocument();
  });

  it("applies exact list filters, validates dates and resets a filtered empty state", async () => {
    const requests: Request[] = [];
    mockFinanceApi({
      operations: (request) => {
        requests.push(request);
        return Promise.resolve(jsonResponse(requests.length === 1 ? financeOperationsFixture : { operations: [], next_cursor: null }));
      },
    });
    render(<FinancePage />);
    await screen.findByRole("table", { name: "Список фінансових операцій" });
    const initialUrl = new URL(requests[0]?.url ?? "http://invalid");
    expect(initialUrl.searchParams.toString()).toBe("");

    fireEvent.change(screen.getByPlaceholderText("Пацієнт, телефон або номер"), { target: { value: "Марія" } });
    fireEvent.change(screen.getByLabelText("Статус"), { target: { value: "OPEN" } });
    fireEvent.change(screen.getByLabelText("Спосіб"), { target: { value: "CARD" } });
    fireEvent.change(screen.getByLabelText("Від дати"), { target: { value: "2026-07-23" } });
    fireEvent.change(screen.getByLabelText("До дати"), { target: { value: "2026-07-22" } });
    fireEvent.click(screen.getByRole("button", { name: "Застосувати" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Дата «Від» не може бути пізнішою");
    expect(requests).toHaveLength(1);

    fireEvent.change(screen.getByLabelText("Від дати"), { target: { value: "2026-07-21" } });
    fireEvent.click(screen.getByRole("button", { name: "Застосувати" }));
    expect(await screen.findByText("Операцій за фільтрами не знайдено")).toBeInTheDocument();
    const url = new URL(requests[1]?.url ?? "http://invalid");
    expect(url.searchParams.get("search")).toBe("Марія");
    expect(url.searchParams.get("type")).toBeNull();
    expect(url.searchParams.get("status")).toBe("OPEN");
    expect(url.searchParams.get("payment_method")).toBe("CARD");
    expect(url.searchParams.get("date_from")).toBe("2026-07-21");
    expect(url.searchParams.get("date_to")).toBe("2026-07-22");
    fireEvent.click(screen.getByRole("button", { name: "Скинути фільтри" }));
    await waitFor(() => { expect(requests).toHaveLength(3); });
    const resetUrl = new URL(requests[2]?.url ?? "http://invalid");
    expect(resetUrl.searchParams.toString()).toBe("");
  });

  it("opens immutable paid and zero-total details with focus return", async () => {
    mockFinanceApi();
    render(<FinancePage />);
    const paidTrigger = await screen.findByRole("button", { name: `Відкрити деталі ${financePaidOperation.payment.public_number} — ${financePaidOperation.patient.display_name}` });
    fireEvent.click(paidTrigger);

    let dialog = screen.getByRole("dialog", { name: financePaidOperation.payment.public_number });
    expect(within(dialog).getByText("Оплачено")).toBeInTheDocument();
    expect(within(dialog).getByText("Оплату підтверджено на терміналі.")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: `Завантажити PDF квитанції ${financePaidOperation.payment.public_number}` })).toBeInTheDocument();
    expect(within(dialog).getByRole("link", { name: `Відкрити PDF для друку ${financePaidOperation.payment.public_number}` })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Оформити повне повернення" })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => { expect(paidTrigger).toHaveFocus(); });

    const zeroTrigger = screen.getByRole("button", { name: `Відкрити деталі ${financeOperationsFixture.operations[2].visit.public_number} — ${financeOperationsFixture.operations[2].patient.display_name}` });
    fireEvent.click(zeroTrigger);
    dialog = screen.getByRole("dialog", { name: financeOperationsFixture.operations[2].visit.public_number });
    expect(within(dialog).getAllByText("Без оплати").length).toBeGreaterThan(0);
    expect(within(dialog).getByText("Нульова сума · закрито без касової операції")).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "Провести оплату" })).not.toBeInTheDocument();
  });

  it("keeps authoritative pricing and posts its version with one stable key", async () => {
    const paymentRequests: Request[] = [];
    const operationRequests: Request[] = [];
    mockFinanceApi({
      current: [responseFactory({ shift: cashShiftFixture }), responseFactory({ shift: cashShiftFixture })],
      operations: (request) => {
        operationRequests.push(request);
        const status = new URL(request.url).searchParams.get("status");
        return Promise.resolve(jsonResponse(status === "OPEN"
          ? { operations: [financeOpenOperation], next_cursor: null }
          : financeOperationsFixture));
      },
      payment: (request) => { paymentRequests.push(request); return Promise.resolve(jsonResponse(financePaymentResult, 201)); },
    });
    render(<FinancePage />);
    fireEvent.click(await screen.findByRole("button", { name: "Провести оплату" }));
    const dialog = screen.getByRole("dialog", { name: "Провести оплату прийому" });
    const option = await within(dialog).findByRole("option", { name: /Марія Бондар/ });
    fireEvent.click(option);
    const pickerUrl = new URL(operationRequests.at(-1)?.url ?? "http://invalid");
    expect(Object.fromEntries(pickerUrl.searchParams)).toEqual({ type: "PAYMENT", status: "OPEN" });

    expect(within(dialog).getByText("Медичний педикюр")).toBeInTheDocument();
    expect(within(dialog).getAllByText(/1.?350,00/).length).toBeGreaterThan(0);
    const pricing = within(dialog).getByRole("group", { name: "Розрахунок оплати" });
    expect(within(pricing).getByText("№ 3")).toBeInTheDocument();
    expect(within(pricing).getAllByText("Без знижки")).toHaveLength(2);
    expect(within(dialog).queryByRole("spinbutton")).not.toBeInTheDocument();
    expect(within(within(dialog).getByRole("group", { name: "Спосіб оплати" })).getAllByRole("radio")).toHaveLength(3);
    fireEvent.click(within(dialog).getByRole("radio", { name: "Картка" }));
    fireEvent.change(within(dialog).getByPlaceholderText("Додаткова інформація про оплату"), { target: { value: "Повна оплата" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Провести повну оплату" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Оплату TXN-701600000000");
    expect(paymentRequests).toHaveLength(1);
    const request = paymentRequests[0];
    expect(request?.headers.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
    expect(request?.headers.get("X-CSRFToken")).toBe("test-csrf");
    expect(await request?.clone().json()).toEqual({
      visit_id: financeOpenOperation.visit.id,
      payment_method: "CARD",
      pricing_version: financeOpenOperation.pricing.version,
      discount_action: "KEEP",
      comment: "Повна оплата",
    });
    const receiptDialog = await screen.findByRole("dialog", { name: "Квитанція готова" });
    expect(within(receiptDialog).getByText(/не є фіскальним чеком/i)).toBeInTheDocument();
    expect(within(receiptDialog).getByRole("button", { name: `Завантажити PDF квитанції ${financePaymentResult.operation.payment.public_number}` })).toBeInTheDocument();
    fireEvent.click(within(receiptDialog).getByRole("button", { name: "Готово" }));
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Фінансові операції" })).toHaveFocus();
    });
  });

  it("replaces, rather than stacks, the current discount and posts SET with its id", async () => {
    const paymentRequests: Request[] = [];
    mockFinanceApi({
      payment: (request) => {
        paymentRequests.push(request);
        return Promise.resolve(jsonResponse(financePaymentResult, 201));
      },
    });
    render(<FinancePage />);

    fireEvent.click(await screen.findByRole("button", { name: /^Оплатити / }));
    const dialog = screen.getByRole("dialog", { name: "Провести оплату прийому" });
    const replaceDiscount = await within(dialog).findByRole("radio", { name: /Замінити знижку/ });
    fireEvent.click(replaceDiscount);
    fireEvent.change(within(dialog).getByRole("combobox", { name: "Активна знижка" }), {
      target: { value: financeReceptionDiscount.id },
    });

    const pricing = within(dialog).getByRole("group", { name: "Розрахунок оплати" });
    expect(within(pricing).getByText(/Постійний клієнт · 10% · −135,00/)).toBeInTheDocument();
    expect(within(pricing).getByText(/1.?215,00/)).toBeInTheDocument();
    expect(within(pricing).getByText("Рецепція")).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("radio", { name: "Картка" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Провести повну оплату" }));

    await screen.findByRole("dialog", { name: "Квитанція готова" });
    expect(paymentRequests).toHaveLength(1);
    expect(await paymentRequests[0]?.clone().json()).toEqual({
      visit_id: financeOpenOperation.visit.id,
      payment_method: "CARD",
      pricing_version: financeOpenOperation.pricing.version,
      discount_action: "SET",
      discount_id: financeReceptionDiscount.id,
      comment: "",
    });
  });

  it("downloads the receipt and exposes a native-browser print link", async () => {
    const receiptRequests: Request[] = [];
    mockFinanceApi({
      receipt: (request) => {
        receiptRequests.push(request);
        return pdfResponse("receipt-custom.pdf")(request);
      },
    });
    render(<FinancePage />);
    fireEvent.click(await screen.findByRole("button", {
      name: `Відкрити деталі ${financePaidOperation.payment.public_number} — ${financePaidOperation.patient.display_name}`,
    }));
    const dialog = screen.getByRole("dialog", { name: financePaidOperation.payment.public_number });

    fireEvent.click(within(dialog).getByRole("button", {
      name: `Завантажити PDF квитанції ${financePaidOperation.payment.public_number}`,
    }));
    await within(dialog).findByText("Завантаження PDF розпочато.");
    expect(receiptRequests).toHaveLength(1);
    expect(new URL(receiptRequests[0]?.url ?? "http://invalid").searchParams.get("disposition")).toBe("attachment");
    expect(receiptRequests[0]?.headers.get("Accept")).toBe("application/pdf");
    expect(
      (URL.createObjectURL as unknown as { readonly mock: { readonly calls: readonly unknown[] } })
        .mock.calls.length,
    ).toBeGreaterThan(0);

    const printLink = within(dialog).getByRole("link", {
      name: `Відкрити PDF для друку ${financePaidOperation.payment.public_number}`,
    });
    const printUrl = new URL(printLink.getAttribute("href") ?? "http://invalid");
    expect(printUrl.pathname).toBe(`/api/v1/payments/${financePaidOperation.payment.id}/receipt`);
    expect(printUrl.searchParams.get("disposition")).toBe("inline");
    expect(printLink).toHaveAttribute("target", "_blank");
    expect(printLink).toHaveAttribute("rel", "noopener noreferrer");
    expect(receiptRequests).toHaveLength(1);
  });

  it("preserves the form and idempotency key through a network retry", async () => {
    const paymentRequests: Request[] = [];
    let attempt = 0;
    mockFinanceApi({
      payment: (request) => {
        paymentRequests.push(request);
        attempt += 1;
        return attempt === 1 ? Promise.reject(new Error("offline")) : Promise.resolve(jsonResponse(financePaymentResult, 201));
      },
    });
    render(<FinancePage />);
    fireEvent.click(await screen.findByRole("button", { name: /^Оплатити / }));
    const dialog = screen.getByRole("dialog", { name: "Провести оплату прийому" });
    fireEvent.click(within(dialog).getByRole("radio", { name: "Готівка" }));
    fireEvent.change(within(dialog).getByPlaceholderText("Додаткова інформація про оплату"), { target: { value: "Збережений коментар" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Провести повну оплату" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Дані збережено у формі");
    expect(within(dialog).getByDisplayValue("Збережений коментар")).toBeInTheDocument();
    expect(within(dialog).getByDisplayValue("Збережений коментар")).toBeDisabled();
    expect(within(dialog).getByRole("radio", { name: "Готівка" })).toBeDisabled();
    fireEvent.click(within(dialog).getByRole("button", { name: "Повторити той самий запит" }));
    await waitFor(() => { expect(paymentRequests).toHaveLength(2); });
    expect(paymentRequests[0]?.headers.get("Idempotency-Key")).toBe(paymentRequests[1]?.headers.get("Idempotency-Key"));
  });

  it("refreshes authoritative operations and blocks duplicate payment on a stale pricing conflict", async () => {
    let operationLoads = 0;
    const paymentRequests: Request[] = [];
    mockFinanceApi({
      current: [responseFactory({ shift: cashShiftFixture }), responseFactory({ shift: cashShiftFixture })],
      operations: (request) => {
        operationLoads += 1;
        const status = new URL(request.url).searchParams.get("status");
        return Promise.resolve(jsonResponse(status === "OPEN" ? { operations: [financeOpenOperation], next_cursor: null } : financeOperationsFixture));
      },
      payment: (request) => {
        paymentRequests.push(request);
        return Promise.resolve(jsonResponse({
          code: "pricing_version_conflict",
          message: "Розрахунок уже змінився. Оновіть дані та повторіть оплату.",
          fields: { pricing_version: ["Версія розрахунку застаріла."] },
          correlation_id: "pricing-conflict",
        }, 409));
      },
    });
    render(<FinancePage />);
    fireEvent.click(await screen.findByRole("button", { name: /^Оплатити / }));
    const dialog = screen.getByRole("dialog", { name: "Провести оплату прийому" });
    fireEvent.click(within(dialog).getByRole("radio", { name: "Переказ" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Провести повну оплату" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Розрахунок уже змінився");
    expect(within(dialog).getByRole("button", { name: "Обрати інший прийом" })).toBeInTheDocument();
    expect(operationLoads).toBeGreaterThanOrEqual(2);
    const submit = within(dialog).getByRole("button", { name: "Провести повну оплату" });
    expect(submit).toBeDisabled();
    fireEvent.click(submit);
    expect(paymentRequests).toHaveLength(1);
    fireEvent.click(within(dialog).getByRole("button", { name: "Обрати інший прийом" }));
    expect(within(dialog).getByRole("combobox", { name: "Неоплачений прийом" })).toHaveValue("");
    await waitFor(() => { expect(within(dialog).getByRole("combobox", { name: "Неоплачений прийом" })).toHaveFocus(); });
  });

  it("returns to the no-shift state when the server rejects a stale shift", async () => {
    mockFinanceApi({
      current: [responseFactory({ shift: cashShiftFixture }), responseFactory({ shift: null })],
      payment: responseFactory({
        code: "cash_shift_required",
        message: "Відкрийте власну касову зміну.",
        fields: {},
        correlation_id: "shift-conflict",
      }, 409),
    });
    render(<FinancePage />);
    fireEvent.click(await screen.findByRole("button", { name: /^Оплатити / }));
    const dialog = screen.getByRole("dialog", { name: "Провести оплату прийому" });
    fireEvent.click(within(dialog).getByRole("radio", { name: "Готівка" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Провести повну оплату" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Відкрийте власну касову зміну");
    fireEvent.click(within(dialog).getByRole("button", { name: "Повернутися до каси" }));
    expect(screen.queryByRole("dialog", { name: "Провести оплату прийому" })).not.toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Касову зміну ще не відкрито" })).toBeInTheDocument();
  });

  it("requires confirmation before discarding a selected payment", async () => {
    mockFinanceApi();
    render(<FinancePage />);
    const trigger = await screen.findByRole("button", { name: /^Оплатити / });
    fireEvent.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "Провести оплату прийому" });
    fireEvent.click(within(dialog).getByRole("radio", { name: "Картка" }));
    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.getByRole("heading", { name: "Відхилити введені дані?" })).toBeInTheDocument();
    await waitFor(() => { expect(screen.getByRole("button", { name: "Продовжити заповнення" })).toHaveFocus(); });
    fireEvent.click(screen.getByRole("button", { name: "Продовжити заповнення" }));
    expect(within(dialog).getByRole("radio", { name: "Картка" })).toBeChecked();
    fireEvent.keyDown(document, { key: "Escape" });
    fireEvent.click(screen.getByRole("button", { name: "Відхилити дані" }));
    expect(screen.queryByRole("dialog", { name: "Провести оплату прийому" })).not.toBeInTheDocument();
    await waitFor(() => { expect(trigger).toHaveFocus(); });
  });
});

describe("TP-703 full refund and cash movements", () => {
  beforeEach(() => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
  });

  afterEach(() => {
    document.cookie = "podoria_csrftoken=; max-age=0; path=/";
    document.body.style.overflow = "";
  });

  it("renders all immutable operation variants and their linked details", async () => {
    mockFinanceApi();
    render(<FinancePage />);

    const table = await screen.findByRole("table", { name: "Список фінансових операцій" });
    expect(within(table).getAllByText("Повернення").length).toBeGreaterThan(0);
    expect(within(table).getAllByText("Внесення").length).toBeGreaterThan(0);
    expect(within(table).getAllByText("Вилучення").length).toBeGreaterThan(0);
    expect(within(table).getAllByText("Проведено").length).toBeGreaterThan(0);

    fireEvent.click(within(table).getByRole("button", { name: "Відкрити деталі TXN-703600000003 — Каса" }));
    const detail = screen.getByRole("dialog", { name: "TXN-703600000003" });
    expect(within(detail).getByText("Розмінні кошти")).toBeInTheDocument();
    expect(within(detail).getByText("Не пов’язана з пацієнтом або способом оплати")).toBeInTheDocument();
    expect(within(detail).queryByRole("button", { name: /повернути|оплатити/i })).not.toBeInTheDocument();
  });

  it("exposes complete table semantics and both sides of a cross-shift refund", async () => {
    mockFinanceApi({
      operations: responseFactory({ operations: [financeCrossShiftRefundOperation], next_cursor: null }),
    });
    render(<FinancePage />);

    const table = await screen.findByRole("table", { name: "Список фінансових операцій" });
    expect(table).toHaveAttribute("tabindex", "0");
    expect(table).toHaveAccessibleDescription("Прокрутіть таблицю горизонтально, щоб переглянути всі стовпці.");
    expect(within(table).getAllByRole("columnheader")).toHaveLength(9);
    expect(within(table).getByRole("columnheader", { name: "Дії" })).toBeInTheDocument();

    fireEvent.click(within(table).getByRole("button", {
      name: `Відкрити деталі ${financeCrossShiftRefundOperation.refund.public_number} — ${financeCrossShiftRefundOperation.patient.display_name}`,
    }));
    const detail = screen.getByRole("dialog", { name: financeCrossShiftRefundOperation.refund.public_number });
    const originalActorFact = within(detail).getByText("Оплату провів(-ла)").parentElement;
    const originalShiftFact = within(detail).getByText("Зміна початкової оплати").parentElement;
    const refundActorFact = within(detail).getByText("Повернення провів(-ла)").parentElement;
    const refundShiftFact = within(detail).getByText("Зміна повернення").parentElement;
    if (originalActorFact === null || originalShiftFact === null || refundActorFact === null || refundShiftFact === null) {
      throw new Error("Refund provenance facts must have value containers.");
    }
    expect(within(originalActorFact).getByText(financeCrossShiftRefundOperation.original_payment.actor.name)).toBeInTheDocument();
    expect(within(originalShiftFact).getByText(financeCrossShiftRefundOperation.original_payment.cash_shift.public_number)).toBeInTheDocument();
    expect(within(refundActorFact).getByText(financeCrossShiftRefundOperation.refund.actor.name)).toBeInTheDocument();
    expect(within(refundShiftFact).getByText(financeCrossShiftRefundOperation.refund.cash_shift.public_number)).toBeInTheDocument();
  });

  it("searches refundable payments by patient, date and exact amount and posts only the reason", async () => {
    const operationRequests: Request[] = [];
    const refundRequests: Request[] = [];
    mockFinanceApi({
      operations: (request) => {
        operationRequests.push(request);
        const params = new URL(request.url).searchParams;
        return Promise.resolve(jsonResponse(params.get("refundable_only") === "true"
          ? { operations: [financePaidOperation], next_cursor: null }
          : financeOperationsFixture));
      },
      refund: (request) => { refundRequests.push(request); return Promise.resolve(jsonResponse(financeRefundResult, 201)); },
    });
    render(<FinancePage />);
    fireEvent.click(await screen.findByRole("button", { name: "Повернення" }));
    const dialog = screen.getByRole("dialog", { name: "Оформити повернення" });

    fireEvent.change(within(dialog).getByRole("combobox", { name: "Початкова оплата" }), { target: { value: "Наталія" } });
    fireEvent.change(within(dialog).getByLabelText(/Дата оплати/), { target: { value: "2026-07-22" } });
    fireEvent.change(within(dialog).getByLabelText(/Точна сума/), { target: { value: "2500" } });
    const option = await within(dialog).findByRole("option", { name: /Наталія Коваль/ });
    const pickerUrl = new URL(operationRequests.at(-1)?.url ?? "http://invalid");
    expect(Object.fromEntries(pickerUrl.searchParams)).toEqual({
      type: "PAYMENT",
      status: "PAID",
      refundable_only: "true",
      search: "Наталія",
      date_from: "2026-07-22",
      date_to: "2026-07-22",
      amount_minor: "250000",
    });
    fireEvent.click(option);
    expect(within(dialog).queryByRole("radio")).not.toBeInTheDocument();
    expect(within(dialog).queryByLabelText("Спосіб оплати")).not.toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText("Причина повернення"), { target: { value: "  Погоджене повне повернення  " } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Перейти до підтвердження" }));

    expect(within(dialog).getByRole("heading", { name: "Підтвердити повне повернення?" })).toBeInTheDocument();
    expect(within(dialog).getByText(financePaidOperation.payment.public_number)).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: /Повернути/ }));

    expect(await screen.findByRole("status")).toHaveTextContent("Повне повернення TXN-703600000001");
    expect(refundRequests).toHaveLength(1);
    expect(refundRequests[0]?.headers.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
    expect(refundRequests[0]?.headers.get("X-CSRFToken")).toBe("test-csrf");
    expect(await refundRequests[0]?.clone().json()).toEqual({ reason: "Погоджене повне повернення" });
  });

  it("opens a preselected refund from payment details and returns focus on cancel", async () => {
    mockFinanceApi();
    render(<FinancePage />);
    const detailTrigger = await screen.findByRole("button", { name: `Відкрити деталі ${financePaidOperation.payment.public_number} — ${financePaidOperation.patient.display_name}` });
    fireEvent.click(detailTrigger);
    fireEvent.click(screen.getByRole("button", { name: "Оформити повне повернення" }));
    const dialog = screen.getByRole("dialog", { name: "Оформити повернення" });
    expect(within(dialog).getByText(financePaidOperation.patient.display_name)).toBeInTheDocument();
    await waitFor(() => { expect(within(dialog).getByLabelText("Причина повернення")).toHaveFocus(); });
    fireEvent.change(within(dialog).getByLabelText("Причина повернення"), { target: { value: "Чернетка причини" } });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("heading", { name: "Відхилити введені дані?" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Відхилити дані" }));
    await waitFor(() => { expect(detailTrigger).toHaveFocus(); });
  });

  it("treats generic refund search filters as dirty and preserves dialog focus lifecycle", async () => {
    mockFinanceApi();
    render(<FinancePage />);
    fireEvent.click(await screen.findByRole("button", { name: "Повернення" }));
    const dialog = screen.getByRole("dialog", { name: "Оформити повернення" });
    const search = within(dialog).getByRole("combobox", { name: "Початкова оплата" });
    await waitFor(() => { expect(search).toHaveFocus(); });
    expect(document.body.style.overflow).toBe("hidden");

    fireEvent.change(search, { target: { value: "Наталія" } });
    fireEvent.change(within(dialog).getByLabelText(/Дата оплати/), { target: { value: "2026-07-22" } });
    fireEvent.change(within(dialog).getByLabelText(/Точна сума/), { target: { value: "2500" } });
    fireEvent.keyDown(document, { key: "Escape" });

    expect(within(dialog).getByRole("heading", { name: "Відхилити введені дані?" })).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Продовжити заповнення" }));
    const resumedSearch = within(dialog).getByRole("combobox", { name: "Початкова оплата" });
    await waitFor(() => { expect(resumedSearch).toHaveFocus(); });
    fireEvent.click(within(dialog).getByRole("button", { name: "Закрити форму повернення" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Відхилити дані" }));
    await waitFor(() => { expect(screen.queryByRole("dialog", { name: "Оформити повернення" })).not.toBeInTheDocument(); });
    expect(document.body.style.overflow).toBe("");
  });

  it("keeps the exact refund key and body through an ambiguous network retry", async () => {
    const requests: Request[] = [];
    mockFinanceApi({
      refund: (request) => {
        requests.push(request);
        return requests.length === 1 ? Promise.reject(new Error("offline")) : Promise.resolve(jsonResponse(financeRefundResult, 201));
      },
    });
    render(<FinancePage />);
    fireEvent.click(await screen.findByRole("button", { name: /^Повернути / }));
    const dialog = screen.getByRole("dialog", { name: "Оформити повернення" });
    fireEvent.change(within(dialog).getByLabelText("Причина повернення"), { target: { value: "Повторюваний запит" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Перейти до підтвердження" }));
    fireEvent.click(within(dialog).getByRole("button", { name: /Повернути/ }));
    const alert = await within(dialog).findByRole("alert");
    expect(alert).toHaveTextContent("повторіть той самий запит");
    await waitFor(() => { expect(alert).toHaveFocus(); });
    expect(document.body.style.overflow).toBe("hidden");
    const close = within(dialog).getByRole("button", { name: "Закрити форму повернення" });
    const back = within(dialog).getByRole("button", { name: "Назад до форми" });
    expect(close).toBeDisabled();
    expect(back).toBeDisabled();
    fireEvent.keyDown(document, { key: "Escape" });
    const layer = dialog.parentElement;
    if (layer === null) throw new Error("Refund dialog must have a modal layer.");
    fireEvent.mouseDown(layer);
    fireEvent.click(close);
    expect(within(dialog).getByRole("heading", { name: "Підтвердити повне повернення?" })).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Повторити той самий запит" }));
    await waitFor(() => { expect(requests).toHaveLength(2); });
    expect(requests[0]?.headers.get("Idempotency-Key")).toBe(requests[1]?.headers.get("Idempotency-Key"));
    expect(await requests[0]?.clone().json()).toEqual(await requests[1]?.clone().json());
  });

  it("locks an ambiguous cash movement to the exact retry across every close path", async () => {
    const requests: Request[] = [];
    mockFinanceApi({
      cashMovement: (request) => {
        requests.push(request);
        return requests.length === 1 ? Promise.reject(new Error("offline")) : Promise.resolve(jsonResponse(financeDepositResult, 201));
      },
    });
    render(<FinancePage />);
    fireEvent.click(await screen.findByRole("button", { name: "+ Внесення" }));
    const dialog = screen.getByRole("dialog", { name: "Внести готівку" });
    fireEvent.change(within(dialog).getByLabelText("Сума"), { target: { value: "300,50" } });
    fireEvent.change(within(dialog).getByLabelText("Причина"), { target: { value: "Розмінні кошти" } });
    fireEvent.change(within(dialog).getByPlaceholderText("Додаткова інформація про операцію"), { target: { value: "До вечірньої зміни" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Перейти до підтвердження" }));
    fireEvent.click(within(dialog).getByRole("button", { name: /Внести/ }));

    const alert = await within(dialog).findByRole("alert");
    await waitFor(() => { expect(alert).toHaveFocus(); });
    const close = within(dialog).getByRole("button", { name: "Закрити форму: внести готівку" });
    const back = within(dialog).getByRole("button", { name: "Назад до форми" });
    expect(close).toBeDisabled();
    expect(back).toBeDisabled();
    fireEvent.keyDown(document, { key: "Escape" });
    const layer = dialog.parentElement;
    if (layer === null) throw new Error("Cash movement dialog must have a modal layer.");
    fireEvent.mouseDown(layer);
    fireEvent.click(close);
    expect(within(dialog).getByRole("heading", { name: "Підтвердити внесення?" })).toBeInTheDocument();
    expect(document.body.style.overflow).toBe("hidden");

    fireEvent.click(within(dialog).getByRole("button", { name: "Повторити той самий запит" }));
    await waitFor(() => { expect(requests).toHaveLength(2); });
    expect(requests[0]?.headers.get("Idempotency-Key")).toBe(requests[1]?.headers.get("Idempotency-Key"));
    expect(await requests[0]?.clone().json()).toEqual(await requests[1]?.clone().json());
  });

  it("posts a deposit without patient or payment-method fields", async () => {
    const requests: Request[] = [];
    mockFinanceApi({ cashMovement: (request) => { requests.push(request); return Promise.resolve(jsonResponse(financeDepositResult, 201)); } });
    render(<FinancePage />);
    fireEvent.click(await screen.findByRole("button", { name: "+ Внесення" }));
    const dialog = screen.getByRole("dialog", { name: "Внести готівку" });
    expect(within(dialog).queryByLabelText(/пацієнт/i)).not.toBeInTheDocument();
    expect(within(dialog).queryByLabelText(/спосіб/i)).not.toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText("Сума"), { target: { value: "300,50" } });
    fireEvent.change(within(dialog).getByLabelText("Причина"), { target: { value: "  Розмінні кошти  " } });
    fireEvent.change(within(dialog).getByPlaceholderText("Додаткова інформація про операцію"), { target: { value: "  До вечірньої зміни  " } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Перейти до підтвердження" }));
    fireEvent.click(within(dialog).getByRole("button", { name: /Внести/ }));

    expect(await screen.findByRole("status")).toHaveTextContent("Внесення TXN-703600000003");
    expect(await requests[0]?.clone().json()).toEqual({
      type: "DEPOSIT",
      amount_minor: 30050,
      reason: "Розмінні кошти",
      comment: "До вечірньої зміни",
    });
  });

  it("blocks an excessive withdrawal and allows the exact available-cash boundary", async () => {
    const requests: Request[] = [];
    mockFinanceApi({ cashMovement: (request) => { requests.push(request); return Promise.resolve(jsonResponse(financeWithdrawalResult, 201)); } });
    render(<FinancePage />);
    fireEvent.click(await screen.findByRole("button", { name: "− Вилучення" }));
    const dialog = screen.getByRole("dialog", { name: "Вилучити готівку" });
    const amount = within(dialog).getByLabelText("Сума");
    fireEvent.change(amount, { target: { value: "500,01" } });
    fireEvent.change(within(dialog).getByLabelText("Причина"), { target: { value: "Інкасація" } });
    expect(within(dialog).getByRole("alert")).toHaveTextContent("доступно");
    expect(within(dialog).getByRole("button", { name: "Перейти до підтвердження" })).toBeDisabled();

    fireEvent.change(amount, { target: { value: "500" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Перейти до підтвердження" }));
    expect(within(dialog).getByText(/^0,00\s*₴$/)).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: /Вилучити/ }));
    await waitFor(() => { expect(requests).toHaveLength(1); });
    expect(await requests[0]?.clone().json()).toEqual({ type: "WITHDRAWAL", amount_minor: 50000, reason: "Інкасація", comment: "" });
  });

  it("refreshes available cash after a recoverable server conflict", async () => {
    const reducedShift = { ...cashShiftFixture, totals: { ...cashShiftFixture.totals, expected_cash_minor: 10000 } };
    mockFinanceApi({
      current: [responseFactory({ shift: cashShiftFixture }), responseFactory({ shift: reducedShift })],
      cashMovement: responseFactory({ code: "insufficient_cash", message: "Недостатньо готівки.", fields: {}, correlation_id: "cash-conflict" }, 409),
    });
    render(<FinancePage />);
    fireEvent.click(await screen.findByRole("button", { name: "− Вилучення" }));
    const dialog = screen.getByRole("dialog", { name: "Вилучити готівку" });
    fireEvent.change(within(dialog).getByLabelText("Сума"), { target: { value: "400" } });
    fireEvent.change(within(dialog).getByLabelText("Причина"), { target: { value: "Інкасація" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Перейти до підтвердження" }));
    fireEvent.click(within(dialog).getByRole("button", { name: /Вилучити/ }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Недостатньо готівки");
    expect(within(dialog).getByText(/100,00/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Перейти до підтвердження" })).toBeDisabled();
  });

  it("gates every mutation while the authoritative shift refreshes and after refresh failure", async () => {
    let rejectRefresh: ((reason?: unknown) => void) | undefined;
    const pendingRefresh = new Promise<Response>((_resolve, reject) => { rejectRefresh = reject; });
    mockFinanceApi({
      current: [
        responseFactory({ shift: cashShiftFixture }),
        () => pendingRefresh,
        responseFactory({ shift: cashShiftFixture }),
      ],
      payment: responseFactory(financePaymentResult, 201),
    });
    render(<FinancePage />);

    fireEvent.click(await screen.findByRole("button", { name: /^Оплатити / }));
    const dialog = screen.getByRole("dialog", { name: "Провести оплату прийому" });
    fireEvent.click(within(dialog).getByRole("radio", { name: "Картка" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Провести повну оплату" }));

    expect(await screen.findByRole("status", { name: /Оновлюємо касову зміну/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Провести оплату" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Оплатити / })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Повернення" })).not.toBeInTheDocument();

    await act(async () => {
      rejectRefresh?.(new Error("offline"));
      await pendingRefresh.catch(() => undefined);
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("Немає зв’язку із сервером");
    expect(screen.getByText("Касові операції недоступні до успішного оновлення зміни")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Поточна касова зміна" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Провести оплату" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Повторити" }));
    expect(await screen.findByRole("heading", { name: "Поточна касова зміна" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Провести оплату" })).toBeInTheDocument();
  });
});

describe("TP-1006 finance operation export", () => {
  beforeEach(() => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
  });

  afterEach(() => {
    document.cookie = "podoria_csrftoken=; max-age=0; path=/";
    document.body.style.overflow = "";
  });

  it("exports only applied main-list filters and keeps the loaded journal visible", async () => {
    let resolveFilteredList: ((response: Response) => void) | undefined;
    let resolveExport: ((response: Response) => void) | undefined;
    let downloadedFilename = "";
    let downloadedHref = "";
    const listRequests: Request[] = [];
    const exportRequests: Request[] = [];
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function captureDownload(this: HTMLAnchorElement) {
        downloadedFilename = this.download;
        downloadedHref = this.href;
      });
    mockFinanceApi({
      operations: (request) => {
        listRequests.push(request);
        if (listRequests.length === 1) return Promise.resolve(jsonResponse(financeOperationsFixture));
        return new Promise<Response>((resolve) => { resolveFilteredList = resolve; });
      },
      operationExports: [
        (request) => {
          exportRequests.push(request);
          return new Promise<Response>((resolve) => { resolveExport = resolve; });
        },
      ],
    });
    render(<FinancePage />);

    await screen.findByRole("table", { name: "Список фінансових операцій" });
    const exportButton = await screen.findByRole("button", { name: "Експортувати CSV" });
    fireEvent.change(screen.getByPlaceholderText("Пацієнт, телефон або номер"), { target: { value: "Марія" } });
    fireEvent.change(screen.getByLabelText("Тип"), { target: { value: "PAYMENT" } });
    fireEvent.change(screen.getByLabelText("Статус"), { target: { value: "PAID" } });
    fireEvent.change(screen.getByLabelText("Спосіб"), { target: { value: "CARD" } });
    fireEvent.change(screen.getByLabelText("Від дати"), { target: { value: "2026-07-24" } });
    fireEvent.change(screen.getByLabelText("До дати"), { target: { value: "2026-07-23" } });
    expect(exportButton).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Від дати"), { target: { value: "2026-07-22" } });
    fireEvent.click(screen.getByRole("button", { name: "Застосувати" }));
    expect(exportButton).toBeDisabled();
    resolveFilteredList?.(jsonResponse(financeOperationsFixture));
    await waitFor(() => { expect(exportButton).toBeEnabled(); });
    fireEvent.change(screen.getByPlaceholderText("Пацієнт, телефон або номер"), { target: { value: "ще-не-застосовано" } });
    fireEvent.click(exportButton);

    expect(screen.getByRole("button", { name: "Готуємо CSV…" })).toBeDisabled();
    expect(screen.getByRole("table", { name: "Список фінансових операцій" })).toBeInTheDocument();
    resolveExport?.(await csvResponse()(new Request("http://localhost/export")));

    expect(await screen.findByRole("status")).toHaveTextContent("Завантаження CSV фінансових операцій розпочато.");
    expect(exportRequests).toHaveLength(1);
    const exportUrl = new URL(exportRequests[0]?.url ?? "http://invalid");
    expect(exportUrl.searchParams.get("search")).toBe("Марія");
    expect(exportUrl.searchParams.get("type")).toBe("PAYMENT");
    expect(exportUrl.searchParams.get("status")).toBe("PAID");
    expect(exportUrl.searchParams.get("payment_method")).toBe("CARD");
    expect(exportUrl.searchParams.get("date_from")).toBe("2026-07-22");
    expect(exportUrl.searchParams.get("date_to")).toBe("2026-07-23");
    expect(exportUrl.searchParams.has("cursor")).toBe(false);
    expect(exportUrl.href).not.toContain(encodeURIComponent("ще-не-застосовано"));
    expect(exportRequests[0]?.headers.get("Accept")).toBe("text/csv");
    expect(downloadedFilename).toBe("finance-operations-20260723-100000.csv");
    expect(downloadedHref).toBe("blob:inventory-export");
    anchorClick.mockRestore();
  });

  it("keeps rows after an export error and retries the same applied projection", async () => {
    const exportRequests: Request[] = [];
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    mockFinanceApi({
      operationExports: [
        (request) => {
          exportRequests.push(request);
          return Promise.resolve(jsonResponse({
            code: "finance_operation_export_too_large",
            message: "Експорт містить забагато фінансових операцій. Звузьте фільтри.",
            fields: { filters: ["Максимум 5000 операцій за один файл."] },
            correlation_id: "tp-1006-test",
          }, 422));
        },
        (request) => {
          exportRequests.push(request);
          return csvResponse()(request);
        },
      ],
    });
    render(<FinancePage />);

    await screen.findByRole("table", { name: "Список фінансових операцій" });
    fireEvent.click(await screen.findByRole("button", { name: "Експортувати CSV" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Експорт містить забагато фінансових операцій.");
    expect(screen.getByRole("table", { name: "Список фінансових операцій" })).toBeInTheDocument();
    expect(anchorClick).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Повторити export" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Завантаження CSV фінансових операцій розпочато.");
    expect(exportRequests).toHaveLength(2);
    expect(new URL(exportRequests[0]?.url ?? "http://invalid").search).toBe(
      new URL(exportRequests[1]?.url ?? "http://invalid").search,
    );
    expect(anchorClick).toHaveBeenCalledTimes(1);
    anchorClick.mockRestore();
  });

  it("does not expose the admin export control to reception", async () => {
    mockFinanceApi({ session: receptionSession });
    render(<FinancePage />);

    await screen.findByRole("table", { name: "Список фінансових операцій" });
    expect(screen.queryByRole("button", { name: "Експортувати CSV" })).not.toBeInTheDocument();
  });
});
