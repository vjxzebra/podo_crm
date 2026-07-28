import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { useModalLifecycle } from "../app/useModalLifecycle";
import { csrfHeaders } from "../auth/AuthContext";

type Credential = components["schemas"]["BookingRequestApiCredential"];
type RotatedCredential = components["schemas"]["BookingRequestApiCredentialRotated"];

const dateTime = new Intl.DateTimeFormat("uk-UA", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Europe/Kyiv",
});

function RotationConfirmation({
  isRotating,
  onClose,
  onConfirm,
}: {
  readonly isRotating: boolean;
  readonly onClose: () => void;
  readonly onConfirm: () => void;
}) {
  const dialogRef = useRef<HTMLElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  useModalLifecycle({
    dialogRef,
    initialFocusRef: confirmRef,
    onEscape: () => {
      if (!isRotating) onClose();
    },
  });

  return (
    <div className="modal-layer" role="presentation">
      <section
        aria-describedby="booking-token-confirm-description"
        aria-labelledby="booking-token-confirm-title"
        aria-modal="true"
        className="modal-card booking-token-dialog"
        ref={dialogRef}
        role="alertdialog"
        tabIndex={-1}
      >
        <header className="modal-card__header">
          <div>
            <p className="eyebrow">Інтеграції · Безпека</p>
            <h2 id="booking-token-confirm-title">Згенерувати новий токен?</h2>
          </div>
          <button
            aria-label="Закрити підтвердження ротації"
            className="icon-button"
            disabled={isRotating}
            onClick={onClose}
            type="button"
          >
            <Icon name="close" />
          </button>
        </header>
        <div className="booking-token-warning" id="booking-token-confirm-description">
          <Icon name="warning" />
          <p>
            <strong>Поточний токен припинить діяти негайно.</strong>
            <span>Після ротації оновіть secret у всіх підключених формах.</span>
          </p>
        </div>
        <footer className="modal-card__footer">
          <button className="button button--secondary" disabled={isRotating} onClick={onClose} type="button">
            Скасувати
          </button>
          <button
            className="button button--danger"
            disabled={isRotating}
            onClick={onConfirm}
            ref={confirmRef}
            type="button"
          >
            {isRotating ? "Генеруємо…" : "Згенерувати новий"}
          </button>
        </footer>
      </section>
    </div>
  );
}

function OneTimeTokenDialog({
  onClose,
  token,
}: {
  readonly onClose: () => void;
  readonly token: string;
}) {
  const dialogRef = useRef<HTMLElement>(null);
  const copyRef = useRef<HTMLButtonElement>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");
  useModalLifecycle({ dialogRef, initialFocusRef: copyRef, onEscape: onClose });

  const copyToken = async () => {
    try {
      await navigator.clipboard.writeText(token);
      setCopyState("copied");
    } catch {
      setCopyState("error");
    }
  };

  return (
    <div className="modal-layer" role="presentation">
      <section
        aria-labelledby="booking-token-value-title"
        aria-modal="true"
        className="modal-card booking-token-dialog booking-token-dialog--value"
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        <header className="modal-card__header">
          <div>
            <p className="eyebrow">Показується один раз</p>
            <h2 id="booking-token-value-title">Новий API-токен</h2>
          </div>
          <button
            aria-label="Закрити новий API-токен"
            className="icon-button"
            onClick={onClose}
            type="button"
          >
            <Icon name="close" />
          </button>
        </header>
        <p className="modal-intro">
          Скопіюйте токен у server-side secret storage. Після закриття CRM не зможе
          показати його повторно.
        </p>
        <label className="form-field">
          <span>Новий API-токен</span>
          <input
            autoComplete="off"
            onFocus={(event) => {
              event.currentTarget.select();
            }}
            readOnly
            value={token}
          />
        </label>
        {copyState === "copied" ? (
          <div className="form-message form-message--success" role="status">
            <Icon name="check" />
            <span>Токен скопійовано.</span>
          </div>
        ) : null}
        {copyState === "error" ? (
          <div className="form-message form-message--error" role="alert">
            <Icon name="warning" />
            <span>Автоматичне копіювання недоступне. Скопіюйте значення з поля.</span>
          </div>
        ) : null}
        <footer className="modal-card__footer">
          <button className="button button--secondary" onClick={onClose} type="button">
            Я зберіг токен
          </button>
          <button className="button button--primary" onClick={() => void copyToken()} ref={copyRef} type="button">
            {copyState === "copied" ? "Скопійовано" : "Копіювати токен"}
          </button>
        </footer>
      </section>
    </div>
  );
}

