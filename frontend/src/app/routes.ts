import type { IconName } from "./Icon";

export type RouteGroup = "primary" | "workspace" | "utility" | "preview";
export type RouteSurface = "overview" | "module" | "contract" | "state";

export interface AppRouteDefinition {
  readonly id: string;
  readonly path: string;
  readonly label: string;
  readonly shortLabel: string;
  readonly description: string;
  readonly icon: IconName;
  readonly group: RouteGroup;
  readonly surface: RouteSurface;
  readonly requiresSession: boolean;
}

/**
 * Client-side routing is presentation only. TP-201 will derive the visible
 * subset from the server session; this registry must never be used as an
 * authorization policy.
 */
export const routeRegistry = [
  {
    id: "overview",
    path: "/",
    label: "Огляд",
    shortLabel: "Огляд",
    description: "Операційний огляд кабінету",
    icon: "overview",
    group: "primary",
    surface: "overview",
    requiresSession: true,
  },
  {
    id: "calendar",
    path: "/calendar",
    label: "Календар",
    shortLabel: "Календар",
    description: "Розклад і майбутні записи",
    icon: "calendar",
    group: "primary",
    surface: "module",
    requiresSession: true,
  },
  {
    id: "patients",
    path: "/patients",
    label: "Пацієнти",
    shortLabel: "Пацієнти",
    description: "Каталог і картки пацієнтів",
    icon: "patients",
    group: "primary",
    surface: "module",
    requiresSession: true,
  },
  {
    id: "work-items",
    path: "/work-items",
    label: "Справи",
    shortLabel: "Справи",
    description: "Внутрішні завдання команди",
    icon: "tasks",
    group: "primary",
    surface: "module",
    requiresSession: true,
  },
  {
    id: "finance",
    path: "/finance",
    label: "Фінанси",
    shortLabel: "Фінанси",
    description: "Каса, оплати й повернення",
    icon: "finance",
    group: "workspace",
    surface: "module",
    requiresSession: true,
  },
  {
    id: "inventory",
    path: "/inventory",
    label: "Склад",
    shortLabel: "Склад",
    description: "Матеріали й рухи залишків",
    icon: "inventory",
    group: "workspace",
    surface: "module",
    requiresSession: true,
  },
  {
    id: "analytics",
    path: "/analytics",
    label: "Аналітика",
    shortLabel: "Аналітика",
    description: "Операційні показники та звіти",
    icon: "analytics",
    group: "workspace",
    surface: "module",
    requiresSession: true,
  },
  {
    id: "notifications",
    path: "/notifications",
    label: "Сповіщення",
    shortLabel: "Сповіщення",
    description: "Внутрішні події та нагадування",
    icon: "bell",
    group: "utility",
    surface: "module",
    requiresSession: true,
  },
  {
    id: "settings",
    path: "/settings",
    label: "Налаштування",
    shortLabel: "Налаштування",
    description: "Профіль кабінету й довідники",
    icon: "settings",
    group: "utility",
    surface: "module",
    requiresSession: true,
  },
  {
    id: "contracts",
    path: "/contracts",
    label: "API contract lab",
    shortLabel: "Контракти",
    description: "Типізовані OpenAPI fixtures із TP-102",
    icon: "code",
    group: "preview",
    surface: "contract",
    requiresSession: true,
  },
] as const satisfies readonly AppRouteDefinition[];

export const primaryRoutes = routeRegistry.filter((route) => route.group === "primary");
export const workspaceRoutes = routeRegistry.filter(
  (route) => route.group === "workspace" || route.group === "utility",
);
export const moreMenuRoutes = routeRegistry.filter(
  (route) => route.group !== "primary" || route.id === "work-items",
);

export function findRouteByPath(pathname: string): AppRouteDefinition | undefined {
  return routeRegistry.find((route) => route.path === pathname);
}
