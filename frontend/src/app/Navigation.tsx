import { useEffect, useRef, useState } from "react";
import { Link, NavLink } from "react-router";

import { Icon } from "./Icon";
import {
  moreMenuRoutes,
  primaryRoutes,
  routeRegistry,
  workspaceRoutes,
  type AppRouteDefinition,
} from "./routes";

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
      <span className="nav-item__icon">
        <Icon name={route.icon} />
      </span>
      <span className="nav-item__label">{route.label}</span>
      <Icon className="nav-item__chevron" name="chevron" />
    </NavLink>
  );
}

export function DesktopNavigation() {
  const contractRoute = routeRegistry.find((route) => route.id === "contracts");

  return (
    <aside className="sidebar" data-testid="desktop-sidebar">
      <Link className="brand" to="/" aria-label="Podoria CRM — на огляд">
        <span className="brand__mark">P</span>
        <span className="brand__wordmark">Podoria</span>
      </Link>

      <nav className="sidebar__navigation" aria-label="Основна навігація">
        <div className="nav-group">
          <p className="nav-group__label">Робочий простір</p>
          {primaryRoutes.map((route) => (
            <RouteLink key={route.id} route={route} />
          ))}
        </div>

        <div className="nav-group nav-group--secondary">
          <p className="nav-group__label">Керування</p>
          {workspaceRoutes.map((route) => (
            <RouteLink key={route.id} route={route} />
          ))}
        </div>
      </nav>

      <div className="sidebar__footer">
        {contractRoute === undefined ? null : <RouteLink route={contractRoute} />}
        <div className="profile-mini">
          <span className="avatar" aria-hidden="true">
            К
          </span>
          <span className="profile-mini__copy">
            <strong>Користувач</strong>
            <small>Роль із сесії API</small>
          </span>
          <Icon className="profile-mini__chevron" name="chevron" />
        </div>
      </div>
    </aside>
  );
}

export function MobileNavigation() {
  const [isMoreOpen, setIsMoreOpen] = useState(false);
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

  const closeMore = () => {
    setIsMoreOpen(false);
    moreButtonRef.current?.focus();
  };

  return (
    <>
      <nav className="mobile-bottom-nav" aria-label="Мобільна навігація" data-testid="mobile-bottom-nav">
        {primaryRoutes.slice(0, 2).map((route) => (
          <RouteLink key={route.id} route={route} />
        ))}
        <Link className="mobile-primary-action" to="/calendar?compose=appointment" aria-label="Новий запис — прототип">
          <Icon name="plus" />
        </Link>
        {primaryRoutes.slice(2, 3).map((route) => (
          <RouteLink key={route.id} route={route} />
        ))}
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
          <span className="nav-item__icon">
            <Icon name="menu" />
          </span>
          <span className="nav-item__label">Ще</span>
        </button>
      </nav>

      {isMoreOpen ? (
        <div className="mobile-more" role="dialog" aria-modal="true" aria-labelledby="mobile-more-title">
          <button className="mobile-more__scrim" onClick={closeMore} type="button" aria-label="Закрити меню" />
          <section className="mobile-more__sheet">
            <div className="mobile-more__handle" aria-hidden="true" />
            <header className="mobile-more__header">
              <span className="avatar" aria-hidden="true">
                К
              </span>
              <span>
                <strong id="mobile-more-title">Робочий простір</strong>
                <small>Доступні пункти визначить сесія API</small>
              </span>
              <button
                className="icon-button"
                onClick={closeMore}
                ref={closeButtonRef}
                type="button"
                aria-label="Закрити додаткове меню"
              >
                <Icon name="close" />
              </button>
            </header>
            <Link aria-label="Глобальний пошук" className="mobile-search-action" onClick={closeMore} to="/previews/empty">
              <span className="nav-item__icon">
                <Icon name="search" />
              </span>
              <span>
                <strong>Глобальний пошук</strong>
                <small>Пошук пацієнтів і записів</small>
              </span>
              <Icon name="chevron" />
            </Link>
            <nav className="mobile-more__grid" aria-label="Додаткові розділи">
              {moreMenuRoutes.map((route) => (
                <RouteLink key={route.id} route={route} onNavigate={closeMore} />
              ))}
            </nav>
          </section>
        </div>
      ) : null}
    </>
  );
}
