import axe from "axe-core";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { App } from "../App";
import {
  adminSession,
  clinicProfile,
  clinicRoom,
  jsonResponse,
} from "../test/setup";
import { DiscountSettings } from "./DiscountSettings";

const activeDiscount = {
  id: "2d40a435-1ff4-49f8-993e-7507ec1456f9",
  name: "Постійний клієнт",
  percent: 10,
  is_active: true,
  version: 1,
  created_at: "2026-08-06T08:00:00Z",
  updated_at: "2026-08-06T08:00:00Z",
} as const;

const inactiveDiscount = {
  ...activeDiscount,
  id: "a010ea40-e2c9-4d2a-891f-42ccae53a131",
  name: "Архівна знижка",
  percent: 5,
  is_active: false,
} as const;

const inactivePolicy = {
  key: "default",
  is_active: false,
  every_n: 5,
  discount: activeDiscount,
  version: 1,
  started_at: null,
  updated_at: "2026-08-06T08:00:00Z",
} as const;

function requestFrom(input: RequestInfo | URL, init?: RequestInit): Request {
  return input instanceof Request ? input : new Request(input, init);
}

describe("TP-1018 discount settings", () => {
  it("mounts the discounts section from the administrator-only settings tab", async () => {
    vi.mocked(fetch).mockImplementation((input, init) => {
      const request = requestFrom(input, init);
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (url.pathname === "/api/v1/clinic-profile") return Promise.resolve(jsonResponse(clinicProfile));
      if (url.pathname === "/api/v1/rooms") return Promise.resolve(jsonResponse({ rooms: [clinicRoom] }));
      if (url.pathname === "/api/v1/discounts") {
        return Promise.resolve(jsonResponse({ discounts: [activeDiscount, inactiveDiscount] }));
      }
      if (url.pathname === "/api/v1/loyalty-policy") {
        return Promise.resolve(jsonResponse(inactivePolicy));
      }
      return Promise.resolve(jsonResponse({}, 404));
    });
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <App />
      </MemoryRouter>,
    );
    await screen.findByRole("heading", { name: "Налаштування кабінету" });
    expect(screen.getByText("Тільки адміністратор")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("settings-discounts-tab"));
    expect(await screen.findByRole("heading", { name: "Знижки" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Програма лояльності" })).toBeInTheDocument();
  });

  it("creates, edits and deactivates a catalog discount with optimistic versions", async () => {
    const seasonalId = "0b5f7c67-bc41-4553-9387-fb39db47bb56";
    let catalog = [activeDiscount, inactiveDiscount] as {
      id: string;
      name: string;
      percent: number;
      is_active: boolean;
      version: number;
      created_at: string;
      updated_at: string;
    }[];
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const request = requestFrom(input, init);
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/discounts" && request.method === "GET") {
        return jsonResponse({ discounts: catalog });
      }
      if (url.pathname === "/api/v1/loyalty-policy" && request.method === "GET") {
        return jsonResponse(inactivePolicy);
      }
      if (url.pathname === "/api/v1/discounts" && request.method === "POST") {
        const body = await request.clone().json() as {
          name: string;
          percent: number;
          is_active: boolean;
        };
        const created = {
          id: seasonalId,
          ...body,
          version: 1,
          created_at: "2026-08-06T09:00:00Z",
          updated_at: "2026-08-06T09:00:00Z",
        };
        catalog = [...catalog, created];
        return jsonResponse(created, 201);
      }
      if (url.pathname === `/api/v1/discounts/${seasonalId}` && request.method === "PATCH") {
        const body = await request.clone().json() as {
          name?: string;
          percent?: number;
          is_active?: boolean;
          version: number;
        };
        const current = catalog.find((discount) => discount.id === seasonalId);
        if (current === undefined) throw new Error("Seasonal discount is missing");
        const updated = {
          ...current,
          ...body,
          version: current.version + 1,
          updated_at: "2026-08-06T10:00:00Z",
        };
        catalog = catalog.map((discount) => discount.id === seasonalId ? updated : discount);
        return jsonResponse(updated);
      }
      return jsonResponse({
        code: "not_found",
        message: "Not found",
        fields: {},
        correlation_id: "discount-settings",
      }, 404);
    });

    render(<DiscountSettings />);
    expect(await screen.findByRole("heading", { name: "Знижки" })).toBeInTheDocument();
    expect(screen.getByText("Архівна знижка")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Додати знижку" }));
    const dialog = screen.getByRole("dialog", { name: "Нова знижка" });
    fireEvent.change(within(dialog).getByLabelText("Назва знижки"), {
      target: { value: "Сезонна" },
    });
    fireEvent.change(within(dialog).getByLabelText(/Відсоток/), {
      target: { value: "12" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Створити знижку" }));
    expect(await screen.findByText("Знижку «Сезонна» створено.")).toBeInTheDocument();

    const createdRow = screen.getByText("Сезонна").closest("article");
    if (createdRow === null) throw new Error("Created discount row is missing");
    fireEvent.click(within(createdRow).getByRole("button", { name: "Редагувати" }));
    const editDialog = screen.getByRole("dialog", { name: "Редагувати знижку" });
    fireEvent.change(within(editDialog).getByLabelText(/Відсоток/), {
      target: { value: "15" },
    });
    fireEvent.click(within(editDialog).getByRole("button", { name: "Зберегти зміни" }));
    expect(await screen.findByText("Знижку «Сезонна» оновлено.")).toBeInTheDocument();

    const updatedRow = screen.getByText("Сезонна").closest("article");
    if (updatedRow === null) throw new Error("Updated discount row is missing");
    expect(within(updatedRow).getByLabelText("15 відсотків")).toBeInTheDocument();
    fireEvent.click(within(updatedRow).getByRole("button", { name: "Деактивувати" }));
    expect(await screen.findByText("Знижку «Сезонна» деактивовано.")).toBeInTheDocument();
    expect(within(updatedRow).getByText("Неактивна")).toBeInTheDocument();

    const requests = vi.mocked(fetch).mock.calls
      .map(([input, init]) => requestFrom(input, init))
      .filter((request) => request.url.includes("/api/v1/discounts"));
    const bodies = await Promise.all(requests
      .filter((request) => request.method !== "GET")
      .map((request) => request.clone().json()));
    expect(bodies).toEqual([
      { name: "Сезонна", percent: 12, is_active: true },
      { name: "Сезонна", percent: 15, is_active: true, version: 1 },
      { is_active: false, version: 2 },
    ]);
  });

  it("keeps a stale loyalty policy conflict recoverable and sends its current version", async () => {
    let policy = inactivePolicy as {
      key: "default";
      is_active: boolean;
      every_n: number;
      discount: typeof activeDiscount | null;
      version: number;
      started_at: string | null;
      updated_at: string;
    };
    let patchCount = 0;
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      const request = requestFrom(input, init);
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/discounts" && request.method === "GET") {
        return Promise.resolve(jsonResponse({ discounts: [activeDiscount] }));
      }
      if (url.pathname === "/api/v1/loyalty-policy" && request.method === "GET") {
        return Promise.resolve(jsonResponse(policy));
      }
      if (url.pathname === "/api/v1/loyalty-policy" && request.method === "PATCH") {
        patchCount += 1;
        policy = { ...policy, version: 2, updated_at: "2026-08-06T11:00:00Z" };
        return Promise.resolve(jsonResponse({
          code: "stale_version",
          message: "Програму лояльності уже змінено.",
          fields: {},
          correlation_id: "loyalty-stale",
        }, 409));
      }
      return Promise.resolve(jsonResponse({}, 404));
    });

    render(<DiscountSettings />);
    await screen.findByRole("heading", { name: "Програма лояльності" });
    fireEvent.click(screen.getByRole("checkbox", { name: /Програма активна/ }));
    fireEvent.change(screen.getByLabelText("Кожен N-й візит"), { target: { value: "7" } });
    fireEvent.change(screen.getByLabelText("Знижка для N-го візиту"), {
      target: { value: activeDiscount.id },
    });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти програму" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("іншій сесії");
    const patchRequest = vi.mocked(fetch).mock.calls
      .map(([input, init]) => requestFrom(input, init))
      .find((request) => request.url.endsWith("/api/v1/loyalty-policy") && request.method === "PATCH");
    if (patchRequest === undefined) throw new Error("Expected loyalty policy PATCH request");
    expect(await patchRequest.clone().json()).toEqual({
      is_active: true,
      every_n: 7,
      discount_id: activeDiscount.id,
      version: 1,
    });

    fireEvent.click(screen.getByRole("button", { name: "Оновити дані" }));
    await waitFor(() => { expect(screen.getByText("Версія налаштувань: 2")).toBeInTheDocument(); });
    expect(patchCount).toBe(1);
  });

  it("has no detectable accessibility violations in the catalog and editor", async () => {
    vi.mocked(fetch).mockImplementation((input, init) => {
      const request = requestFrom(input, init);
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/discounts") {
        return Promise.resolve(jsonResponse({ discounts: [activeDiscount, inactiveDiscount] }));
      }
      if (url.pathname === "/api/v1/loyalty-policy") {
        return Promise.resolve(jsonResponse(inactivePolicy));
      }
      return Promise.resolve(jsonResponse({}, 404));
    });
    const { container } = render(<DiscountSettings />);
    await screen.findByRole("heading", { name: "Знижки" });
    fireEvent.click(screen.getByRole("button", { name: "Додати знижку" }));
    await screen.findByRole("dialog", { name: "Нова знижка" });

    const results = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(results.violations).toEqual([]);
  });
});
