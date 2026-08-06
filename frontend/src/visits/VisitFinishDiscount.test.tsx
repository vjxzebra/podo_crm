import axe from "axe-core";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { App } from "../App";
import {
  adminSession,
  clinicService,
  jsonResponse,
  loyaltyEligibleVisitLoyalty,
  visitFixture,
} from "../test/setup";

const smallerDiscount = {
  id: "9c2f1f0e-6b8a-4a1d-9f7c-2b5d3e4a6c81",
  name: "Разова 5%",
  percent: 5,
  is_active: true,
  version: 1,
  created_at: "2026-08-06T08:00:00Z",
  updated_at: "2026-08-06T08:00:00Z",
} as const;

const manualDiscount = {
  id: "2d40a435-1ff4-49f8-993e-7507ec1456f9",
  name: "Постійний клієнт",
  percent: 10,
  is_active: true,
  version: 1,
  created_at: "2026-08-06T08:00:00Z",
  updated_at: "2026-08-06T08:00:00Z",
} as const;

function requestFrom(input: RequestInfo | URL, init?: RequestInit): Request {
  return input instanceof Request ? input : new Request(input, init);
}

async function openFinishStep() {
  await screen.findByRole("heading", { name: visitFixture.patient.display_name, level: 1 });
  fireEvent.click(screen.getByRole("button", { name: "Далі: послуги й матеріали" }));
  fireEvent.click(screen.getByRole("button", { name: "Далі: фото" }));
  fireEvent.click(screen.getByRole("button", { name: "Далі: завершення" }));
  await screen.findByRole("heading", { name: "Перевірка та завершення", level: 2 });
}

function renderVisit() {
  return render(
    <MemoryRouter initialEntries={[`/visits/${visitFixture.id}`]}>
      <App />
    </MemoryRouter>,
  );
}