export function BookingRequestIntegrationSettings() {
  const [credential, setCredential] = useState<Credential | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRotating, setIsRotating] = useState(false);
  const [confirmRotation, setConfirmRotation] = useState(false);
  const [oneTimeToken, setOneTimeToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const actionRef = useRef<HTMLButtonElement>(null);

  const loadCredential = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const result = await apiClient.GET("/api/v1/booking-request-integration").catch(() => null);
    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(result.error.message);
    } else {
      setCredential(result.data);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    void loadCredential();
  }, [loadCredential]);

  const closeConfirmation = () => {
    setConfirmRotation(false);
    window.setTimeout(() => actionRef.current?.focus(), 0);
  };

  const closeToken = () => {
    setOneTimeToken(null);
    window.setTimeout(() => actionRef.current?.focus(), 0);
  };

  const rotate = async () => {
    if (credential === null || isRotating) return;
    setIsRotating(true);
    setError(null);
    const result = await apiClient.POST("/api/v1/booking-request-integration/token/rotate", {
      body: { version: credential.version, confirm: true },
      headers: csrfHeaders(),
    }).catch(() => null);
    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(result.error.message);
      if (result.error.code === "version_conflict") {
        await loadCredential();
      }
    } else {
      const rotated: RotatedCredential = result.data;
      setCredential({
        is_configured: rotated.is_configured,
        rotated_at: rotated.rotated_at,
        rotated_by_display_name: rotated.rotated_by_display_name,
        token_hint: rotated.token_hint,
        version: rotated.version,
      });
      setConfirmRotation(false);
      setOneTimeToken(rotated.token);
    }
    setIsRotating(false);
  };

  if (isLoading) {
    return (
      <section className="panel settings-state">
        <span className="spinner" />
        <p>Завантажуємо налаштування інтеграції…</p>
      </section>
    );
  }

  return (
    <>
      <section className="panel settings-card booking-integration-card">
        <header>
          <div>
            <p className="eyebrow">Server-to-server · Bearer</p>
            <h2>API заявок на запис</h2>
            <p>Приймає заявки з Instagram, Facebook і сайту без доступу до CRM-сесії.</p>
          </div>
          <span className={`profile-status profile-status--${credential?.is_configured ? "active" : "inactive"}`}>
            <span />
            {credential?.is_configured ? "Налаштовано" : "Не налаштовано"}
          </span>
        </header>

        {error === null ? null : (
          <div className="form-message form-message--error" role="alert">
            <Icon name="warning" />
            <span>{error}</span>
            <button className="text-action" onClick={() => void loadCredential()} type="button">
              Оновити
            </button>
          </div>
        )}

        <div className="booking-integration-meta">
          <article>
            <span>Токен</span>
            <strong>{credential?.is_configured ? `••••••${credential.token_hint}` : "Ще не створено"}</strong>
            <small>Повне значення не зберігається у відкритому вигляді.</small>
          </article>
          <article>
            <span>Остання ротація</span>
            <strong>
              {credential?.rotated_at === null || credential?.rotated_at === undefined
                ? "Не виконувалась"
                : dateTime.format(new Date(credential.rotated_at))}
            </strong>
            <small>
              {credential?.rotated_by_display_name === undefined
                || credential.rotated_by_display_name === ""
                ? "Автор відсутній"
                : credential.rotated_by_display_name}
            </small>
          </article>
        </div>

        <div className="booking-integration-security">
          <Icon name="lock" />
          <p>
            <strong>Використовуйте токен лише на backend сайту або інтеграції.</strong>
            <span>Не додавайте його в JavaScript, HTML, GTM чи публічний репозиторій.</span>
          </p>
        </div>

        <footer>
          <span>Старий токен припиняє діяти одразу після ротації.</span>
          <button
            className={credential?.is_configured ? "button button--secondary" : "button button--primary"}
            disabled={credential === null || isRotating}
            onClick={() => {
              if (credential?.is_configured) {
                setConfirmRotation(true);
              } else {
                void rotate();
              }
            }}
            ref={actionRef}
            type="button"
          >
            <Icon name={credential?.is_configured ? "refresh" : "plus"} />
            {isRotating
              ? "Генеруємо…"
              : credential?.is_configured
                ? "Згенерувати новий"
                : "Згенерувати токен"}
          </button>
        </footer>
      </section>

      {confirmRotation ? (
        <RotationConfirmation
          isRotating={isRotating}
          onClose={closeConfirmation}
          onConfirm={() => void rotate()}
        />
      ) : null}
      {oneTimeToken === null ? null : <OneTimeTokenDialog onClose={closeToken} token={oneTimeToken} />}
    </>
  );
}
