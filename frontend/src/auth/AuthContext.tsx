import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";

export type SessionData = components["schemas"]["Session"];
export type UserRole = components["schemas"]["RoleEnum"];

type AuthState =
  | { readonly status: "checking" }
  | { readonly status: "anonymous" }
  | { readonly status: "authenticated"; readonly session: SessionData }
  | { readonly status: "error" };

interface LoginInput {
  readonly email: string;
  readonly password: string;
}

interface AuthContextValue {
  readonly state: AuthState;
  readonly login: (input: LoginInput) => Promise<void>;
  readonly logout: () => Promise<void>;
  readonly retry: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const CSRF_COOKIE_NAME = "podoria_csrftoken";

function csrfToken(): string | undefined {
  const prefix = `${CSRF_COOKIE_NAME}=`;
  const value = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  return value === undefined ? undefined : decodeURIComponent(value.slice(prefix.length));
}

function csrfHeaders(): HeadersInit {
  const token = csrfToken();
  return token === undefined ? {} : { "X-CSRFToken": token };
}

async function retrieveSession(): Promise<AuthState> {
  try {
    const { data, response } = await apiClient.GET("/api/v1/session");
    if (data !== undefined) {
      return { status: "authenticated", session: data };
    }
    return response.status === 401 ? { status: "anonymous" } : { status: "error" };
  } catch {
    return { status: "error" };
  }
}

export function AuthProvider({ children }: { readonly children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "checking" });

  const retry = useCallback(async () => {
    setState({ status: "checking" });
    setState(await retrieveSession());
  }, []);

  useEffect(() => {
    let active = true;
    void retrieveSession().then((nextState) => {
      if (active) {
        setState(nextState);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async ({ email, password }: LoginInput) => {
    const result = await apiClient
      .POST("/api/v1/auth/login", {
        body: { email, password },
        headers: csrfHeaders(),
      })
      .catch(() => null);
    if (result === null) {
      throw new Error("Немає зв’язку із сервером. Спробуйте ще раз.");
    }
    const { data, error } = result;
    if (data === undefined) {
      throw new Error(error.message);
    }
    setState({ status: "authenticated", session: data });
  }, []);

  const logout = useCallback(async () => {
    const result = await apiClient
      .POST("/api/v1/auth/logout", {
        headers: csrfHeaders(),
      })
      .catch(() => null);
    if (result === null) {
      throw new Error("Немає зв’язку із сервером. Спробуйте ще раз.");
    }
    const { response } = result;
    if (!response.ok) {
      throw new Error("Не вдалося завершити сесію. Спробуйте ще раз.");
    }
    setState({ status: "anonymous" });
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ state, login, logout, retry }),
    [state, login, logout, retry],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (value === null) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }
  return value;
}

export const roleLabels: Record<UserRole, string> = {
  podologist: "Подолог",
  reception: "Рецепція",
  admin: "Адміністратор",
};
