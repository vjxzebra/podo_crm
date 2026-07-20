import { Navigate, Route, Routes } from "react-router";

import { AppShell } from "./app/AppShell";
import { AuthBoundary } from "./app/AuthBoundary";
import { ContractLabPage, ModulePreviewPage, OverviewPage } from "./app/pages";
import { routeRegistry, type AppRouteDefinition } from "./app/routes";
import { SystemState, type SystemStateKind } from "./app/SystemState";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { LoginPage } from "./auth/LoginPage";
import { FirstLoginPage } from "./auth/PasswordLifecycle";
import { PasswordResetRequestsPage } from "./auth/PasswordResetRequestsPage";
import { SettingsPage } from "./settings/SettingsPage";
import { TeamPage } from "./team/TeamPage";

function pageForRoute(route: AppRouteDefinition) {
  if (route.id === "password-resets") {
    return <PasswordResetRequestsPage />;
  }
  if (route.id === "team") {
    return <TeamPage />;
  }
  if (route.id === "settings") {
    return <SettingsPage />;
  }
  if (route.surface === "overview") {
    return <OverviewPage />;
  }
  if (route.surface === "contract") {
    return <ContractLabPage />;
  }
  return <ModulePreviewPage route={route} />;
}

const stateRoutes = ["loading", "empty", "error", "forbidden"] as const satisfies readonly SystemStateKind[];

function RoleSafePage({ route }: { readonly route: AppRouteDefinition }) {
  const { state } = useAuth();
  if (state.status !== "authenticated") {
    return null;
  }
  if (!state.session.route_ids.includes(route.id)) {
    return <Navigate replace to="/?notice=forbidden" />;
  }
  return pageForRoute(route);
}

export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/first-login" element={<FirstLoginPage />} />
        <Route
          element={
            <AuthBoundary>
              <AppShell />
            </AuthBoundary>
          }
        >
          {routeRegistry.map((route) => (
            <Route key={route.id} path={route.path} element={<RoleSafePage route={route} />} />
          ))}
          {stateRoutes.map((stateKind) => (
            <Route key={stateKind} path={`/previews/${stateKind}`} element={<SystemState kind={stateKind} />} />
          ))}
          <Route path="*" element={<SystemState kind="not-found" />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
