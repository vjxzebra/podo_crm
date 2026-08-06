import axe from "axe-core";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { cashShiftFixture, jsonResponse } from "../test/setup";
import type {
  CashShiftClosePreview,
  CashShiftCloseResponse,
  CashShiftProjection,
} from "./cashShiftTypes";
import { CloseCashShiftDialog } from "./CloseCashShiftDialog";

type ResponseFactory = (request: Request) => Promise<Response>;

const openShift = {
  ...cashShiftFixture,
  entries: cashShiftFixture.entries.map((entry) => ({ ...entry })),
  closed_at: null,
  reconciliation: null,
} satisfies CashShiftProjection;

const closedShift = {
  ...openShift,
  status: "CLOSED",
  closed_at: "2026-07-22T16:15:00Z",
  reconciliation: {
    expected_cash_minor: 50000,
    actual_cash_minor: 50000,
    discrepancy_minor: 0,
    comment: "",
    closed_by: openShift.employee,
  },
} satisfies CashShiftProjection;

const preview = {
  shift: openShift,
  unpaid: { count: 2, total_minor: 180000 },
} satisfies CashShiftClosePreview;

function response(body: unknown, status = 200): ResponseFactory {
  return () => Promise.resolve(jsonResponse(body, status));
}

function mockCloseApi({
  previews = [response(preview)],
  closes = [response({ shift: closedShift, replayed: false } satisfies CashShiftCloseResponse, 201)],
  detail = response(closedShift),
}: {
  readonly previews?: readonly ResponseFactory[];
  readonly closes?: readonly ResponseFactory[];
  readonly detail?: ResponseFactory;
} = {}) {
  const previewQueue = [...previews];
  const closeQueue = [...closes];
  const requests: Request[] = [];
  vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const request = input instanceof Request ? input : new Request(input, init);
    requests.push(request);
    const url = new URL(request.url);
    if (url.pathname.endsWith("/close-preview") && request.method === "GET") {
      const factory = previewQueue.shift() ?? previews[previews.length - 1];
      return factory?.(request) ?? Promise.resolve(jsonResponse(preview));
    }
    if (url.pathname.endsWith("/close") && request.method === "POST") {
      const factory = closeQueue.shift() ?? closes[closes.length - 1];
      return factory?.(request) ?? Promise.resolve(jsonResponse({ shift: closedShift, replayed: false }, 201));
    }
    if (url.pathname === `/api/v1/cash-shifts/${openShift.id}` && request.method === "GET") {
      return detail(request);
    }
    return Promise.resolve(jsonResponse({ code: "not_found", message: "Not found", fields: {}, correlation_id: "close-test" }, 404));
  });
  return requests;
}

function renderDialog(onSuccess = vi.fn<(result: CashShiftCloseResponse) => void>()) {
  render(<CloseCashShiftDialog onClose={vi.fn()} onSuccess={onSuccess} shiftId={openShift.id} shiftNumber={openShift.public_number} />);
  return onSuccess;
}

async function fillBalancedClose(dialog: HTMLElement) {
  const actual = await within(dialog).findByLabelText("Фактично в касі");
  fireEvent.change(actual, { target: { value: "500" } });
  fireEvent.click(within(dialog).getByRole("checkbox", { name: /Готівку перераховано/ }));
}

