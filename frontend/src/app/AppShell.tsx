import { useCallback, useEffect, useRef, useState } from "react";
import { Link, Outlet, useLocation } from "react-router";

import { DesktopNavigation, MobileNavigation } from "./Navigation";
import { roleLabels, useAuth } from "../auth/AuthContext";
import { GlobalSearchOverlay } from "../search/GlobalSearchOverlay";
import { NOTIFICATION_COUNT_EVENT } from "../notifications/notificationApi";
import { Icon } from "./Icon";
import { findRouteByPath } from "./routes";
import { TelegramDialog } from "../telegram/TelegramDialog";

export function AppShell() {
  const location = useLocation();
  const currentRoute = findRouteByPath(location.pathname);
  const { state } = useAuth();
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isTelegramOpen, setIsTelegramOpen] = useState(false);
  const [notificationUnreadCount, setNotificationUnreadCount] = useState(0);
  const searchTriggerRef = useRef<HTMLElement | null>(null);
  const desktopSearchRef = useRef<HTMLButtonElement>(null);

  const openSearch = useCallback((trigger: HTMLElement | null = null) => {
    searchTriggerRef.current = trigger
      ?? (document.activeElement instanceof HTMLElement ? document.activeElement : desktopSearchRef.current);
    setIsSearchOpen(true);
  }, []);
  const closeSearch = useCallback((restoreFocus: boolean) => {
    setIsSearchOpen(false);
    if (!restoreFocus) return;
    const trigger = searchTriggerRef.current;
    window.setTimeout(() => {
      if (trigger?.isConnected) trigger.focus();
      else desktopSearchRef.current?.focus();
    }, 0);
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((!event.ctrlKey && !event.metaKey) || event.altKey || event.code !== "KeyK" || event.isComposing) return;
      event.preventDefault();
      if (isSearchOpen) {
        document.querySelector<HTMLInputElement>("#global-search-dialog input[type='search']")?.focus();
        return;
      }
      openSearch();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => { document.removeEventListener("keydown", onKeyDown); };
  }, [isSearchOpen, openSearch]);

  useEffect(() => {
    if (state.status === "authenticated") {
      setNotificationUnreadCount(state.session.notification_unread_count);
    }
  }, [state]);

  useEffect(() => {
    const updateUnreadCount = (event: Event) => {
      if (event instanceof CustomEvent && typeof event.detail === "number") {
        setNotificationUnreadCount(Math.max(0, event.detail));
      }
    };
    window.addEventListener(NOTIFICATION_COUNT_EVENT, updateUnreadCount);
    return () => { window.removeEventListener(NOTIFICATION_COUNT_EVENT, updateUnreadCount); };
  }, []);

  if (state.status !== "authenticated") {
    return null;
  }
  const showForbiddenNotice = new URLSearchParams(location.search).get("notice") === "forbidden";
  const canUseTelegram = state.session.route_ids.includes("work-items");

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">До основного вмісту</a>
      <DesktopNavigation />
      <div className="app-main">
        <header className="topbar">
          <Link className="mobile-brand" to="/" aria-label="Podoria CRM — на огляд">
            <span className="brand__mark">P</span>
            <strong>{currentRoute?.shortLabel ?? "Podoria"}</strong>
          </Link>
          <button
            aria-controls="global-search-dialog"
            aria-expanded={isSearchOpen}
            aria-haspopup="dialog"
            aria-keyshortcuts="Control+K Meta+K"
            aria-label="Відкрити глобальний пошук"
            className="global-search"
            onClick={(event) => { openSearch(event.currentTarget); }}
            ref={desktopSearchRef}
            type="button"
          >
            <Icon name="search" />
            <span className="global-search__placeholder">Пацієнт, запис, оплата або матеріал</span>
            <kbd aria-hidden="true">Ctrl K</kbd>
          </button>
          <div className="topbar__actions">
            <span className="session-role" title="Роль із серверної сесії">
              <span className="session-role__dot" />
              {roleLabels[state.session.user.role]}
            </span>
            {canUseTelegram ? (
              <button
                aria-label="Telegram-сповіщення"
                className="icon-button topbar__telegram"
                onClick={() => { setIsTelegramOpen(true); }}
                type="button"
              >
                <Icon name="inbox" />
              </button>
            ) : null}
            <Link
              aria-label={notificationUnreadCount === 0
                ? "Сповіщення: немає непрочитаних"
                : `Сповіщення: ${String(notificationUnreadCount)} непрочитаних`}
              className="icon-button topbar__notifications"
              to="/notifications"
            >
              <Icon name="bell" />
              {notificationUnreadCount > 0 ? (
                <span aria-hidden="true" className="notification-badge">
                  {notificationUnreadCount > 99 ? "99+" : notificationUnreadCount}
                </span>
              ) : null}
            </Link>
            <Link className="button button--primary topbar__create" to="/calendar?compose=appointment">
              <Icon name="plus" />
              Новий запис
            </Link>
          </div>
        </header>
        {showForbiddenNotice ? (
          <div className="access-notice" role="status">
            <Icon name="lock" />
            <span>Цей розділ недоступний для ролі «{roleLabels[state.session.user.role]}». Повернули вас до огляду.</span>
          </div>
        ) : null}
        <main className="content-wrap" id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
      <MobileNavigation onSearchOpen={openSearch} />
      {isSearchOpen ? <GlobalSearchOverlay onClose={() => { closeSearch(true); }} onNavigate={() => { closeSearch(false); }} /> : null}
      {isTelegramOpen ? <TelegramDialog onClose={() => { setIsTelegramOpen(false); }} /> : null}
    </div>
  );
}
