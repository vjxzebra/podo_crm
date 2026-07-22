import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { App } from "../App";
import {
  adminSession,
  analyticsFixture,
  jsonResponse,
  overviewFixture,
  podologistSession,
  workItemListFixture,
} from "../test/setup";

function renderApp(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("TP-804 role overview", () => {
  it("renders live metrics, schedule and canonical appointment links", async () => {
    renderApp();

    expect(await screen.findByRole("heading", { name: "Добрий день" })).toBeInTheDocument();
    expect(await screen.findByText("Очікуваний дохід")).toBeInTheDocument();
    expect(screen.getByText("1 450 ₴")).toBeInTheDocument();
    const appointmentLink = screen.getByRole("link", { name: /Марія Бондар/ });
    expect(appointmentLink).toHaveAttribute("href", `/calendar?appointment=${overviewFixture.schedule[0].id}`);
    expect(
      vi.mocked(fetch).mock.calls.some(([input]) => {
        if (!(input instanceof Request)) return false;
        const url = new URL(input.url);
        return url.pathname === "/api/v1/overview" && url.searchParams.has("date");
      }),
    ).toBe(true);
  });

  it("keeps clinic finance absent from a podologist projection", async () => {
    const podologistOverview = {
      ...overviewFixture,
      role: "podologist",
      metrics: [
        { key: "appointments", label: "Власні записи", value: 1, format: "integer", note: "на вибрану дату", tone: "sage" },
        { key: "patients", label: "Власні пацієнти", value: 1, format: "integer", note: "distinct у розкладі", tone: "sand" },
        { key: "workday_minutes", label: "Робочий день", value: 510, format: "duration", note: "за графіком клініки", tone: "lilac" },
        { key: "attention", label: "Потребує уваги", value: 0, format: "integer", note: "власні справи", tone: "coral" },
      ],
      attention: [
        { kind: "work_items", label: "Власні прострочені або важливі справи", count: 0, deep_link: "/work-items" },
      ],
    } as const;
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/session") return Promise.resolve(jsonResponse(podologistSession));
      if (path === "/api/v1/overview") return Promise.resolve(jsonResponse(podologistOverview));
      if (path === "/api/v1/work-items") return Promise.resolve(jsonResponse(workItemListFixture));
      return Promise.resolve(jsonResponse({ code: "not_found", message: "Not found", fields: {}, correlation_id: "tp804" }, 404));
    });

    renderApp();

    expect(await screen.findByText("Власні записи")).toBeInTheDocument();
    expect(screen.getByText("Власні пацієнти")).toBeInTheDocument();
    expect(screen.queryByText("Очікуваний дохід")).not.toBeInTheDocument();
    expect(screen.queryByText("Оплати за день")).not.toBeInTheDocument();
  });
});

describe("TP-804 administrator analytics", () => {
  it("renders reconciled KPIs and refetches every panel through the service filter", async () => {
    renderApp("/analytics");

    expect(await screen.findByRole("heading", { name: "Аналітика клініки" })).toBeInTheDocument();
    expect(await screen.findAllByText("28 450 ₴")).not.toHaveLength(0);
    expect(screen.getByRole("heading", { name: "Завантаженість спеціалістів" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Рейтинг за виконаним обсягом" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Послуга"), {
      target: { value: analyticsFixture.available_services[0].id },
    });

    await waitFor(() => {
      expect(
        vi.mocked(fetch).mock.calls.some(([input]) => {
          if (!(input instanceof Request)) return false;
          const url = new URL(input.url);
          return url.pathname === "/api/v1/analytics"
            && url.searchParams.get("service_id") === analyticsFixture.available_services[0].id;
        }),
      ).toBe(true);
    });
  });

  it("shows a retryable server error without presenting invented analytics", async () => {
    let attempts = 0;
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (path === "/api/v1/analytics") {
        attempts += 1;
        if (attempts === 1) {
          return Promise.resolve(jsonResponse({ code: "internal_error", message: "Тимчасова помилка", fields: {}, correlation_id: "tp804" }, 500));
        }
        return Promise.resolve(jsonResponse(analyticsFixture));
      }
      return Promise.resolve(jsonResponse({ code: "not_found", message: "Not found", fields: {}, correlation_id: "tp804" }, 404));
    });

    renderApp("/analytics");

    expect(await screen.findByRole("alert")).toHaveTextContent("Тимчасова помилка");
    fireEvent.click(screen.getByRole("button", { name: "Повторити" }));
    expect(await screen.findAllByText("28 450 ₴")).not.toHaveLength(0);
    expect(attempts).toBe(2);
  });
});
