import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { adminSession, cashShiftFixture, jsonResponse } from "../test/setup";
import type { CashShiftProjection, CashShiftSummary } from "./cashShiftTypes";

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

function summarize(shift: CashShiftProjection): CashShiftSummary {
  return {
    id: shift.id,
    public_number: shift.public_number,
    status: shift.status,
    employee: shift.employee,
    opened_at: shift.opened_at,
    closed_at: shift.closed_at,
    totals: shift.totals,
    reconciliation: shift.reconciliation,
  };
}

const openSummary = summarize(openShift);
const closedSummary = summarize(closedShift);

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location-probe">{location.pathname}{location.search}</output>;
}

function renderApp(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><LocationProbe /><App /></MemoryRouter>);
}

function preview(shift: CashShiftProjection) {
  return { shift, unpaid: { count: 0, total_minor: 0 } };
}

afterEach(() => {
  document.body.style.overflow = "";
});

describe("TP-704 close and history parent flow", () => {
  it("refreshes current and operations, then navigates a current close to authoritative history detail", async () => {
    const currentResponses = [{ shift: openShift }, { shift: null }];
    const requests: Request[] = [];
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      requests.push(request);
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (url.pathname === "/api/v1/cash-shifts/current") return Promise.resolve(jsonResponse(currentResponses.shift() ?? { shift: null }));
      if (url.pathname === "/api/v1/finance/operations") return Promise.resolve(jsonResponse({ operations: [], next_cursor: null }));
      if (url.pathname.endsWith("/close-preview")) return Promise.resolve(jsonResponse(preview(openShift)));
      if (url.pathname.endsWith("/close") && request.method === "POST") return Promise.resolve(jsonResponse({ shift: closedShift, replayed: false }, 201));
      if (url.pathname === "/api/v1/cash-shifts" && request.method === "GET") return Promise.resolve(jsonResponse({ shifts: [closedSummary], next_cursor: null }));
      if (url.pathname === `/api/v1/cash-shifts/${openShift.id}` && request.method === "GET") return Promise.resolve(jsonResponse(closedShift));
      if (url.pathname === "/api/v1/users") return Promise.resolve(jsonResponse({ users: [] }));
      return Promise.resolve(jsonResponse({ code: "not_found", message: "Not found", fields: {}, correlation_id: "flow" }, 404));
    });

    renderApp("/finance");
    fireEvent.click(await screen.findByRole("button", { name: "Закрити зміну" }));
    const closeDialog = screen.getByRole("dialog", { name: "Закрити касову зміну?" });
    fireEvent.change(await within(closeDialog).findByLabelText("Фактично в касі"), { target: { value: "500" } });
    fireEvent.click(within(closeDialog).getByRole("checkbox", { name: /Готівку перераховано/ }));
    fireEvent.click(within(closeDialog).getByRole("button", { name: "Закрити зміну" }));

    await waitFor(() => {
      expect(screen.getByTestId("location-probe")).toHaveTextContent(`/finance/shifts?shift=${openShift.id}`);
    });
    expect(await screen.findByRole("dialog", { name: closedShift.public_number })).toBeInTheDocument();
    expect(screen.getByText(`Касову зміну ${closedShift.public_number} закрито.`)).toBeInTheDocument();
    expect(requests.filter((request) => new URL(request.url).pathname === "/api/v1/cash-shifts/current")).toHaveLength(2);
    expect(requests.filter((request) => new URL(request.url).pathname === "/api/v1/finance/operations")).toHaveLength(2);
    expect(requests.some((request) => new URL(request.url).pathname === "/api/v1/cash-shifts")).toBe(true);
  });

  it("returns from OPEN detail to close and replaces it with closed authoritative detail on success", async () => {
    const listResponses = [
      { shifts: [openSummary satisfies CashShiftSummary], next_cursor: null },
      { shifts: [closedSummary satisfies CashShiftSummary], next_cursor: null },
    ];
    const requests: Request[] = [];
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      requests.push(request);
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (url.pathname === "/api/v1/users") return Promise.resolve(jsonResponse({ users: [] }));
      if (url.pathname === "/api/v1/cash-shifts" && request.method === "GET") return Promise.resolve(jsonResponse(listResponses.shift() ?? { shifts: [closedSummary], next_cursor: null }));
      if (url.pathname === `/api/v1/cash-shifts/${openShift.id}` && request.method === "GET") return Promise.resolve(jsonResponse(openShift));
      if (url.pathname.endsWith("/close-preview")) return Promise.resolve(jsonResponse(preview(openShift)));
      if (url.pathname.endsWith("/close") && request.method === "POST") return Promise.resolve(jsonResponse({ shift: closedShift, replayed: false }, 201));
      return Promise.resolve(jsonResponse({ code: "not_found", message: "Not found", fields: {}, correlation_id: "flow" }, 404));
    });

    renderApp("/finance/shifts");
    fireEvent.click(await screen.findByRole("button", { name: `Відкрити деталі ${openShift.public_number}` }));
    let detail = await screen.findByRole("dialog", { name: openShift.public_number });
    fireEvent.click(within(detail).getByRole("button", { name: "Закрити зміну" }));
    let closeDialog = await screen.findByRole("dialog", { name: "Закрити касову зміну?" });
    await within(closeDialog).findByLabelText("Фактично в касі");
    fireEvent.click(within(closeDialog).getByRole("button", { name: "Скасувати" }));

    detail = await screen.findByRole("dialog", { name: openShift.public_number });
    expect(within(detail).getByRole("button", { name: "Закрити зміну" })).toBeInTheDocument();
    fireEvent.click(within(detail).getByRole("button", { name: "Закрити зміну" }));
    closeDialog = await screen.findByRole("dialog", { name: "Закрити касову зміну?" });
    fireEvent.change(await within(closeDialog).findByLabelText("Фактично в касі"), { target: { value: "500" } });
    fireEvent.click(within(closeDialog).getByRole("checkbox", { name: /Готівку перераховано/ }));
    fireEvent.click(within(closeDialog).getByRole("button", { name: "Закрити зміну" }));

    detail = await screen.findByRole("dialog", { name: closedShift.public_number });
    expect(within(detail).queryByRole("button", { name: "Закрити зміну" })).not.toBeInTheDocument();
    expect(within(detail).getByText("Закриту зміну не можна редагувати, видалити або відкрити повторно.")).toBeInTheDocument();
    await waitFor(() => {
      expect(requests.filter((request) => new URL(request.url).pathname === "/api/v1/cash-shifts")).toHaveLength(2);
    });
  });
});