describe("TP-704 cash-shift reconciliation", () => {
  beforeEach(() => {
    document.cookie = "podoria_csrftoken=test-csrf; path=/";
  });

  afterEach(() => {
    document.cookie = "podoria_csrftoken=; max-age=0; path=/";
    document.body.style.overflow = "";
  });

  it("starts blank, accepts zero, requires a discrepancy comment and resets counted on amount changes", async () => {
    mockCloseApi();
    renderDialog();
    const dialog = screen.getByRole("dialog", { name: "Закрити касову зміну?" });
    const actual = await within(dialog).findByLabelText("Фактично в касі");
    const counted = within(dialog).getByRole("checkbox", { name: /Готівку перераховано/ });
    const submit = within(dialog).getByRole("button", { name: "Закрити зміну" });

    expect(within(dialog).getByText(/Початок/)).toHaveTextContent(/перша зміна каси/);
    expect(actual).toHaveValue("");
    expect(counted).toBeDisabled();
    expect(submit).toBeDisabled();

    fireEvent.change(actual, { target: { value: "0" } });
    expect(within(dialog).getByText(/Нестача/)).toBeInTheDocument();
    expect(counted).toBeEnabled();
    fireEvent.click(counted);
    expect(submit).toBeDisabled();
    fireEvent.change(within(dialog).getByPlaceholderText("Поясніть надлишок або нестачу"), { target: { value: "Перераховано двічі" } });
    expect(submit).toBeEnabled();

    fireEvent.change(actual, { target: { value: "500" } });
    expect(counted).not.toBeChecked();
    expect(within(dialog).getByText("Каса зійшлася")).toBeInTheDocument();
    expect(submit).toBeDisabled();
  });

  it("freezes the exact body and idempotency key after an ambiguous network result", async () => {
    const requests = mockCloseApi({
      closes: [() => Promise.reject(new Error("offline")), response({ shift: closedShift, replayed: true })],
    });
    const onSuccess = renderDialog();
    const dialog = screen.getByRole("dialog", { name: "Закрити касову зміну?" });
    await fillBalancedClose(dialog);
    fireEvent.click(within(dialog).getByRole("button", { name: "Закрити зміну" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("ключ заблоковано");
    expect(within(dialog).getByLabelText("Фактично в касі")).toBeDisabled();
    expect(within(dialog).getByRole("button", { name: "Закрити звірку касової зміни" })).toBeDisabled();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("dialog", { name: "Закрити касову зміну?" })).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: "Повторити той самий запит" }));
    await waitFor(() => { expect(onSuccess).toHaveBeenCalledTimes(1); });
    const closeRequests = requests.filter((request) => new URL(request.url).pathname.endsWith("/close"));
    expect(closeRequests).toHaveLength(2);
    expect(closeRequests[0]?.headers.get("Idempotency-Key")).toBe(closeRequests[1]?.headers.get("Idempotency-Key"));
    await expect(closeRequests[0]?.clone().text()).resolves.toBe(await closeRequests[1]?.clone().text());
  });

  it("treats a 5xx close response as ambiguous and offers only exact retry", async () => {
    mockCloseApi({
      closes: [response({ code: "server_error", message: "Proxy failed", fields: {}, correlation_id: "proxy" }, 502)],
    });
    renderDialog();
    const dialog = screen.getByRole("dialog", { name: "Закрити касову зміну?" });
    await fillBalancedClose(dialog);
    fireEvent.click(within(dialog).getByRole("button", { name: "Закрити зміну" }));

    expect(await within(dialog).findByRole("button", { name: "Повторити той самий запит" })).toBeEnabled();
    expect(within(dialog).getByLabelText("Фактично в касі")).toBeDisabled();
  });

  it("clears a stale preview and keeps submit disabled when the conflict refresh fails", async () => {
    mockCloseApi({
      previews: [response(preview), () => Promise.reject(new Error("offline")), response({
        ...preview,
        shift: { ...openShift, totals: { ...openShift.totals, operations_count: 3, expected_cash_minor: 60000 } },
      })],
      closes: [response({ code: "cash_shift_changed", message: "Зміна оновилась.", fields: {}, correlation_id: "stale" }, 409)],
    });
    renderDialog();
    const dialog = screen.getByRole("dialog", { name: "Закрити касову зміну?" });
    await fillBalancedClose(dialog);
    fireEvent.click(within(dialog).getByRole("button", { name: "Закрити зміну" }));

    expect(await within(dialog).findByText("Не вдалося підготувати звірку")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Закрити зміну" })).toBeDisabled();
    expect(within(dialog).queryByLabelText("Фактично в касі")).not.toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: "Повторити" }));
    const actual = await within(dialog).findByLabelText("Фактично в касі");
    expect(actual).toHaveValue("500");
    expect(within(dialog).getByRole("checkbox", { name: /Готівку перераховано/ })).not.toBeChecked();
    expect(within(dialog).getByText(/Нестача/)).toBeInTheDocument();
  });

  it("recovers an already-closed response through authoritative detail", async () => {
    mockCloseApi({
      closes: [response({ code: "cash_shift_already_closed", message: "Зміну вже закрито.", fields: {}, correlation_id: "closed" }, 409)],
      detail: response(closedShift),
    });
    const onSuccess = renderDialog();
    const dialog = screen.getByRole("dialog", { name: "Закрити касову зміну?" });
    await fillBalancedClose(dialog);
    fireEvent.click(within(dialog).getByRole("button", { name: "Закрити зміну" }));

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith({ shift: closedShift, replayed: true });
    });
  });

  it("guards dirty dismissal and has no detectable accessibility violations", async () => {
    mockCloseApi();
    const onClose = vi.fn();
    const { container } = render(<CloseCashShiftDialog onClose={onClose} onSuccess={vi.fn()} shiftId={openShift.id} shiftNumber={openShift.public_number} />);
    const dialog = screen.getByRole("dialog", { name: "Закрити касову зміну?" });
    const actual = await within(dialog).findByLabelText("Фактично в касі");
    fireEvent.change(actual, { target: { value: "500" } });
    fireEvent.keyDown(document, { key: "Escape" });

    expect(within(dialog).getByRole("heading", { name: "Відхилити введені дані?" })).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
    const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(results.violations).toEqual([]);
  });
});
