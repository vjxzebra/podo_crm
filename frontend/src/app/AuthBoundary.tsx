import type { ReactNode } from "react";

import { SystemState } from "./SystemState";

export type AuthBoundaryState =
  | { readonly status: "unconfigured" }
  | { readonly status: "checking" }
  | { readonly status: "anonymous" }
  | { readonly status: "authenticated" }
  | { readonly status: "forbidden" }
  | { readonly status: "error" };

interface AuthBoundaryProps {
  readonly state: AuthBoundaryState;
  readonly children: ReactNode;
}

/**
 * A rendering contract for TP-201. It deliberately contains no roles,
 * permissions, route allowlists, or client-side authorization decisions.
 */
export function AuthBoundary({ state, children }: AuthBoundaryProps) {
  if (state.status === "unconfigured" || state.status === "authenticated") {
    return <div data-auth-boundary={state.status}>{children}</div>;
  }

  const stateKind =
    state.status === "checking"
      ? "loading"
      : state.status === "error"
        ? "error"
        : state.status;

  return (
    <main className="standalone-state">
      <a className="skip-link" href="#auth-state">
        До повідомлення
      </a>
      <div id="auth-state">
        <SystemState kind={stateKind} />
      </div>
    </main>
  );
}
