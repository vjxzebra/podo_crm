import { Link, Outlet, useLocation } from "react-router";

import { DesktopNavigation, MobileNavigation } from "./Navigation";
import { Icon } from "./Icon";
import { findRouteByPath } from "./routes";

export function AppShell() {
  const location = useLocation();
  const currentRoute = findRouteByPath(location.pathname);

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
            <span className="session-role" title="Роль надасть серверна сесія">
              <span className="session-role__dot" />
              Роль із сесії
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
        <div className="preview-banner" role="note">
          <Icon name="lock" />
          <span><strong>UI preview.</strong> Реальну сесію та рольову навігацію підключить TP-201.</span>
        </div>
        <main className="content-wrap" id="main-content">
          <Outlet />
        </main>
      </div>
      <MobileNavigation />
    </div>
  );
}
