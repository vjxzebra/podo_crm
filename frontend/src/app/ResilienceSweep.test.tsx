import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { App } from "../App";
import {
  adminSession,
  jsonResponse,
  overviewFixture,
  workItemListFixture,
} from "../test/setup";

const notFoundProblem = {
  type: "about:blank",
  title: "Not found",
  status: 404,
  detail: "Test route was not configured.",
};

function renderOverview() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );
}

describe("cross-feature resilience sweep", () => {
  it("recovers the protected shell after the initial session request fails", async () => {
    let sessionAttempts = 0;

    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = new URL(input instanceof Request ? input.url : input.toString(), window.location.origin);

        if (url.pathname === "/api/v1/session") {
          sessionAttempts += 1;
          if (sessionAttempts === 1) {
            return Promise.reject(new TypeError("Failed to fetch"));
          }
          return Promise.resolve(jsonResponse(adminSession));
        }
        if (url.pathname === "/api/v1/overview") {
          return Promise.resolve(jsonResponse(overviewFixture));
        }
        if (url.pathname === "/api/v1/work-items") {
          return Promise.resolve(jsonResponse(workItemListFixture));
        }
        return Promise.resolve(jsonResponse(notFoundProblem, 404));
      }),
    );

    renderOverview();

    expect(await screen.findByRole("heading", { name: "Не вдалося завантажити дані" })).toBeVisible();
    expect(screen.queryByRole("navigation", { name: "Основна навігація" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Спробувати ще раз" }));

    expect(await screen.findByRole("heading", { name: "Добрий день" })).toBeVisible();
    expect(screen.getByRole("navigation", { name: "Основна навігація" })).toBeInTheDocument();
    expect(sessionAttempts).toBe(2);
  });

  it("keeps successful overview widgets available when the work-items widget fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = new URL(input instanceof Request ? input.url : input.toString(), window.location.origin);

        if (url.pathname === "/api/v1/session") {
          return Promise.resolve(jsonResponse(adminSession));
        }
        if (url.pathname === "/api/v1/overview") {
          return Promise.resolve(jsonResponse(overviewFixture));
        }
        if (url.pathname === "/api/v1/work-items") {
          return Promise.resolve(jsonResponse(
            {
              type: "about:blank",
              title: "Service unavailable",
              status: 503,
              detail: "Work-items are temporarily unavailable.",
            },
            503,
          ));
        }
        return Promise.resolve(jsonResponse(notFoundProblem, 404));
      }),
    );

    renderOverview();

    expect(await screen.findByRole("heading", { name: "Добрий день" })).toBeVisible();
    expect(await screen.findByText("Не вдалося завантажити справи.")).toBeVisible();
    expect(screen.getByText("Записи кабінету")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Записи на день" })).toBeVisible();
  });
});
