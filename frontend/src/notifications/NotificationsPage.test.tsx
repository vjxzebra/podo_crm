import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { App } from "../App";
import {
  adminSession,
  jsonResponse,
  notificationFixture,
  notificationListFixture,
  overviewFixture,
  podologistSession,
  workItemFixture,
  workItemListFixture,
} from "../test/setup";

const apiFailure = {
  code: "temporary_failure",
  message: "Сервіс тимчасово недоступний.",
  fields: {},
  correlation_id: "notification-test",
} as const;

function renderNotifications() {
  return render(
    <MemoryRouter initialEntries={["/notifications"]}>
      <App />
    </MemoryRouter>,
  );
}

function requestDetails(input: RequestInfo | URL, init?: RequestInit) {
  const request = input instanceof Request ? input : new Request(input, init);
  return { method: request.method, url: new URL(request.url) };
}

describe("notifications center", () => {
  it("renders recipient notifications, syncs the badge, filters, and marks all read", async () => {
    let markedAll = false;
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const { method, url } = requestDetails(input, init);
      if (url.pathname === "/api/v1/session") {
        return Promise.resolve(jsonResponse({ ...adminSession, notification_unread_count: 1 }));
      }
      if (url.pathname === "/api/v1/notifications/read-all" && method === "POST") {
        markedAll = true;
        return Promise.resolve(jsonResponse({ marked_count: 1, unread_count: 0 }));
      }
      if (url.pathname === "/api/v1/notifications" && method === "GET") {
        const notifications = markedAll
          ? [{ ...notificationFixture, is_read: true, read_at: "2026-07-22T09:00:00Z" }]
          : [notificationFixture];
        return Promise.resolve(jsonResponse({
          notifications: url.searchParams.get("status") === "unread" && markedAll
            ? []
            : notifications,
          total_count: 1,
          unread_count: markedAll ? 0 : 1,
          next_cursor: null,
        }));
      }
      if (url.pathname === "/api/v1/overview" && method === "GET") {
        return Promise.resolve(jsonResponse(overviewFixture));
      }
      return Promise.resolve(jsonResponse({}));
    });

    renderNotifications();

    expect(await screen.findByText("Пацієнт уже прибув")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Сповіщення: 1 непрочитаних" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Позначити всі прочитаними" }));

    expect(await screen.findByRole("link", { name: "Сповіщення: немає непрочитаних" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Прочитане сповіщення: Пацієнт уже прибув/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Непрочитані" }));
    expect(await screen.findByRole("heading", { name: "Усе прочитано" })).toBeInTheDocument();
  });

  it("marks an item before navigating to its canonical highlighted work item", async () => {
    const deepLink = `/work-items?item=${workItemFixture.id}`;
    const source = { ...notificationFixture, deep_link: deepLink };
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const { method, url } = requestDetails(input, init);
      if (url.pathname === "/api/v1/session") {
        return Promise.resolve(jsonResponse({ ...adminSession, notification_unread_count: 1 }));
      }
      if (url.pathname === "/api/v1/notifications" && method === "GET") {
        return Promise.resolve(jsonResponse({ ...notificationListFixture, notifications: [source] }));
      }
      if (url.pathname.endsWith("/read") && method === "POST") {
        return Promise.resolve(jsonResponse({
          ...source,
          is_read: true,
          read_at: "2026-07-22T09:00:00Z",
        }));
      }
      if (url.pathname === "/api/v1/work-items" && method === "GET") {
        return Promise.resolve(jsonResponse(workItemListFixture));
      }
      return Promise.resolve(jsonResponse({}));
    });

    renderNotifications();
    fireEvent.click(await screen.findByRole("button", {
      name: /Непрочитане сповіщення: Пацієнт уже прибув/,
    }));

    expect(await screen.findByRole("heading", { name: "Внутрішні справи" })).toBeInTheDocument();
    await screen.findByText(workItemFixture.title);
    await waitFor(() => {
      expect(document.getElementById(`work-item-${workItemFixture.id}`)).toHaveFocus();
    });
    expect(screen.getByRole("link", { name: "Сповіщення: немає непрочитаних" })).toBeInTheDocument();
    const requests = vi.mocked(fetch).mock.calls.map(([input, init]) => requestDetails(input, init));
    const readIndex = requests.findIndex(({ method, url }) => method === "POST" && url.pathname.endsWith("/read"));
    const workItemIndex = requests.findIndex(({ method, url }) => method === "GET" && url.pathname === "/api/v1/work-items");
    expect(readIndex).toBeGreaterThan(-1);
    expect(workItemIndex).toBeGreaterThan(readIndex);
  });

  it("falls back to the overview when a returned deep link is unsafe for the role", async () => {
    const inaccessible = {
      ...notificationFixture,
      deep_link: "/finance?operation=PAYMENT:private",
    };
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const { method, url } = requestDetails(input, init);
      if (url.pathname === "/api/v1/session") {
        return Promise.resolve(jsonResponse({ ...podologistSession, notification_unread_count: 1 }));
      }
      if (url.pathname === "/api/v1/notifications" && method === "GET") {
        return Promise.resolve(jsonResponse({
          ...notificationListFixture,
          notifications: [inaccessible],
        }));
      }
      if (url.pathname.endsWith("/read") && method === "POST") {
        return Promise.resolve(jsonResponse({
          ...inaccessible,
          is_read: true,
          read_at: "2026-07-22T09:00:00Z",
        }));
      }
      if (url.pathname === "/api/v1/overview" && method === "GET") {
        return Promise.resolve(jsonResponse(overviewFixture));
      }
      return Promise.resolve(jsonResponse({}));
    });

    renderNotifications();
    fireEvent.click(await screen.findByRole("button", {
      name: /Непрочитане сповіщення: Пацієнт уже прибув/,
    }));

    expect(await screen.findByRole("heading", { name: "Добрий день" })).toBeInTheDocument();
  });

  it("recovers from a list failure and appends an older cursor page", async () => {
    const older = {
      ...notificationFixture,
      id: "205675c3-0e45-4a2d-98a9-38af789f6d06",
      title: "Справу прострочено",
      kind: "work_item_overdue" as const,
      tone: "coral" as const,
      occurred_at: "2026-07-21T08:55:00Z",
    };
    let listRequests = 0;
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const { method, url } = requestDetails(input, init);
      if (url.pathname === "/api/v1/session") {
        return Promise.resolve(jsonResponse(adminSession));
      }
      if (url.pathname === "/api/v1/notifications" && method === "GET") {
        listRequests += 1;
        if (listRequests === 1) return Promise.resolve(jsonResponse(apiFailure, 503));
        if (url.searchParams.get("cursor") === "older-page") {
          return Promise.resolve(jsonResponse({
            notifications: [older],
            total_count: 2,
            unread_count: 2,
            next_cursor: null,
          }));
        }
        return Promise.resolve(jsonResponse({
          ...notificationListFixture,
          total_count: 2,
          unread_count: 2,
          next_cursor: "older-page",
        }));
      }
      return Promise.resolve(jsonResponse({}));
    });

    renderNotifications();
    expect(await screen.findByRole("alert")).toHaveTextContent("Сервіс тимчасово недоступний");
    fireEvent.click(screen.getByRole("button", { name: "Повторити" }));
    expect(await screen.findByText("Пацієнт уже прибув")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Показати старіші" }));

    const olderItem = await screen.findByText("Справу прострочено");
    const newerItem = screen.getByText("Пацієнт уже прибув");
    const newerRegion = newerItem.closest("section.notification-group");
    const olderRegion = olderItem.closest("section.notification-group");
    expect(newerRegion).not.toBeNull();
    expect(olderRegion).not.toBeNull();
    expect(
      (newerRegion?.compareDocumentPosition(olderRegion as Node) ?? 0)
      & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Показати старіші" })).not.toBeInTheDocument();
    });
  });

  it("keeps the item in place after a read failure and supports retry", async () => {
    let readRequests = 0;
    const source = { ...notificationFixture, deep_link: "/" };
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const { method, url } = requestDetails(input, init);
      if (url.pathname === "/api/v1/session") {
        return Promise.resolve(jsonResponse({ ...adminSession, notification_unread_count: 1 }));
      }
      if (url.pathname === "/api/v1/notifications" && method === "GET") {
        return Promise.resolve(jsonResponse({
          ...notificationListFixture,
          notifications: [source],
        }));
      }
      if (url.pathname === "/api/v1/overview" && method === "GET") {
        return Promise.resolve(jsonResponse(overviewFixture));
      }
      if (url.pathname.endsWith("/read") && method === "POST") {
        readRequests += 1;
        return readRequests === 1
          ? Promise.resolve(jsonResponse(apiFailure, 503))
          : Promise.resolve(jsonResponse({
              ...source,
              is_read: true,
              read_at: "2026-07-22T09:00:00Z",
            }));
      }
      return Promise.resolve(jsonResponse({}));
    });

    renderNotifications();
    fireEvent.click(await screen.findByRole("button", {
      name: /Непрочитане сповіщення: Пацієнт уже прибув/,
    }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Сервіс тимчасово недоступний");
    expect(screen.getByRole("heading", { name: "Сповіщення" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Повторити" }));
    await waitFor(() => { expect(readRequests).toBe(2); });
    expect(await screen.findByRole("heading", { name: "Добрий день" })).toBeInTheDocument();
  });
});
