import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../auth/AuthContext";
import { GlobalSearchOverlay } from "./GlobalSearchOverlay";
import type { GlobalSearchApiResult, GlobalSearchResponse } from "./searchTypes";

const patientGroup = {
  type: "patients",
  has_more: false,
  items: [{
    type: "patient",
    id: "c49d72c2-689d-4f54-91df-9a63845a02e7",
    title: "Марія Бондар",
    subtitle: "+380 93 112 40 18 · PT-00184",
    meta: "Наступний запис сьогодні",
    deep_link: "/patients/c49d72c2-689d-4f54-91df-9a63845a02e7/overview",
  }],
} as const;

const appointmentGroup = {
  type: "appointments",
  has_more: true,
  items: [{
    type: "appointment",
    id: "e18dc976-94dc-4f6a-bf66-57139bea10fa",
    title: "Марія Бондар · сьогодні, 09:00",
    subtitle: "Первинна консультація · Олена Подолог",
    meta: "A-18DC97694DC6 · Підтверджено",
    deep_link: "/calendar?appointment=e18dc976-94dc-4f6a-bf66-57139bea10fa",
  }],
} as const;

const searchResponse: GlobalSearchResponse = {
  query: "Марія",
  groups: [patientGroup, appointmentGroup],
  returned_count: 2,
};

function ok(data: GlobalSearchResponse = searchResponse): GlobalSearchApiResult {
  return { ok: true, data };
}

function renderOverlay(search: (query: string, signal: AbortSignal) => Promise<GlobalSearchApiResult>) {
  const onClose = vi.fn();
  const onNavigate = vi.fn();
  render(
    <MemoryRouter>
      <AuthProvider>
        <GlobalSearchOverlay onClose={onClose} onNavigate={onNavigate} search={search} />
      </AuthProvider>
    </MemoryRouter>,
  );
  return { onClose, onNavigate };
}

describe("TP-801 global search overlay", () => {
  it("waits for two characters, debounces, and renders only server-returned groups", async () => {
    const search = vi.fn<(query: string, signal: AbortSignal) => Promise<GlobalSearchApiResult>>()
      .mockResolvedValue(ok());
    renderOverlay(search);

    const input = screen.getByRole("combobox", { name: "Пошуковий запит" });
    await waitFor(() => { expect(input).toHaveFocus(); });
    fireEvent.change(input, { target: { value: "М" } });
    expect(screen.getByText("Потрібно ще один символ")).toBeInTheDocument();
    expect(search).not.toHaveBeenCalled();

    fireEvent.change(input, { target: { value: "Марія" } });
    expect(screen.getByText("Готуємо пошук…")).toBeInTheDocument();
    await waitFor(() => { expect(search).toHaveBeenCalledTimes(1); });

    expect(await screen.findByText("Пацієнти", { selector: "h3" })).toBeInTheDocument();
    expect(screen.getByText("Записи", { selector: "h3" })).toBeInTheDocument();
    expect(screen.queryByText("Оплати", { selector: "h3" })).not.toBeInTheDocument();
    expect(screen.queryByText("Матеріали", { selector: "h3" })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: /\+380 93 112/ })).toHaveAttribute(
      "href",
      patientGroup.items[0].deep_link,
    );
    expect(screen.getByText("Є ще — уточніть запит")).toBeInTheDocument();
  });

  it("supports arrow navigation, Enter activation, and Escape close", async () => {
    HTMLElement.prototype.scrollIntoView = vi.fn();
    const search = vi.fn<(query: string, signal: AbortSignal) => Promise<GlobalSearchApiResult>>()
      .mockResolvedValue(ok());
    const { onClose, onNavigate } = renderOverlay(search);
    const input = screen.getByRole("combobox", { name: "Пошуковий запит" });
    fireEvent.change(input, { target: { value: "Марія" } });
    await screen.findAllByRole("option");

    fireEvent.keyDown(input, { key: "ArrowDown" });
    const options = screen.getAllByRole("option");
    expect(options[1]).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onNavigate).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("aborts a stale request so the latest query owns the results", async () => {
    let firstSignal: AbortSignal | null = null;
    const search = vi.fn((query: string, signal: AbortSignal): Promise<GlobalSearchApiResult> => {
      if (query === "Ма") {
        firstSignal = signal;
        return new Promise(() => undefined);
      }
      return Promise.resolve(ok({
        query,
        groups: [{ ...patientGroup, items: [{ ...patientGroup.items[0], title: "Наталія Коваль" }] }],
        returned_count: 1,
      }));
    });
    renderOverlay(search);
    const input = screen.getByRole("combobox", { name: "Пошуковий запит" });

    fireEvent.change(input, { target: { value: "Ма" } });
    await waitFor(() => { expect(search).toHaveBeenCalledTimes(1); });
    fireEvent.change(input, { target: { value: "Наталія" } });
    await screen.findByText("Наталія Коваль");

    expect(firstSignal).not.toBeNull();
    expect((firstSignal as AbortSignal | null)?.aborted).toBe(true);
    expect(screen.queryByText("Марія Бондар", { selector: "strong" })).not.toBeInTheDocument();
  });

  it("shows correlation-safe errors, retries the same query, and exposes role-safe create links", async () => {
    const search = vi.fn<(query: string, signal: AbortSignal) => Promise<GlobalSearchApiResult>>()
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        error: {
          code: "service_unavailable",
          message: "Пошук тимчасово недоступний.",
          fields: {},
          correlation_id: "search-request-801",
        },
      })
      .mockResolvedValueOnce(ok());
    renderOverlay(search);
    fireEvent.change(screen.getByRole("combobox", { name: "Пошуковий запит" }), { target: { value: "Марія" } });

    expect(await screen.findByRole("alert")).toHaveTextContent("Пошук тимчасово недоступний");
    expect(screen.getByRole("alert")).toHaveTextContent("search-request-801");
    fireEvent.click(screen.getByRole("button", { name: "Повторити" }));
    await screen.findByText("Пацієнти", { selector: "h3" });
    expect(search).toHaveBeenNthCalledWith(2, "Марія", expect.any(AbortSignal));

    expect(await screen.findByRole("link", { name: /Новий пацієнт/ })).toHaveAttribute("href", "/patients?compose=patient");
    expect(screen.getByRole("link", { name: /Новий запис/ })).toHaveAttribute("href", "/calendar?compose=appointment");
  });
});
