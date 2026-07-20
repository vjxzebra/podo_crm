import { Route, Routes } from "react-router";

import { AppShell } from "./app/AppShell";
import { AuthBoundary } from "./app/AuthBoundary";
import { ContractLabPage, ModulePreviewPage, OverviewPage } from "./app/pages";
import { routeRegistry, type AppRouteDefinition } from "./app/routes";
import { SystemState, type SystemStateKind } from "./app/SystemState";

function pageForRoute(route: AppRouteDefinition) {
  if (route.surface === "overview") {
    return <OverviewPage />;
  }
  if (route.surface === "contract") {
    return <ContractLabPage />;
  }
  return <ModulePreviewPage route={route} />;
}

const stateRoutes = ["loading", "empty", "error", "forbidden"] as const satisfies readonly SystemStateKind[];

export function App() {
  return (
    <AuthBoundary state={{ status: "unconfigured" }}>
      <Routes>
        <Route element={<AppShell />}>
          {routeRegistry.map((route) => (
            <Route key={route.id} path={route.path} element={pageForRoute(route)} />
          ))}
          {stateRoutes.map((state) => (
            <Route key={state} path={`/previews/${state}`} element={<SystemState kind={state} />} />
          ))}
          <Route path="*" element={<SystemState kind="not-found" />} />
        </Route>
      </Routes>
    </AuthBoundary>
  );
}
