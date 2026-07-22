import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { csrfHeaders } from "../auth/AuthContext";

export type Notification = components["schemas"]["Notification"];
export type NotificationListResponse = components["schemas"]["NotificationListResponse"];
export type NotificationStatus = "all" | "unread";

type NotificationApiError = components["schemas"]["ErrorEnvelope"];
export type NotificationApiResult<T> =
  | { readonly ok: true; readonly data: T }
  | { readonly ok: false; readonly error: NotificationApiError; readonly status: number };

export const NOTIFICATION_COUNT_EVENT = "podoria:notification-count";

export function publishNotificationUnreadCount(unreadCount: number): void {
  window.dispatchEvent(
    new CustomEvent<number>(NOTIFICATION_COUNT_EVENT, {
      detail: Math.max(0, unreadCount),
    }),
  );
}

export async function listNotifications(
  status: NotificationStatus,
  cursor?: string,
  signal?: AbortSignal,
): Promise<NotificationApiResult<NotificationListResponse>> {
  const { data, error, response } = await apiClient.GET("/api/v1/notifications", {
    params: {
      query: {
        status,
        ...(cursor === undefined ? {} : { cursor }),
      },
    },
    ...(signal === undefined ? {} : { signal }),
  });
  return data === undefined
    ? { ok: false, error, status: response.status }
    : { ok: true, data };
}

export async function markNotificationRead(
  notificationId: string,
): Promise<NotificationApiResult<Notification>> {
  const { data, error, response } = await apiClient.POST(
    "/api/v1/notifications/{notification_id}/read",
    {
      params: { path: { notification_id: notificationId } },
      headers: csrfHeaders(),
    },
  );
  return data === undefined
    ? { ok: false, error, status: response.status }
    : { ok: true, data };
}

export async function markAllNotificationsRead(): Promise<
  NotificationApiResult<components["schemas"]["NotificationMarkAllResponse"]>
> {
  const { data, error, response } = await apiClient.POST("/api/v1/notifications/read-all", {
    headers: csrfHeaders(),
  });
  return data === undefined
    ? { ok: false, error, status: response.status }
    : { ok: true, data };
}
