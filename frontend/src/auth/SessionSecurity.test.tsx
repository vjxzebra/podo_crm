import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { adminSession, jsonResponse } from "../test/setup";

const sessionExpiredProblem = {
  code: "session_expired",
  message: "Сесію завершено. Увійдіть знову, щоб продовжити роботу.",
  fields: {},
  correlation_id: "tp-902-session-expired",
};

function renderApp(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("TP-902 session expiry boundary", () => {
  it("shows a neutral notice when the bootstrap session has expired", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse(sessionExpiredProblem, 401));

    renderApp("/inventory");

    expect(await screen.findByRole("heading", { name: "Вхід до кабінету" })).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Сесію завершено. Увійдіть знову, щоб продовжити роботу.",
    );
    expect(screen.queryByTestId("desktop-sidebar")).not.toBeInTheDocument();
  });

  it("unmounts protected UI when an in-flight protected request returns 401", async () => {
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (path === "/api/v1/notifications") {
        return Promise.resolve(jsonResponse(sessionExpiredProblem, 401));
      }
      return Promise.resolve(jsonResponse(sessionExpiredProblem, 401));
    });

    renderApp("/notifications");

    expect(await screen.findByRole("heading", { name: "Вхід до кабінету" })).toBeVisible();
    await waitFor(() => {
      expect(screen.queryByTestId("desktop-sidebar")).not.toBeInTheDocument();
      expect(screen.queryByRole("navigation", { name: "Основна навігація" })).not.toBeInTheDocument();
      expect(screen.queryByRole("heading", { name: "Сповіщення" })).not.toBeInTheDocument();
    });
    expect(screen.getByRole("status")).toHaveTextContent("Сесію завершено");
  });

  it("treats the admin reset-queue GET as protected although public reset POST shares its path", async () => {
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(input, init);
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/session") return Promise.resolve(jsonResponse(adminSession));
      if (path === "/api/v1/password-reset-requests" && request.method === "GET") {
        return Promise.resolve(jsonResponse(sessionExpiredProblem, 401));
      }
      return Promise.resolve(jsonResponse(sessionExpiredProblem, 401));
    });

    renderApp("/password-resets");

    expect(await screen.findByRole("heading", { name: "Вхід до кабінету" })).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("Сесію завершено");
    expect(screen.queryByRole("heading", { name: "Запити на відновлення" })).not.toBeInTheDocument();
  });
});
