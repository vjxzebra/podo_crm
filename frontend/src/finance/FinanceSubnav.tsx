import { NavLink } from "react-router";

import { Icon } from "../app/Icon";

export function FinanceSubnav() {
  return (
    <nav aria-label="Розділи фінансів" className="finance-subnav">
      <NavLink className={({ isActive }) => `finance-subnav__link${isActive ? " finance-subnav__link--active" : ""}`} end to="/finance"><Icon name="finance" />Поточна каса</NavLink>
      <NavLink className={({ isActive }) => `finance-subnav__link${isActive ? " finance-subnav__link--active" : ""}`} to="/finance/shifts"><Icon name="calendar" />Історія змін</NavLink>
    </nav>
  );
}
