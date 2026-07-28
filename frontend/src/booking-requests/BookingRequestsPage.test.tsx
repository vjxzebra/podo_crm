import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { App } from "../App";
import {
  adminSession,
  bookingRequestFixture,
  bookingRequestListFixture,
  jsonResponse,
  podologistSession,
} from "../test/setup";

function renderPage(path = "/booking-requests") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("BookingRequestsPage", () => {
  it("shows server counts and the default new-request list", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { name: "Заявки на запис" })).toBeInTheDocument();
    expect((await screen.findAllByText(bookingRequestFixture.client_name)).length).toBeGreaterThan(0);
    const summary = screen.getByRole("region", { name: "Підсумок заявок" });
    expect(within(summary).getByText("1")).toBeInTheDocument();
    expect(within(summary).getByText("2")).toBeInTheDocument();
    expect(within(summary).getByText("3")).toBeInTheDocument();
    expect(screen.getAllByText(bookingRequestFixture.public_number).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Instagram").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Нова").length).toBeGreaterThan(0);

    const listRequest = vi.mocked(fetch).mock.calls.find(([input]) =>
      new URL(input instanceof Request ? input.url : input.toString()).pathname
      === "/api/v1/booking-requests");
    expect(listRequest).toBeDefined();
    const listUrl = new URL(
      listRequest?.[0] instanceof Request
        ? listRequest[0].url
        : listRequest?.[0].toString() ?? window.location.origin,
    );
    expect(listUrl.searchParams.get("status")).toBe("NEW");
    expect(listUrl.searchParams.get("source")).toBe("ALL");
  });

  it("applies status, source, and debounced search filters", async () => {
    const requestedUrls: URL[] = [];
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (url.pathname === "/api/v1/booking-requests") {
        requestedUrls.push(url);
        return Promise.resolve(jsonResponse(bookingRequestListFixture));
      }
      return Promise.resolve(jsonResponse({ code: "not_found", message: "Not found", fields: {}, correlation_id: "filters" }, 404));
    });
    renderPage();
    await screen.findAllByText(bookingRequestFixture.client_name);

    fireEvent.change(screen.getByRole("combobox", { name: "Статус заявок" }), {
      target: { value: "ALL" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Джерело заявок" }), {
      target: { value: "WEBSITE" },
    });
    fireEvent.change(screen.getByRole("searchbox", { name: "Пошук заявок" }), {
      target: { value: "Ірина" },
    });

    await waitFor(() => {
      const lastUrl = requestedUrls.at(-1);
      expect(lastUrl?.searchParams.get("status")).toBe("ALL");
      expect(lastUrl?.searchParams.get("source")).toBe("WEBSITE");
      expect(lastUrl?.searchParams.get("search")).toBe("Ірина");
    });
  });

  it("opens reload-stable details and marks a request processed", async () => {
    const processed = {
      ...bookingRequestFixture,
      status: "PROCESSED",
      status_label: "Оброблена",
      processed_by_display_name: adminSession.user.display_name,
      processed_at: "2026-07-28T10:05:00+03:00",
      version: 2,
      updated_at: "2026-07-28T10:05:00+03:00",
    } as const;
    let processBody: unknown;
    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/session") return jsonResponse(adminSession);
      if (url.pathname === "/api/v1/booking-requests") return jsonResponse(bookingRequestListFixture);
      if (url.pathname === `/api/v1/booking-requests/${bookingRequestFixture.id}`) {
        return jsonResponse(bookingRequestFixture);
      }
      if (
        url.pathname === `/api/v1/booking-requests/${bookingRequestFixture.id}/process`
        && request.method === "POST"
      ) {
        processBody = await request.clone().json();
        return jsonResponse(processed);
      }
      return jsonResponse({ code: "not_found", message: "Not found", fields: {}, correlation_id: "process" }, 404);
    });
    renderPage();
    const openButtons = await screen.findAllByRole("button", {
      name: `Відкрити заявку ${bookingRequestFixture.public_number} — ${bookingRequestFixture.client_name}`,
    });
    const openButton = openButtons[0];
    expect(openButton).toBeDefined();
    if (openButton === undefined) throw new Error("Booking request action is missing.");
    fireEvent.click(openButton);

    const dialog = await screen.findByRole("dialog", { name: bookingRequestFixture.public_number });
    expect(within(dialog).getByText(bookingRequestFixture.message)).toBeInTheDocument();
    expect(within(dialog).getByText(bookingRequestFixture.service)).toBeInTheDocument();
    expect(within(dialog).getByRole("link", { name: bookingRequestFixture.phone })).toHaveAttribute(
      "href",
      `tel:${bookingRequestFixture.phone}`,
    );
    fireEvent.click(within(dialog).getByRole("button", { name: "Заявка оброблена" }));

    expect(await within(dialog).findByText("Заявку позначено обробленою.")).toBeInTheDocument();
    expect(within(dialog).getByText("Заявку оброблено")).toBeInTheDocument();
    expect(within(dialog).getByText(new RegExp(adminSession.user.display_name))).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "Заявка оброблена" })).not.toBeInTheDocument();
    expect(processBody).toEqual({ version: 1 });
  });

  it("shows all optional form fields safely when they are blank", async () => {
    const emptyRequest = {
      ...bookingRequestFixture,
      id: "c1410bea-e7ff-4cab-b8d2-13c547f3f9c9",
      public_number: "REQ-0000000000",
      client_name: "",
      phone: "",
      service: "",
      contact_handle: "",
      message: "",
      preferred_at: null,
    } as const;
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (url.pathname === "/api/v1/booking-requests") {
        return Promise.resolve(jsonResponse({
          booking_requests: [emptyRequest],
          counts: { new: 1, processed: 0, total: 1 },
          next_cursor: null,
        }));
      }
      if (url.pathname === `/api/v1/booking-requests/${emptyRequest.id}`) {
        return Promise.resolve(jsonResponse(emptyRequest));
      }
      return Promise.resolve(jsonResponse({
        code: "not_found",
        message: "Not found",
        fields: {},
        correlation_id: "optional-fields",
      }, 404));
    });

    renderPage(`/booking-requests?request=${emptyRequest.id}`);

    const dialog = await screen.findByRole("dialog", { name: emptyRequest.public_number });
    expect(within(dialog).getAllByText("Не вказано")).toHaveLength(2);
    expect(within(dialog).getByText("Коментар не вказано.")).toBeInTheDocument();
    expect(within(dialog).queryByRole("link", { name: "Не вказано" })).not.toBeInTheDocument();
    expect((await screen.findAllByText("Ім’я не вказано")).length).toBeGreaterThan(0);
  });

  it("restores a detail directly from the query string and closes with Escape", async () => {
    renderPage(`/booking-requests?request=${bookingRequestFixture.id}`);

    const dialog = await screen.findByRole("dialog", { name: bookingRequestFixture.public_number });
    expect(within(dialog).getByText(bookingRequestFixture.client_name)).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: bookingRequestFixture.public_number })).not.toBeInTheDocument();
    });
  });

  it("keeps the domain unchanged on a version conflict and refreshes detail", async () => {
    let detailCalls = 0;
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (url.pathname === "/api/v1/booking-requests") return Promise.resolve(jsonResponse(bookingRequestListFixture));
      if (url.pathname === `/api/v1/booking-requests/${bookingRequestFixture.id}`) {
        detailCalls += 1;
        return Promise.resolve(jsonResponse(bookingRequestFixture));
      }
      if (url.pathname.endsWith("/process")) {
        return Promise.resolve(jsonResponse({
          code: "version_conflict",
          message: "Conflict",
          fields: { version: ["Застаріла версія."] },
          correlation_id: "conflict",
        }, 409));
      }
      return Promise.resolve(jsonResponse({ code: "not_found", message: "Not found", fields: {}, correlation_id: "conflict" }, 404));
    });
    renderPage(`/booking-requests?request=${bookingRequestFixture.id}`);
    const dialog = await screen.findByRole("dialog", { name: bookingRequestFixture.public_number });

    fireEvent.click(within(dialog).getByRole("button", { name: "Заявка оброблена" }));

    expect(await within(dialog).findByText("Заявку вже змінив інший працівник. Дані оновлено.")).toBeInTheDocument();
    await waitFor(() => { expect(detailCalls).toBe(2); });
    expect(within(dialog).getByRole("button", { name: "Заявка оброблена" })).toBeEnabled();
  });

  it("supports empty, error, retry, and cursor load-more states", async () => {
    let listCalls = 0;
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      const url = new URL(request.url);
      if (url.pathname === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (url.pathname === "/api/v1/booking-requests") {
        listCalls += 1;
        if (listCalls === 1) {
          return Promise.resolve(jsonResponse({
            code: "temporary_error",
            message: "Сервіс тимчасово недоступний.",
            fields: {},
            correlation_id: "retry",
          }, 503));
        }
        if (url.searchParams.get("cursor") === "page-two") {
          return Promise.resolve(jsonResponse({
            booking_requests: [{ ...bookingRequestFixture, id: "86079fa8-fc6b-4197-97d5-cae597ab3c5b", public_number: "REQ-1111222233" }],
            counts: { new: 2, processed: 0, total: 2 },
            next_cursor: null,
          }));
        }
        return Promise.resolve(jsonResponse({
          booking_requests: [bookingRequestFixture],
          counts: { new: 2, processed: 0, total: 2 },
          next_cursor: "page-two",
        }));
      }
      return Promise.resolve(jsonResponse({ code: "not_found", message: "Not found", fields: {}, correlation_id: "retry" }, 404));
    });
    renderPage();

    expect(await screen.findByText("Сервіс тимчасово недоступний.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Повторити" }));
    await screen.findAllByText(bookingRequestFixture.client_name);
    fireEvent.click(screen.getByRole("button", { name: "Показати ще" }));
    expect((await screen.findAllByText("REQ-1111222233")).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Показати ще" })).not.toBeInTheDocument();
  });

  it("does not expose the route to podologists", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(podologistSession));
    renderPage();

    expect(await screen.findByRole("heading", { name: "Добрий день" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Заявки" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Заявки на запис" })).not.toBeInTheDocument();
  });
});
