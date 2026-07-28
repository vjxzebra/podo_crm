import { useEffect, useRef, useState } from "react";

import { Icon } from "../app/Icon";
import { useModalLifecycle } from "../app/useModalLifecycle";
import {
  createTelegramLinkIntent,
  disconnectTelegramSubscription,
  getTelegramSubscription,
  type TelegramLinkIntent,
  type TelegramSubscription,
} from "./telegramApi";

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "Не вказано";
  return new Intl.DateTimeFormat("uk-UA", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function TelegramDialog({ onClose }: { readonly onClose: () => void }) {
  const dialogRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const [subscription, setSubscription] = useState<TelegramSubscription | null>(null);
  const [intent, setIntent] = useState<TelegramLinkIntent | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);

  useModalLifecycle({
    dialogRef,
    initialFocusRef: closeRef,
    onEscape: onClose,
  });

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    void getTelegramSubscription(controller.signal)
      .then((result) => {
        if (!result.ok) {
          setError(result.error.message);
          return;
        }
        setSubscription(result.data);
      })
      .catch(() => {
        setError("Немає зв’язку із сервером. Спробуйте ще раз.");
      })
      .finally(() => {
        setIsLoading(false);
      });
    return () => {
      controller.abort();
    };
  }, []);

  async function createLink() {
    setIsCreating(true);
    setError(null);
    setStatusMessage(null);
    const result = await createTelegramLinkIntent().catch(() => null);
    setIsCreating(false);
    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
      return;
    }
    if (!result.ok) {
      setError(result.error.message);
      return;
    }
    setIntent(result.data);
    setStatusMessage("Посилання готове. Воно одноразове й діє 10 хвилин.");
  }

  async function disconnect() {
    setIsDisconnecting(true);
    setError(null);
    setStatusMessage(null);
    const result = await disconnectTelegramSubscription().catch(() => null);
    setIsDisconnecting(false);
    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
      return;
    }
    if (!result.ok) {
      setError(result.error.message);
      return;
    }
    setSubscription((current) => current === null ? current : { ...current, is_linked: false, is_enabled: false });
    setIntent(null);
    setStatusMessage("Telegram відключено для вашого профілю.");
  }

  async function copyLink() {
    if (intent === null) return;
    await navigator.clipboard.writeText(intent.url);
    setStatusMessage("Посилання скопійовано.");
  }

  const isLinked = subscription?.is_linked === true && subscription.is_enabled;
  const linkedName = (() => {
    if (subscription === null) return "Приватний чат";
    const username = subscription.username ?? "";
    if (username !== "") return `@${username}`;
    const firstName = subscription.first_name ?? "";
    return firstName !== "" ? firstName : "Приватний чат";
  })();
  const linkedDisplay = subscription === null
    ? "Приватний чат"
    : `${linkedName} · ${formatDateTime(subscription.linked_at)}`;

  return (
    <div className="modal-layer" role="presentation">
      <section
        aria-labelledby="telegram-dialog-title"
        aria-modal="true"
        className="modal-card telegram-dialog"
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        <header className="modal-card__header">
          <div>
            <p className="eyebrow">Особисті сповіщення</p>
            <h2 id="telegram-dialog-title">Telegram</h2>
            <p>Контактні дані нових заявок надходитимуть у ваш приватний чат.</p>
          </div>
          <button aria-label="Закрити Telegram" className="icon-button" onClick={onClose} ref={closeRef} type="button">
            <Icon name="close" />
          </button>
        </header>

        {isLoading ? <div className="form-message">Перевіряємо підключення…</div> : null}
        {error ? <div className="form-message form-message--error" role="alert">{error}</div> : null}
        {statusMessage ? <div className="form-message form-message--success" role="status">{statusMessage}</div> : null}

        {!isLoading ? (
          <div className="telegram-dialog__body">
            <div className="telegram-status">
              <span className={isLinked ? "telegram-status__dot telegram-status__dot--on" : "telegram-status__dot"} />
              <span>
                <strong>{isLinked ? "Підключено" : "Не підключено"}</strong>
                <small>
                  {isLinked
                    ? linkedDisplay
                    : "Створіть одноразове посилання та відкрийте його в Telegram."}
                </small>
              </span>
            </div>

            {intent ? (
              <div className="telegram-link-box">
                <input aria-label="Одноразове Telegram-посилання" readOnly value={intent.url} />
                <small>Діє до {formatDateTime(intent.expires_at)}.</small>
              </div>
            ) : null}
          </div>
        ) : null}

        <footer className="modal-card__footer">
          {intent ? (
            <>
              <a className="button button--primary" href={intent.url} rel="noreferrer" target="_blank">
                <Icon name="chevron" />
                Відкрити Telegram
              </a>
              <button className="button button--secondary" onClick={() => void copyLink()} type="button">
                Скопіювати
              </button>
            </>
          ) : (
            <button className="button button--primary" disabled={isCreating || isLoading} onClick={() => void createLink()} type="button">
              <Icon name="plus" />
              {isCreating ? "Створюємо…" : isLinked ? "Нове посилання" : "Підключити"}
            </button>
          )}
          {isLinked ? (
            <button className="button button--secondary" disabled={isDisconnecting} onClick={() => void disconnect()} type="button">
              {isDisconnecting ? "Відключаємо…" : "Відключити"}
            </button>
          ) : null}
        </footer>
      </section>
    </div>
  );
}
