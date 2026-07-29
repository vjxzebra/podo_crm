import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { jsonResponse } from "../test/setup";
import { TelegramDialog } from "./TelegramDialog";

function renderDialog() {
  return render(<TelegramDialog onClose={vi.fn()} />);
}

function requestParts(input: RequestInfo | URL, init?: RequestInit): { url: string; method: string } {
  if (input instanceof Request) {
    return { url: input.url, method: init?.method ?? input.method };
  }
  return { url: input.toString(), method: init?.method ?? "GET" };
}

describe("TelegramDialog", () => {
  it("creates and copies a one-time private link", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const { url, method } = requestParts(input, init);
      if (url.endsWith("/api/v1/telegram/subscription") && method === "GET") {
        return Promise.resolve(jsonResponse({
          is_linked: false,
          is_enabled: false,
          username: "",
          first_name: "",
          linked_at: null,
          disabled_at: null,
          last_seen_at: null,
        }));
      }
      if (url.endsWith("/api/v1/telegram/link-intents") && method === "POST") {
        return Promise.resolve(jsonResponse({
          url: "https://t.me/podo_crm_pod_bot?start=one-time-secret",
          expires_at: "2026-07-28T10:10:00Z",
        }, 201));
      }
      return Promise.resolve(jsonResponse({ code: "not_found", message: "Missing", fields: {}, correlation_id: "test" }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderDialog();
    expect(await screen.findByText("Не підключено")).toBeInTheDocument();
    expect(screen.getByText(/Ваші справи та доступні вам нові заявки/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Підключити" }));
    expect(await screen.findByDisplayValue(/one-time-secret/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Скопіювати" }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith("https://t.me/podo_crm_pod_bot?start=one-time-secret");
    });
    expect(screen.getByRole("link", { name: /Відкрити Telegram/ })).toHaveAttribute(
      "href",
      "https://t.me/podo_crm_pod_bot?start=one-time-secret",
    );
  });

  it("disconnects an enabled subscription", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const { url, method } = requestParts(input, init);
      if (url.endsWith("/api/v1/telegram/subscription") && method === "GET") {
        return Promise.resolve(jsonResponse({
          is_linked: true,
          is_enabled: true,
          username: "frontdesk",
          first_name: "Front",
          linked_at: "2026-07-28T10:00:00Z",
          disabled_at: null,
          last_seen_at: "2026-07-28T10:00:00Z",
        }));
      }
      if (url.endsWith("/api/v1/telegram/subscription") && method === "DELETE") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      return Promise.resolve(jsonResponse({ code: "not_found", message: "Missing", fields: {}, correlation_id: "test" }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderDialog();
    expect(await screen.findByText("Підключено")).toBeInTheDocument();
    expect(screen.getByText(/@frontdesk/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Відключити" }));

    await waitFor(() => {
      expect(screen.getByText("Telegram відключено для вашого профілю.")).toBeInTheDocument();
    });
    expect(fetchMock.mock.calls.some(([input, init]) => {
      const { url, method } = requestParts(input, init);
      return url.endsWith("/api/v1/telegram/subscription") && method === "DELETE";
    })).toBe(true);
  });
});
