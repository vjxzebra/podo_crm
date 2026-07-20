import { useEffect, useId, useRef, useState, type SyntheticEvent } from "react";
import { Navigate } from "react-router";

import { Icon } from "../app/Icon";
import { SystemState } from "../app/SystemState";
import { AuthApiError, useAuth } from "./AuthContext";

interface PasswordInputProps {
  readonly autoComplete: string;
  readonly error?: string | undefined;
  readonly label: string;
  readonly name: string;
  readonly onChange: (value: string) => void;
  readonly value: string;
}

function PasswordInput({ autoComplete, error, label, name, onChange, value }: PasswordInputProps) {
  const [isVisible, setIsVisible] = useState(false);
  const errorId = useId();
  return (
    <label className="form-field">
      <span>{label}</span>
      <span className="password-field">
        <input
          aria-describedby={error === undefined ? undefined : errorId}
          aria-invalid={error === undefined ? undefined : true}
          autoComplete={autoComplete}
          minLength={8}
          name={name}
          onChange={(event) => {
            onChange(event.target.value);
          }}
          required
          type={isVisible ? "text" : "password"}
          value={value}
        />
        <button
          aria-label={isVisible ? `Приховати: ${label}` : `Показати: ${label}`}
          onClick={() => {
            setIsVisible((current) => !current);
          }}
          type="button"
        >
          {isVisible ? "Сховати" : "Показати"}
        </button>
      </span>
      {error === undefined ? null : <small className="field-error" id={errorId}>{error}</small>}
    </label>
  );
}

function errorFields(reason: unknown): Readonly<Record<string, readonly string[]>> {
  return reason instanceof AuthApiError ? reason.fields : {};
}

function errorMessage(reason: unknown, fallback: string): string {
  return reason instanceof Error ? reason.message : fallback;
}

