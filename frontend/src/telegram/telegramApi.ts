import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { csrfHeaders } from "../auth/AuthContext";

export type TelegramSubscription = components["schemas"]["TelegramSubscription"];
export type TelegramLinkIntent = components["schemas"]["TelegramLinkIntent"];
type TelegramApiError = components["schemas"]["ErrorEnvelope"];

export type TelegramApiResult<T> =
  | { readonly ok: true; readonly data: T }
  | { readonly ok: false; readonly error: TelegramApiError; readonly status: number };

export async function getTelegramSubscription(
  signal?: AbortSignal,
): Promise<TelegramApiResult<TelegramSubscription>> {
  const { data, error, response } = await apiClient.GET("/api/v1/telegram/subscription", {
    ...(signal === undefined ? {} : { signal }),
  });
  return data === undefined
    ? { ok: false, error, status: response.status }
    : { ok: true, data };
}

export async function createTelegramLinkIntent(): Promise<TelegramApiResult<TelegramLinkIntent>> {
  const { data, error, response } = await apiClient.POST("/api/v1/telegram/link-intents", {
    headers: csrfHeaders(),
  });
  return data === undefined
    ? { ok: false, error, status: response.status }
    : { ok: true, data };
}

export async function disconnectTelegramSubscription(): Promise<TelegramApiResult<null>> {
  const { error, response } = await apiClient.DELETE("/api/v1/telegram/subscription", {
    headers: csrfHeaders(),
  });
  return response.ok
    ? { ok: true, data: null }
    : {
        ok: false,
        error: error ?? {
          code: "api_error",
          correlation_id: "",
          fields: {},
          message: "Не вдалося відключити Telegram.",
        },
        status: response.status,
      };
}
