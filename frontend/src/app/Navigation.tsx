import { useEffect, useRef, useState } from "react";
import { Link, NavLink } from "react-router";

import { roleLabels, useAuth } from "../auth/AuthContext";
import { Icon } from "./Icon";
import { routesForIds, type AppRouteDefinition } from "./routes";

interface RouteLinkProps {
  readonly route: AppRouteDefinition;
  readonly onNavigate?: () => void;
}

function RouteLink({ route, onNavigate }: RouteLinkProps) {
  return (
    <NavLink
      aria-label={route.label}
      className={({ isActive }) => `nav-item${isActive ? " nav-item--active" : ""}`}
      end={route.path === "/"}
      onClick={onNavigate}
      title={route.label}
      to={route.path}
    >
      <span className="nav-item__icon"><Icon name={route.icon} /></span>
      <span className="nav-item__label">{route.label}</span>
      <Icon className="nav-item__chevron" name="chevron" />
    </NavLink>
  );
}

function initials(displayName: string): string {
  return displayName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toLocaleUpperCase("uk");
}

export function DesktopNavigation() {
  const { state, logout } = useAuth();
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  if (state.status !== "authenticated") {
    return null;
  }

  const routes = routesForIds(state.session.route_ids);
  const primaryRoutes = routes.filter((route) => route.group === "primary");
  const workspaceRoutes = routes.filter(
    (route) => route.group === "workspace" || route.group === "utility",
  );
  const contractRoute = routes.find((route) => route.id === "contracts");
  const user = state.session.user;

  const signOut = async () => {
    setLogoutError(null);
    setIsLoggingOut(true);
    try {
      await logout();
    } catch (reason) {
      setLogoutError(reason instanceof Error ? reason.message : "Не вдалося завершити сесію.");
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <aside className="sidebar" data-testid="desktop-sidebar">
      <Link className="brand" to="/" aria-label="Podoria CRM — на огляд">
        <span className="brand__mark">P</span>
        <span className="brand__wordmark">Podoria</span>
      </Link>

      <nav className="sidebar__navigation" aria-label="Основна навігація">
        <div className="nav-group">
          <p className="nav-group__label">Робочий простір</p>
          {primaryRoutes.map((route) => <RouteLink key={route.id} route={route} />)}
        </div>
        {workspaceRoutes.length === 0 ? null : (
          <div className="nav-group nav-group--secondary">
            <p className="nav-group__label">Керування</p>
            {workspaceRoutes.map((route) => <RouteLink key={route.id} route={route} />)}
          </div>
        )}
      </nav>

      <div className="sidebar__footer">
        {contractRoute === undefined ? null : <RouteLink route={contractRoute} />}
        <div className="profile-area">
          <button
            aria-expanded={isProfileOpen}
            aria-haspopup="menu"
            className="profile-mini"
            onClick={() => {
              setIsProfileOpen((current) => !current);
            }}
            type="button"
          >
            <span className="avatar" aria-hidden="true">{initials(user.display_name)}</span>
            <span className="profile-mini__copy">
              <strong>{user.display_name}</strong>
              <small>{roleLabels[user.role]}</small>
            </span>
            <Icon className="profile-mini__chevron" name="chevron" />
          </button>
          {isProfileOpen ? (
            <div className="profile-popover" role="menu">
              <span>{user.email}</span>
              <button disabled={isLoggingOut} onClick={() => void signOut()} role="menuitem" type="button">
                {isLoggingOut ? "Виходимо…" : "Вийти"}
              </button>
              {logoutError === null ? null : <p className="profile-logout-error" role="alert">{logoutError}</p>}
            </div>
          ) : null}
        </div>
      </div>
    </aside>
  );
}

export function MobileNavigation() {
  const { state, logout } = useAuth();
  const [isMoreOpen, setIsMoreOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const moreButtonRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isMoreOpen) {
      return;
    }
    closeButtonRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsMoreOpen(false);
        moreButtonRef.current?.focus();
      }
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [isMoreOpen]);

  if (state.status !== "authenticated") {
    return null;
  }

  const routes = routesForIds(state.session.route_ids);
  const primaryRoutes = routes.filter((route) => route.group === "primary");
  const moreMenuRoutes = routes.filter((route) => route.group !== "primary" || route.id === "work-items");
  const user = state.session.user;
  const closeMore = () => {
    setIsMoreOpen(false);
    moreButtonRef.current?.focus();
  };

  const signOut = async () => {
    setLogoutError(null);
    setIsLoggingOut(true);
    try {
      await logout();
    } catch (reason) {
      setLogoutError(reason instanceof Error ? reason.message : "Не вдалося завершити сесію.");
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <>
      <nav className="mobile-bottom-nav" aria-label="Мобільна навігація" data-testid="mobile-bottom-nav">
        {primaryRoutes.slice(0, 2).map((route) => <RouteLink key={route.id} route={route} />)}
        <Link className="mobile-primary-action" to="/calendar?compose=appointment" aria-label="Новий запис">
          <Icon name="plus" />
        </Link>
        {primaryRoutes.slice(2, 3).map((route) => <RouteLink key={route.id} route={route} />)}
        <button
          aria-expanded={isMoreOpen}
          aria-haspopup="dialog"
          className="nav-item mobile-more-button"
          onClick={() => {
            setIsMoreOpen(true);
          }}
          ref={moreButtonRef}
          type="button"
        >
          <span className="nav-item__icon"><Icon name="menu" /></span>
          <span className="nav-item__label">Ще</span>
        </button>
      </nav>

      {isMoreOpen ? (
        <div className="mobile-more" role="dialog" aria-modal="true" aria-labelledby="mobile-more-title">
          <button className="mobile-more__scrim" onClick={closeMore} type="button" aria-label="Закрити меню" />
          <section className="mobile-more__sheet">
            <div className="mobile-more__handle" aria-hidden="true" />
            <header className="mobile-more__header">
              <span className="avatar" aria-hidden="true">{initials(user.display_name)}</span>
              <span>
                <strong id="mobile-more-title">{user.display_name}</strong>
                <small>{roleLabels[user.role]}</small>
              </span>
              <button className="icon-button" onClick={closeMore} ref={closeButtonRef} type="button" aria-label="Закрити додаткове меню">
                <Icon name="close" />
              </button>
            </header>
            <Link aria-label="Глобальний пошук" className="mobile-search-action" onClick={closeMore} to="/previews/empty">
              <span className="nav-item__icon"><Icon name="search" /></span>
              <span><strong>Глобальний пошук</strong><small>Пошук пацієнтів і записів</small></span>
              <Icon name="chevron" />
            </Link>
            <nav className="mobile-more__grid" aria-label="Додаткові розділи">
              {moreMenuRoutes.map((route) => <RouteLink key={route.id} route={route} onNavigate={closeMore} />)}
            </nav>
            <button className="mobile-logout" disabled={isLoggingOut} onClick={() => void signOut()} type="button">
              {isLoggingOut ? "Виходимо…" : "Вийти із системи"}
            </button>
            {logoutError === null ? null : <p className="profile-logout-error" role="alert">{logoutError}</p>}
          </section>
        </div>
      ) : null}
    </>
  );
}