export function FirstLoginPage() {
  const { state, completeFirstLogin, logout, requestPasswordReset, retry } = useAuth();
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Readonly<Record<string, readonly string[]>>>({});
  const [resetMessage, setResetMessage] = useState<string | null>(null);
  const [expiredByServer, setExpiredByServer] = useState(false);

  if (state.status === "checking") {
    return <main className="standalone-state"><SystemState kind="loading" /></main>;
  }
  if (state.status === "error") {
    return (
      <main className="standalone-state">
        <SystemState kind="error" onAction={() => void retry()} />
      </main>
    );
  }
  if (state.status === "anonymous") {
    return <Navigate replace to="/login" />;
  }
  if (!state.session.must_change_password) {
    return <Navigate replace to="/" />;
  }

  const expired = state.session.temporary_password_expired || expiredByServer;

  const submit = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    setError(null);
    setFields({});
    if (newPassword !== confirmation) {
      setFields({ new_password_confirmation: ["Паролі не збігаються."] });
      return;
    }
    setIsSubmitting(true);
    try {
      await completeFirstLogin({
        newPassword,
        newPasswordConfirmation: confirmation,
      });
    } catch (reason) {
      if (reason instanceof AuthApiError && reason.code === "temporary_password_expired") {
        setExpiredByServer(true);
      }
      setFields(errorFields(reason));
      setError(errorMessage(reason, "Не вдалося зберегти пароль."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const createResetRequest = async () => {
    setError(null);
    setIsSubmitting(true);
    try {
      setResetMessage(await requestPasswordReset(state.session.user.email));
    } catch (reason) {
      setError(errorMessage(reason, "Не вдалося створити запит."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const exitToLogin = async () => {
    setError(null);
    setIsSubmitting(true);
    try {
      await logout();
    } catch (reason) {
      setError(errorMessage(reason, "Не вдалося завершити сесію."));
      setIsSubmitting(false);
    }
  };

  return (
    <main className="password-gate">
      <section className="password-gate__brand" aria-label="Podoria CRM">
        <span className="login-brand-mark">P</span>
        <p className="eyebrow">Захищений перший вхід</p>
        <h1>Тимчасовий пароль — лише ключ до цієї форми.</h1>
        <p>Робочі розділи стануть доступними після створення вашого особистого пароля.</p>
      </section>
      <section className="password-gate__panel">
        <form className="password-card" onSubmit={(event) => void submit(event)}>
          <span className="password-card__icon"><Icon name={expired ? "warning" : "lock"} /></span>
          <p className="eyebrow">{expired ? "Потрібна допомога адміністратора" : "Перший вхід"}</p>
          <h2>{expired ? "Тимчасовий пароль більше не діє" : "Створіть власний пароль"}</h2>
          <p>
            {expired
              ? "Створіть запит на відновлення. Відповідальний адміністратор перевірить його й видасть новий тимчасовий пароль."
              : `Ви увійшли як ${state.session.user.display_name}. Новий пароль має містити щонайменше 8 символів і не бути надто поширеним.`}
          </p>

          {error === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div>}
          {resetMessage === null ? null : <div className="form-message form-message--success" role="status"><Icon name="lock" /><span>{resetMessage}</span></div>}

          {expired ? (
            <button className="button button--primary button--full" disabled={isSubmitting || resetMessage !== null} onClick={() => void createResetRequest()} type="button">
              {isSubmitting ? "Створюємо запит…" : "Створити запит на відновлення"}
            </button>
          ) : (
            <>
              <PasswordInput
                autoComplete="new-password"
                error={fields.new_password?.[0]}
                label="Новий пароль"
                name="new-password"
                onChange={setNewPassword}
                value={newPassword}
              />
              <PasswordInput
                autoComplete="new-password"
                error={fields.new_password_confirmation?.[0]}
                label="Повторіть новий пароль"
                name="new-password-confirmation"
                onChange={setConfirmation}
                value={confirmation}
              />
              <button className="button button--primary button--full" disabled={isSubmitting} type="submit">
                {isSubmitting ? "Зберігаємо…" : "Зберегти й продовжити"}
              </button>
            </>
          )}
          <button className="text-action" disabled={isSubmitting} onClick={() => void exitToLogin()} type="button">Вийти й повернутися до входу</button>
        </form>
      </section>
    </main>
  );
}

interface ChangePasswordDialogProps {
  readonly onClose: () => void;
}

export function ChangePasswordDialog({ onClose }: ChangePasswordDialogProps) {
  const { changePassword } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Readonly<Record<string, readonly string[]>>>({});
  const closeButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeButton.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isSubmitting) {
        onClose();
      }
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [isSubmitting, onClose]);

  const submit = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    setError(null);
    setFields({});
    if (newPassword !== confirmation) {
      setFields({ new_password_confirmation: ["Паролі не збігаються."] });
      return;
    }
    setIsSubmitting(true);
    try {
      await changePassword({
        currentPassword,
        newPassword,
        newPasswordConfirmation: confirmation,
      });
      setIsComplete(true);
    } catch (reason) {
      setFields(errorFields(reason));
      setError(errorMessage(reason, "Не вдалося змінити пароль."));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-layer" role="dialog" aria-modal="true" aria-labelledby="change-password-title">
      <div className="modal-card password-modal">
        <header className="modal-card__header">
          <div><p className="eyebrow">Безпека профілю</p><h2 id="change-password-title">Змінити пароль</h2></div>
          <button aria-label="Закрити зміну пароля" className="icon-button" disabled={isSubmitting} onClick={onClose} ref={closeButton} type="button"><Icon name="close" /></button>
        </header>
        {isComplete ? (
          <div className="password-success">
            <span><Icon name="lock" /></span>
            <h3>Пароль змінено</h3>
            <p>Поточна сесія залишилася активною, решту ваших сесій відкликано.</p>
            <button className="button button--primary button--full" onClick={onClose} type="button">Готово</button>
          </div>
        ) : (
          <form onSubmit={(event) => void submit(event)}>
            <p className="modal-intro">Укажіть поточний пароль і створіть новий. Після збереження інші пристрої потрібно буде авторизувати повторно.</p>
            {error === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div>}
            <PasswordInput autoComplete="current-password" error={fields.current_password?.[0]} label="Поточний пароль" name="current-password" onChange={setCurrentPassword} value={currentPassword} />
            <PasswordInput autoComplete="new-password" error={fields.new_password?.[0]} label="Новий пароль" name="new-password" onChange={setNewPassword} value={newPassword} />
            <PasswordInput autoComplete="new-password" error={fields.new_password_confirmation?.[0]} label="Повторіть новий пароль" name="new-password-confirmation" onChange={setConfirmation} value={confirmation} />
            <div className="modal-actions">
              <button className="button button--secondary" disabled={isSubmitting} onClick={onClose} type="button">Скасувати</button>
              <button className="button button--primary" disabled={isSubmitting} type="submit">{isSubmitting ? "Зберігаємо…" : "Змінити пароль"}</button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
