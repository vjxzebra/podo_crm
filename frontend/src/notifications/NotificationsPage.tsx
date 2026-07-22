import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { Icon, type IconName } from "../app/Icon";
import { useAuth } from "../auth/AuthContext";
import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  publishNotificationUnreadCount,
  type Notification,
  type NotificationStatus,
} from "./notificationApi";

interface NotificationGroup {
  readonly key: string;
  readonly label: string;
  readonly notifications: readonly Notification[];
}

interface ActionFailure {
  readonly message: string;
  readonly notificationId?: string;
  readonly kind: "read" | "read-all";
}

const kindIcons: Readonly<Record<Notification["kind"], IconName>> = {
  appointment_arrived: "patients",
  appointment_upcoming: "calendar",
  appointment_canceled: "calendar",
  work_item_overdue: "tasks",
  visit_payment_ready: "finance",
  password_reset_requested: "lock",
};

const routeIdByRoot: Readonly<Record<string, string>> = {
  calendar: "calendar",
  patients: "patients",
  finance: "finance",
  inventory: "inventory",
  "work-items": "work-items",
  "password-resets": "password-resets",
  notifications: "notifications",
  audit: "audit",
};

function kyivDateKey(value: string | Date): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    day: "2-digit",
    month: "2-digit",
    timeZone: "Europe/Kyiv",
    year: "numeric",
  }).formatToParts(typeof value === "string" ? new Date(value) : value);
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((candidate) => candidate.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

function groupLabel(value: string): string {
  const today = new Date();
  const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000);
  const key = kyivDateKey(value);
  if (key === kyivDateKey(today)) return "Сьогодні";
  if (key === kyivDateKey(yesterday)) return "Вчора";
  return new Intl.DateTimeFormat("uk-UA", {
    day: "numeric",
    month: "long",
    timeZone: "Europe/Kyiv",
    year: "numeric",
  }).format(new Date(value));
}

function formatNotificationTime(value: string): string {
  return new Intl.DateTimeFormat("uk-UA", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Kyiv",
  }).format(new Date(value));
}

function safeDeepLink(value: string, routeIds: readonly string[]): string {
  if (
    !value.startsWith("/")
    || value.startsWith("//")
    || value.includes("\\")
    || Array.from(value).some((character) => character.charCodeAt(0) < 32)
  ) {
    return "/";
  }
  const parsed = new URL(value, window.location.origin);
  if (parsed.origin !== window.location.origin || parsed.hash !== "") return "/";
  if (parsed.pathname === "/") return "/";
  const root = parsed.pathname.slice(1).split("/", 1)[0] ?? "";
  const routeId = routeIdByRoot[root];
  if (routeId === undefined || !routeIds.includes(routeId)) return "/";
  return `${parsed.pathname}${parsed.search}`;
}

function notificationGroups(notifications: readonly Notification[]): readonly NotificationGroup[] {
  const groups = new Map<string, NotificationGroup>();
  for (const notification of notifications) {
    const key = kyivDateKey(notification.occurred_at);
    const existing = groups.get(key);
    if (existing === undefined) {
      groups.set(key, {
        key,
        label: groupLabel(notification.occurred_at),
        notifications: [notification],
      });
    } else {
      groups.set(key, {
        ...existing,
        notifications: [...existing.notifications, notification],
      });
    }
  }
  return [...groups.values()].sort((left, right) => right.key.localeCompare(left.key));
}

function failureMessage(message: string): string {
  return message.trim() || "Не вдалося виконати дію. Спробуйте ще раз.";
}

