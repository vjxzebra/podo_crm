import { Link, Outlet, useLocation } from "react-router";

import { DesktopNavigation, MobileNavigation } from "./Navigation";
import { roleLabels, useAuth } from "../auth/AuthContext";
import { Icon } from "./Icon";
import { findRouteByPath } from "./routes";

export function AppShell() {
  const location = useLocation();
  const currentRoute = findRouteByPath(location.pathname);
  const { state } = useAuth();
  if (state.status !== "authenticated") {
    return null;
  }
  const showForbiddenNotice = new URLSearchParams(location.search).get("notice") === "forbidden";

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
          <label className="global-search">
            <span className="visually-hidden">Глобальний пошук</span>
            <Icon name="search" />
            <input aria-describedby="search-preview-note" placeholder="Пацієнт, телефон або запис" readOnly />
            <kbd>⌘ K</kbd>
          </label>
          <span className="visually-hidden" id="search-preview-note">Пошук буде підключено в окремому task packet</span>
          <div className="topbar__actions">
            <span className="session-role" title="Роль із серверної сесії">
              <span className="session-role__dot" />
              {roleLabels[state.session.user.role]}
            </span>
            <Link className="icon-button topbar__notifications" to="/notifications" aria-label="Сповіщення">
              <Icon name="bell" />
              <span className="notification-dot" />
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
        <main className="content-wrap" id="main-content">
          <Outlet />
        </main>
      </div>
      <MobileNavigation />
    </div>
  );
}
