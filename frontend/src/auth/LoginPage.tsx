import { useEffect, useRef, useState, type SyntheticEvent } from "react";
import { Navigate, useLocation } from "react-router";

import { Icon } from "../app/Icon";
import { routeRegistry } from "../app/routes";
import { SystemState } from "../app/SystemState";
import { AuthApiError, useAuth } from "./AuthContext";

interface LoginLocationState {
  readonly from?: string;
}

export function LoginPage() {
  const { state, login, requestPasswordReset, retry } = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isResetOpen, setIsResetOpen] = useState(false);
  const [resetEmail, setResetEmail] = useState("");
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetMessage, setResetMessage] = useState<string | null>(null);
  const [isResetSubmitting, setIsResetSubmitting] = useState(false);
  const resetCloseButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isResetOpen) {
      return;
    }
    resetCloseButton.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isResetSubmitting) {
        setIsResetOpen(false);
      }
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [isResetOpen, isResetSubmitting]);

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
    if (state.session.must_change_password) {
      return <Navigate replace to="/first-login" />;
    }
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

  const submitReset = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    setResetError(null);
    setIsResetSubmitting(true);
    try {
      setResetMessage(await requestPasswordReset(resetEmail));
    } catch (reason) {
      setResetError(
        reason instanceof AuthApiError
          ? reason.fields.email?.[0] ?? reason.message
          : "Не вдалося створити запит. Спробуйте ще раз.",
      );
    } finally {
      setIsResetSubmitting(false);
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
              setResetEmail(email);
              setResetError(null);
              setResetMessage(null);
              setIsResetOpen(true);
            }}
            type="button"
          >
            Забули пароль?
          </button>
        </form>
      </section>
      {isResetOpen ? (
        <div className="modal-layer" role="dialog" aria-modal="true" aria-labelledby="reset-password-title">
          <div className="modal-card password-modal">
            <header className="modal-card__header">
              <div><p className="eyebrow">Відновлення доступу</p><h2 id="reset-password-title">Забули пароль?</h2></div>
              <button
                aria-label="Закрити відновлення пароля"
                className="icon-button"
                disabled={isResetSubmitting}
                onClick={() => { setIsResetOpen(false); }}
                ref={resetCloseButton}
                type="button"
              ><Icon name="close" /></button>
            </header>
            {resetMessage === null ? (
              <form onSubmit={(event) => { void submitReset(event); }}>
                <p className="modal-intro">Укажіть робочий email. Якщо активний профіль існує, адміністратор побачить запит і видасть новий тимчасовий пароль.</p>
                {resetError === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{resetError}</span></div>}
                <label className="form-field">
                  <span>Робочий email</span>
                  <input autoComplete="username" inputMode="email" name="reset-email" onChange={(event) => { setResetEmail(event.target.value); }} required type="email" value={resetEmail} />
                </label>
                <div className="modal-actions">
                  <button className="button button--secondary" disabled={isResetSubmitting} onClick={() => { setIsResetOpen(false); }} type="button">Скасувати</button>
                  <button className="button button--primary" disabled={isResetSubmitting} type="submit">{isResetSubmitting ? "Надсилаємо…" : "Створити запит"}</button>
                </div>
              </form>
            ) : (
              <div className="password-success">
                <span><Icon name="lock" /></span>
                <h3>Запит прийнято</h3>
                <p role="status">{resetMessage}</p>
                <button className="button button--primary button--full" onClick={() => { setIsResetOpen(false); }} type="button">Повернутися до входу</button>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </main>
  );
}