export function NotificationsPage() {
  const navigate = useNavigate();
  const { state } = useAuth();
  const routeIds = state.status === "authenticated" ? state.session.route_ids : [];
  const [filter, setFilter] = useState<NotificationStatus>("all");
  const [notifications, setNotifications] = useState<readonly Notification[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isMarkingAll, setIsMarkingAll] = useState(false);
  const [readingId, setReadingId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionFailure, setActionFailure] = useState<ActionFailure | null>(null);
  const requestSequence = useRef(0);

  const load = useCallback(async (
    requestedFilter: NotificationStatus,
    cursor?: string,
    signal?: AbortSignal,
  ) => {
    const sequence = requestSequence.current + 1;
    requestSequence.current = sequence;
    if (cursor === undefined) {
      setIsLoading(true);
      setLoadError(null);
    } else {
      setIsLoadingMore(true);
    }
    try {
      const result = await listNotifications(requestedFilter, cursor, signal);
      if (sequence !== requestSequence.current || signal?.aborted) return;
      if (!result.ok) {
        setLoadError(failureMessage(result.error.message));
        return;
      }
      setNotifications((current) => cursor === undefined
        ? result.data.notifications
        : [...current, ...result.data.notifications]);
      setTotalCount(result.data.total_count);
      setUnreadCount(result.data.unread_count);
      setNextCursor(result.data.next_cursor);
      setLoadError(null);
      publishNotificationUnreadCount(result.data.unread_count);
    } catch (reason: unknown) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      if (sequence === requestSequence.current) {
        setLoadError("Немає зв’язку із сервером. Перевірте мережу та повторіть.");
      }
    } finally {
      if (sequence === requestSequence.current) {
        setIsLoading(false);
        setIsLoadingMore(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(filter, undefined, controller.signal);
    return () => { controller.abort(); };
  }, [filter, load]);

  const groups = useMemo(() => notificationGroups(notifications), [notifications]);

  const openNotification = useCallback(async (notification: Notification) => {
    if (readingId !== null) return;
    setReadingId(notification.id);
    setActionFailure(null);
    try {
      const result = await markNotificationRead(notification.id);
      if (!result.ok) {
        setActionFailure({
          kind: "read",
          message: failureMessage(result.error.message),
          notificationId: notification.id,
        });
        return;
      }
      setNotifications((current) => current.map((item) =>
        item.id === result.data.id ? result.data : item));
      const nextUnreadCount = notification.is_read ? unreadCount : Math.max(0, unreadCount - 1);
      setUnreadCount(nextUnreadCount);
      publishNotificationUnreadCount(nextUnreadCount);
      void navigate(safeDeepLink(result.data.deep_link, routeIds));
    } catch {
      setActionFailure({
        kind: "read",
        message: "Немає зв’язку із сервером. Сповіщення не відкрито.",
        notificationId: notification.id,
      });
    } finally {
      setReadingId(null);
    }
  }, [navigate, readingId, routeIds, unreadCount]);

  const markAll = useCallback(async () => {
    if (isMarkingAll || unreadCount === 0) return;
    setIsMarkingAll(true);
    setActionFailure(null);
    try {
      const result = await markAllNotificationsRead();
      if (!result.ok) {
        setActionFailure({ kind: "read-all", message: failureMessage(result.error.message) });
        return;
      }
      setUnreadCount(result.data.unread_count);
      publishNotificationUnreadCount(result.data.unread_count);
      await load(filter);
    } catch {
      setActionFailure({
        kind: "read-all",
        message: "Немає зв’язку із сервером. Стан сповіщень не змінено.",
      });
    } finally {
      setIsMarkingAll(false);
    }
  }, [filter, isMarkingAll, load, unreadCount]);

  const retryAction = () => {
    if (actionFailure?.kind === "read-all") {
      void markAll();
      return;
    }
    const notification = notifications.find((item) => item.id === actionFailure?.notificationId);
    if (notification !== undefined) void openNotification(notification);
  };

  return (
    <>
      <header className="page-heading notifications-heading">
        <div>
          <p className="eyebrow">Робочий простір · TP-802</p>
          <h1>Сповіщення</h1>
          <p>Події календаря, оплат, внутрішніх справ і доступу — лише в межах вашої ролі.</p>
        </div>
        <button
          className="button button--secondary"
          disabled={isLoading || isMarkingAll || unreadCount === 0}
          onClick={() => { void markAll(); }}
          type="button"
        >
          <Icon name="check" />
          {isMarkingAll ? "Позначаємо…" : "Позначити всі прочитаними"}
        </button>
      </header>

      <section className="notifications-panel panel" aria-labelledby="notification-list-title">
        <header className="notifications-toolbar">
          <div>
            <h2 id="notification-list-title">Центр сповіщень</h2>
            <p>{String(unreadCount)} непрочитаних · {String(totalCount)} загалом</p>
          </div>
          <div className="segmented-control" aria-label="Фільтр сповіщень">
            <button
              aria-pressed={filter === "all"}
              className={filter === "all" ? "active" : ""}
              onClick={() => { setFilter("all"); setActionFailure(null); }}
              type="button"
            >
              Усі
            </button>
            <button
              aria-pressed={filter === "unread"}
              className={filter === "unread" ? "active" : ""}
              onClick={() => { setFilter("unread"); setActionFailure(null); }}
              type="button"
            >
              Непрочитані {unreadCount > 0 ? <span>{unreadCount > 99 ? "99+" : unreadCount}</span> : null}
            </button>
          </div>
        </header>

        {actionFailure === null ? null : (
          <div className="notifications-action-error" role="alert">
            <Icon name="warning" />
            <span><strong>Дію не виконано</strong><small>{actionFailure.message}</small></span>
            <button className="button button--secondary" onClick={retryAction} type="button">Повторити</button>
          </div>
        )}

        {isLoading && notifications.length === 0 ? (
          <div aria-label="Завантаження сповіщень" className="notification-skeletons" role="status">
            <span /><span /><span />
          </div>
        ) : null}

        {!isLoading && loadError !== null && notifications.length === 0 ? (
          <div className="notifications-state notifications-state--error" role="alert">
            <span className="notifications-state__icon"><Icon name="warning" /></span>
            <h2>Не вдалося завантажити сповіщення</h2>
            <p>{loadError}</p>
            <button className="button button--primary" onClick={() => { void load(filter); }} type="button">
              <Icon name="refresh" />Повторити
            </button>
          </div>
        ) : null}

        {!isLoading && loadError === null && notifications.length === 0 ? (
          <div className="notifications-state">
            <span className="notifications-state__icon"><Icon name={filter === "unread" ? "check" : "bell"} /></span>
            <h2>{filter === "unread" ? "Усе прочитано" : "Сповіщень ще немає"}</h2>
            <p>{filter === "unread" ? "Нові події з’являться тут автоматично після оновлення сторінки." : "Важливі внутрішні події та нагадування з’являться в цьому списку."}</p>
          </div>
        ) : null}

        {groups.length > 0 ? (
          <div className="notification-groups">
            {groups.map((group) => (
              <section aria-labelledby={`notification-group-${group.key}`} className="notification-group" key={group.key}>
                <h3 id={`notification-group-${group.key}`}>{group.label}</h3>
                <div className="notification-list">
                  {group.notifications.map((notification) => (
                    <button
                      aria-label={`${notification.is_read ? "Прочитане" : "Непрочитане"} сповіщення: ${notification.title}`}
                      className={`notification-item notification-item--${notification.tone}${notification.is_read ? " notification-item--read" : ""}`}
                      disabled={readingId !== null}
                      key={notification.id}
                      onClick={() => { void openNotification(notification); }}
                      type="button"
                    >
                      <span className="notification-item__icon"><Icon name={kindIcons[notification.kind]} /></span>
                      <span className="notification-item__copy">
                        <span className="notification-item__title">
                          <strong>{notification.title}</strong>
                          {notification.is_important ? <em><Icon name="flag" />Важливе</em> : null}
                        </span>
                        <small>{notification.message}</small>
                      </span>
                      <time dateTime={notification.occurred_at}>{formatNotificationTime(notification.occurred_at)}</time>
                      {notification.is_read ? null : <span aria-hidden="true" className="notification-item__unread" />}
                      <Icon name={readingId === notification.id ? "refresh" : "chevron"} />
                    </button>
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : null}

        {loadError !== null && notifications.length > 0 ? (
          <div className="notifications-inline-error" role="alert">
            <span>{loadError}</span>
            <button onClick={() => { void load(filter); }} type="button">Оновити список</button>
          </div>
        ) : null}

        {nextCursor === null ? null : (
          <div className="notifications-load-more">
            <button
              className="button button--secondary"
              disabled={isLoadingMore}
              onClick={() => { void load(filter, nextCursor); }}
              type="button"
            >
              {isLoadingMore ? "Завантажуємо…" : "Показати старіші"}
            </button>
          </div>
        )}
      </section>
    </>
  );
}
