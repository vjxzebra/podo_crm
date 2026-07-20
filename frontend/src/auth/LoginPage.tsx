import { useState, type SyntheticEvent } from "react";
import { Navigate, useLocation } from "react-router";

import { Icon } from "../app/Icon";
import { routeRegistry } from "../app/routes";
import { SystemState } from "../app/SystemState";
import { useAuth } from "./AuthContext";

interface LoginLocationState {
  readonly from?: string;
}

export function LoginPage() {
  const { state, login, retry } = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resetNotice, setResetNotice] = useState(false);

  const requestedPath = (location.state as LoginLocationState | null)?.from;

  if (state.status === "checking") {
    return (
      <main className="standalone-state">
        <SystemState kind="loading" />
      </main>
    );
  }

  if (state.status === "error") {
    return (
      <main className="standalone-state">
        <SystemState kind="error" onAction={() => void retry()} />
      </main>
    );
  }

  if (state.status === "authenticated") {
    const requestedRoute = routeRegistry.find((route) => route.path === requestedPath);
    const destination =
      requestedRoute !== undefined && state.session.route_ids.includes(requestedRoute.id)
        ? requestedRoute.path
        : "/";
    return <Navigate replace to={destination} />;
  }

  const submit = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login({ email, password });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не вдалося увійти. Спробуйте ще раз.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="login-page">
      <a className="skip-link" href="#login-form">До форми входу</a>
      <section className="login-brand-panel" aria-label="Podoria CRM">
        <span className="login-brand-mark">P</span>
        <p className="eyebrow">Podoria CRM</p>
        <h1>Спокійний простір для щоденної роботи кабінету.</h1>
        <p>Записи, пацієнти й операційні справи — у межах вашої серверної ролі.</p>
        <div className="login-brand-panel__security">
          <Icon name="lock" />
          <span>Роль і доступ визначає захищена сесія</span>
        </div>
      </section>
      <section className="login-form-panel">
        <form
          className="login-card"
          id="login-form"
          onSubmit={(event) => {
            void submit(event);
          }}
        >
          <div className="login-card__mobile-brand" aria-hidden="true">
            <span className="brand__mark">P</span>
            <strong>Podoria</strong>
          </div>
          <p className="eyebrow">Робочий простір</p>
          <h2>Вхід до кабінету</h2>
          <p className="login-card__intro">Використайте email і пароль вашого облікового запису.</p>

          {error === null ? null : (
            <div className="form-message form-message--error" role="alert">
              <Icon name="warning" />
              <span>{error}</span>
            </div>
          )}

          <label className="form-field">
            <span>Email</span>
            <input
              autoComplete="username"
              inputMode="email"
              name="email"
              onChange={(event) => {
                setEmail(event.target.value);
              }}
              placeholder="name@podoria.ua"
              required
              type="email"
              value={email}
            />
          </label>

          <label className="form-field">
            <span>Пароль</span>
            <span className="password-field">
              <input
                autoComplete="current-password"
                name="password"
                onChange={(event) => {
                  setPassword(event.target.value);
                }}
                required
                type={showPassword ? "text" : "password"}
                value={password}
              />
              <button
                aria-label={showPassword ? "Приховати пароль" : "Показати пароль"}
                onClick={() => {
                  setShowPassword((current) => !current);
                }}
                type="button"
              >
                {showPassword ? "Сховати" : "Показати"}
              </button>
            </span>
          </label>

          <button className="button button--primary button--full login-submit" disabled={isSubmitting} type="submit">
            {isSubmitting ? "Входимо…" : "Увійти"}
          </button>

          <button
            className="login-reset-link"
            onClick={() => {
              setResetNotice(true);
            }}
            type="button"
          >
            Забули пароль?
          </button>
          {resetNotice ? (
            <p className="login-reset-notice" role="status">Відновлення пароля буде підключено в TP-202.</p>
          ) : null}
        </form>
      </section>
    </main>
  );
}
