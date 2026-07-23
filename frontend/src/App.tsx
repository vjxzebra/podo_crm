import { Navigate, Route, Routes } from "react-router";

import { AnalyticsPage } from "./analytics/AnalyticsPage";
import { OverviewPage } from "./analytics/OverviewPage";
import { AuditPage } from "./audit/AuditPage";
import { AppShell } from "./app/AppShell";
import { AuthBoundary } from "./app/AuthBoundary";
import { ContractLabPage, ModulePreviewPage } from "./app/pages";
import { routeRegistry, type AppRouteDefinition } from "./app/routes";
import { SystemState, type SystemStateKind } from "./app/SystemState";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { LoginPage } from "./auth/LoginPage";
import { FirstLoginPage } from "./auth/PasswordLifecycle";
import { PasswordResetRequestsPage } from "./auth/PasswordResetRequestsPage";
import { CalendarPage } from "./calendar/CalendarPage";
import { FinancePage } from "./finance/FinancePage";
import { CashShiftHistoryPage } from "./finance/CashShiftHistoryPage";
import { InventoryPage } from "./inventory/InventoryPage";
import { NotificationsPage } from "./notifications/NotificationsPage";
import { PatientsPage } from "./patients/PatientsPage";
import { PatientDetailPage } from "./patients/PatientDetailPage";
import { SettingsPage } from "./settings/SettingsPage";
import { TeamPage } from "./team/TeamPage";
import { WorkItemsPage } from "./work-items/WorkItemsPage";
import { VisitPage } from "./visits/VisitPage";

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
  if (route.id === "patients") {
    return <PatientsPage />;
  }
  if (route.id === "work-items") {
    return <WorkItemsPage />;
  }
  if (route.id === "calendar") {
    return <CalendarPage />;
  }
  if (route.id === "inventory") {
    return <InventoryPage />;
  }
  if (route.id === "notifications") {
    return <NotificationsPage />;
  }
  if (route.id === "audit") {
    return <AuditPage />;
  }
  if (route.id === "analytics") {
    return <AnalyticsPage />;
  }
  if (route.id === "finance") {
    return <FinancePage />;
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

function PatientDetailRoute() {
  const { state } = useAuth();
  if (state.status !== "authenticated") {
    return null;
  }
  if (!state.session.route_ids.includes("patients")) {
    return <Navigate replace to="/?notice=forbidden" />;
  }
  return <PatientDetailPage />;
}

function VisitRoute() {
  const { state } = useAuth();
  if (state.status !== "authenticated") {
    return null;
  }
  if (state.session.user.role === "reception") {
    return <Navigate replace to="/?notice=forbidden" />;
  }
  return <VisitPage />;
}

function FinanceShiftHistoryRoute() {
  const { state } = useAuth();
  if (state.status !== "authenticated") {
    return null;
  }
  if (!state.session.route_ids.includes("finance")) {
    return <Navigate replace to="/?notice=forbidden" />;
  }
  return <CashShiftHistoryPage />;
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
          <Route path="/patients/:patientId/:tab?" element={<PatientDetailRoute />} />
          <Route path="/visits/:visitId" element={<VisitRoute />} />
          <Route path="/finance/shifts" element={<FinanceShiftHistoryRoute />} />
          {stateRoutes.map((stateKind) => (
            <Route key={stateKind} path={`/previews/${stateKind}`} element={<SystemState kind={stateKind} />} />
          ))}
          <Route path="*" element={<SystemState kind="not-found" />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