describe("TP-1019 visit finish discount", () => {
  it("previews gross/discount/net, submits optional discount_id and shows authoritative pricing", async () => {
    const netMinor = 108000;
    const completedVisit = {
      ...visitFixture,
      status: "COMPLETED",
      version: 2,
      total_minor: netMinor,
      payment_handoff_requested: true,
      editable: false,
      completed_at: "2026-08-06T10:00:00Z",
      appointment: {
        ...visitFixture.appointment,
        status_code: "COMPLETED",
        status_label: "Завершено",
      },
    } as const;
    const finishResponse = {
      replayed: false,
      visit: completedVisit,
      receivable: {
        id: "4ef6696a-51f8-4df6-b230-2131c77f5d26",
        amount_minor: netMinor,
        status: "OPEN",
        created_at: "2026-08-06T10:00:00Z",
      },
      pricing: {
        gross_minor: clinicService.price_minor,
        discount_id: manualDiscount.id,
        discount_name: manualDiscount.name,
        discount_percent: manualDiscount.percent,
        discount_source: "PODOLOGIST",
        discount_amount_minor: 12000,
        net_minor: netMinor,
        version: 1,
        state: "OPEN",
      },
      inventory_operation_id: null,
      movement_ids: [],
      follow_up_appointment_id: null,
    } as const;
    vi.mocked(fetch).mockImplementation((input, init) => {
      const request = requestFrom(input, init);
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (url.pathname === `/api/v1/visits/${visitFixture.id}` && request.method === "GET") {
        return Promise.resolve(jsonResponse(visitFixture));
      }
      if (url.pathname === "/api/v1/services" && request.method === "GET") {
        return Promise.resolve(jsonResponse({ services: [clinicService] }));
      }
      if (url.pathname === "/api/v1/discounts" && request.method === "GET") {
        return Promise.resolve(jsonResponse({ discounts: [manualDiscount] }));
      }
      if (url.pathname.endsWith("/finish") && request.method === "POST") {
        return Promise.resolve(jsonResponse(finishResponse, 201));
      }
      return Promise.resolve(jsonResponse({
        code: "not_found",
        message: "Not found",
        fields: {},
        correlation_id: "visit-discount",
      }, 404));
    });

    const { container } = renderVisit();
    await openFinishStep();
    const option = await screen.findByRole("option", { name: "Постійний клієнт · 10%" });
    expect(option).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Ручна знижка/), {
      target: { value: manualDiscount.id },
    });

    const preview = screen.getByLabelText("Попередній розрахунок");
    expect(preview).toHaveTextContent(/1\s?200,00/);
    expect(preview).toHaveTextContent(/120,00/);
    expect(preview).toHaveTextContent(/1\s?080,00/);

    const axeResult = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(axeResult.violations).toEqual([]);

    fireEvent.click(screen.getByLabelText(/Підтверджую підсумок прийому/));
    fireEvent.click(screen.getByRole("button", { name: "Завершити й передати на оплату" }));
    expect(await screen.findByRole("heading", { name: "Передано ресепшну на оплату" }))
      .toBeInTheDocument();
    expect(screen.getByText(/Постійний клієнт · 10%/)).toHaveTextContent(/120,00/);

    const finishRequest = vi.mocked(fetch).mock.calls
      .map(([input, init]) => requestFrom(input, init))
      .find((request) => request.url.endsWith("/finish") && request.method === "POST");
    if (finishRequest === undefined) throw new Error("Expected visit finish request");
    expect(await finishRequest.clone().json()).toEqual({
      version: visitFixture.version,
      recommendations: "",
      payment_handoff_requested: true,
      discount_id: manualDiscount.id,
      follow_up: null,
    });
  });

  it("clears an unavailable discount and requires confirmation after refreshing the picker", async () => {
    let discountLoads = 0;
    vi.mocked(fetch).mockImplementation((input, init) => {
      const request = requestFrom(input, init);
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (url.pathname === `/api/v1/visits/${visitFixture.id}` && request.method === "GET") {
        return Promise.resolve(jsonResponse(visitFixture));
      }
      if (url.pathname === "/api/v1/services" && request.method === "GET") {
        return Promise.resolve(jsonResponse({ services: [clinicService] }));
      }
      if (url.pathname === "/api/v1/discounts" && request.method === "GET") {
        discountLoads += 1;
        return Promise.resolve(jsonResponse({ discounts: discountLoads === 1 ? [manualDiscount] : [] }));
      }
      if (url.pathname.endsWith("/finish") && request.method === "POST") {
        return Promise.resolve(jsonResponse({
          code: "discount_unavailable",
          message: "Обрана знижка неактивна або не існує.",
          fields: { discount_id: ["Оберіть активну знижку."] },
          correlation_id: "discount-race",
        }, 409));
      }
      return Promise.resolve(jsonResponse({}, 404));
    });

    renderVisit();
    await openFinishStep();
    await screen.findByRole("option", { name: "Постійний клієнт · 10%" });
    fireEvent.change(screen.getByLabelText(/Ручна знижка/), {
      target: { value: manualDiscount.id },
    });
    fireEvent.click(screen.getByLabelText(/Підтверджую підсумок прийому/));
    fireEvent.click(screen.getByRole("button", { name: "Завершити й передати на оплату" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Каталог оновлено");
    await waitFor(() => { expect(discountLoads).toBe(2); });
    expect(screen.getByLabelText(/Ручна знижка/)).toHaveValue("");
    expect(screen.getByLabelText(/Підтверджую підсумок прийому/)).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Завершити й передати на оплату" })).toBeDisabled();
  });

  it("shows the loyalty discount up front and lets the podologist decide whether to replace it", async () => {
    const eligibleVisit = { ...visitFixture, loyalty: loyaltyEligibleVisitLoyalty } as const;
    vi.mocked(fetch).mockImplementation((input, init) => {
      const request = requestFrom(input, init);
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (url.pathname === `/api/v1/visits/${visitFixture.id}` && request.method === "GET") {
        return Promise.resolve(jsonResponse(eligibleVisit));
      }
      if (url.pathname === "/api/v1/services" && request.method === "GET") {
        return Promise.resolve(jsonResponse({ services: [clinicService] }));
      }
      if (url.pathname === "/api/v1/discounts" && request.method === "GET") {
        return Promise.resolve(jsonResponse({ discounts: [manualDiscount, smallerDiscount] }));
      }
      return Promise.resolve(jsonResponse({}, 404));
    });

    renderVisit();
    await openFinishStep();

    // The loyalty discount is visible and already priced in, with no action taken.
    const notice = await screen.findByTestId("visit-loyalty-notice");
    expect(notice).toHaveTextContent("5-й візит");
    expect(notice).toHaveTextContent("Постійний клієнт");
    expect(notice).toHaveTextContent("10%");
    const preview = screen.getByLabelText("Попередній розрахунок");
    expect(preview).toHaveTextContent(/120,00/);
    expect(preview).toHaveTextContent(/1\s?080,00/);
    expect(preview).toHaveTextContent("Постійний клієнт (автоматична)");
    const select = screen.getByLabelText(/Замінити знижку/);
    expect(select).toHaveValue("");
    expect(await screen.findByRole("option", {
      name: "Залишити знижку постійного клієнта · 10%",
    })).toBeInTheDocument();
    expect(screen.queryByTestId("visit-loyalty-override")).not.toBeInTheDocument();

    // Replacing it with a smaller discount warns instead of silently downgrading.
    fireEvent.change(select, { target: { value: smallerDiscount.id } });
    const override = screen.getByTestId("visit-loyalty-override");
    expect(override).toHaveTextContent("замінюєте знижку постійного клієнта 10% на меншу 5%");
    expect(preview).toHaveTextContent(/60,00/);
    expect(preview).toHaveTextContent(/1\s?140,00/);

    // And the decision is reversible.
    fireEvent.click(screen.getByRole("button", { name: "Повернути знижку постійного клієнта" }));
    expect(screen.queryByTestId("visit-loyalty-override")).not.toBeInTheDocument();
    expect(screen.getByLabelText(/Замінити знижку/)).toHaveValue("");
    expect(preview).toHaveTextContent(/1\s?080,00/);
  });
});
