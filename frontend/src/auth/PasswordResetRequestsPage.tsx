import { useCallback, useEffect, useState, type SyntheticEvent } from "react";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { roleLabels, csrfHeaders } from "./AuthContext";

type ResetRequest = components["schemas"]["PasswordResetRequestItem"];

function formatRequestedAt(value: string): string {
  return new Intl.DateTimeFormat("uk-UA", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function PasswordResetRequestsPage() {
  const [requests, setRequests] = useState<readonly ResetRequest[]>([]);
  const [selected, setSelected] = useState<ResetRequest | null>(null);
  const [temporaryPassword, setTemporaryPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadRequests = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const result = await apiClient.GET("/api/v1/password-reset-requests").catch(() => null);
    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(result.error.message);
    } else {
      setRequests(result.data.requests);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    void loadRequests();
  }, [loadRequests]);

  const submit = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    if (selected === null) {
      return;
    }
    setError(null);
    setFieldError(null);
    setSuccess(null);
    if (temporaryPassword !== confirmation) {
      setFieldError("Паролі не збігаються.");
      return;
    }
    setIsSaving(true);
    const result = await apiClient
      .POST("/api/v1/users/{user_id}/temporary-password", {
        params: { path: { user_id: selected.user.id } },
        body: {
          temporary_password: temporaryPassword,
          temporary_password_confirmation: confirmation,
        },
        headers: csrfHeaders(),
      })
      .catch(() => null);
    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(result.error.message);
      setFieldError(
        result.error.fields.temporary_password?.[0]
          ?? result.error.fields.temporary_password_confirmation?.[0]
          ?? null,
      );
    } else {
      setRequests((current) => current.filter((item) => item.id !== selected.id));
      setSuccess(`Тимчасовий пароль для ${selected.user.display_name} встановлено. Усі попередні сесії відкликано.`);
      setSelected(null);
      setTemporaryPassword("");
      setConfirmation("");
    }
    setIsSaving(false);
  };

  return (
    <>
      <header className="page-heading reset-queue-heading">
        <div>
          <p className="eyebrow">Безпека · TP-202</p>
          <h1>Запити на відновлення доступу</h1>
          <p>Перевірте працівника поза системою, а потім задайте тимчасовий пароль. CRM не надсилає пароль автоматично.</p>
        </div>
        <button className="button button--secondary" disabled={isLoading} onClick={() => void loadRequests()} type="button"><Icon name="refresh" />Оновити</button>
      </header>

      {error === null ? null : <div className="form-message form-message--error page-message" role="alert"><Icon name="warning" /><span>{error}</span></div>}
      {success === null ? null : <div className="form-message form-message--success page-message" role="status"><Icon name="lock" /><span>{success}</span></div>}

      <section className="reset-queue-layout" aria-label="Черга відновлення паролів">
        <div className="panel reset-request-list">
          <header><div><h2>Очікують перевірки</h2><p>Лише активні облікові записи</p></div><span>{requests.length}</span></header>
          {isLoading ? <div className="queue-state"><span className="spinner" /><p>Завантажуємо запити…</p></div> : null}
          {!isLoading && requests.length === 0 ? (
            <div className="queue-state"><Icon name="lock" /><h3>Нових запитів немає</h3><p>Черга оновиться, коли працівник скористається дією «Забули пароль?».</p></div>
          ) : null}
          {!isLoading ? requests.map((request) => (
            <button
              className={`reset-request-row${selected?.id === request.id ? " reset-request-row--selected" : ""}`}
              key={request.id}
              onClick={() => {
                setSelected(request);
                setTemporaryPassword("");
                setConfirmation("");
                setFieldError(null);
                setSuccess(null);
              }}
              type="button"
            >
              <span className="avatar" aria-hidden="true">{request.user.display_name.split(/\s+/).map((part) => part[0]).join("").slice(0, 2)}</span>
              <span><strong>{request.user.display_name}</strong><small>{request.user.email}</small><small>{roleLabels[request.user.role]} · {formatRequestedAt(request.requested_at)}</small></span>
              <Icon name="chevron" />
            </button>
          )) : null}
        </div>

        <aside className="panel reset-request-detail">
          {selected === null ? (
            <div className="queue-state"><Icon name="arrow-left" /><h3>Оберіть запит</h3><p>Після перевірки працівника тут можна встановити тимчасовий пароль.</p></div>
          ) : (
            <form onSubmit={(event) => void submit(event)}>
              <p className="eyebrow">Тимчасовий доступ</p>
              <h2>{selected.user.display_name}</h2>
              <p>{selected.user.email} · {roleLabels[selected.user.role]}</p>
              <div className="security-note"><Icon name="lock" /><span>Строк дії тимчасового пароля обмежений політикою безпеки. Під час наступного входу працівник обов’язково створить власний пароль.</span></div>
              <label className="form-field"><span>Тимчасовий пароль</span><input aria-invalid={fieldError === null ? undefined : true} autoComplete="new-password" minLength={8} onChange={(event) => { setTemporaryPassword(event.target.value); }} required type="password" value={temporaryPassword} /></label>
              <label className="form-field"><span>Повторіть тимчасовий пароль</span><input aria-invalid={fieldError === null ? undefined : true} autoComplete="new-password" minLength={8} onChange={(event) => { setConfirmation(event.target.value); }} required type="password" value={confirmation} /></label>
              {fieldError === null ? null : <p className="field-error" role="alert">{fieldError}</p>}
              <div className="modal-actions">
                <button className="button button--secondary" disabled={isSaving} onClick={() => { setSelected(null); }} type="button">Скасувати</button>
                <button className="button button--primary" disabled={isSaving} type="submit">{isSaving ? "Зберігаємо…" : "Встановити пароль"}</button>
              </div>
            </form>
          )}
        </aside>
      </section>
    </>
  );
}
