import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import { useAuth } from "../auth/AuthContext";
import { SystemState } from "./SystemState";

interface AuthBoundaryProps {
  readonly children: ReactNode;
}

export function AuthBoundary({ children }: AuthBoundaryProps) {
  const { state, retry } = useAuth();
  const location = useLocation();

  if (state.status === "authenticated") {
    if (state.session.must_change_password) {
      return <Navigate replace to="/first-login" />;
    }
    return <div data-auth-boundary="authenticated">{children}</div>;
  }

  if (state.status === "anonymous") {
    return <Navigate replace state={{ from: location.pathname, reason: state.reason }} to="/login" />;
  }

  return (
    <main className="standalone-state">
      <a className="skip-link" href="#auth-state">
        До повідомлення
      </a>
      <div id="auth-state">
        <SystemState
          kind={state.status === "checking" ? "loading" : "error"}
          onAction={state.status === "error" ? () => void retry() : undefined}
        />
      </div>
    </main>
  );
}
