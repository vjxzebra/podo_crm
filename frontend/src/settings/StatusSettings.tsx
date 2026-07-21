import { useEffect, useMemo, useState, type SyntheticEvent } from "react";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders } from "../auth/AuthContext";

type StatusConfig = components["schemas"]["AppointmentStatusConfig"];
type FieldErrors = Readonly<Record<string, readonly string[]>>;

const statusOrder = [
  "NEW",
  "PENDING_CONFIRMATION",
  "CONFIRMED",
  "ARRIVED",
  "IN_PROGRESS",
  "COMPLETED",
  "CANCELED",
  "NO_SHOW",
] as const;

const roleLabels = {
  manual_admin: "Адміністратор",
  manual_reception: "Рецепція",
  manual_podologist: "Подолог",
} as const;

function StatusEditor({
  status,
  onClose,
  onSaved,
}: {
  readonly status: StatusConfig;
  readonly onClose: () => void;
  readonly onSaved: (status: StatusConfig) => void;
}) {
  const [label, setLabel] = useState(status.label);
  const [color, setColor] = useState(status.color);
  const [manualAdmin, setManualAdmin] = useState(status.manual_admin ?? true);
  const [manualReception, setManualReception] = useState(status.manual_reception ?? false);
  const [manualPodologist, setManualPodologist] = useState(status.manual_podologist ?? false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const isDirty = label !== status.label
    || color.toUpperCase() !== status.color
    || manualAdmin !== status.manual_admin
    || manualReception !== status.manual_reception
    || manualPodologist !== status.manual_podologist;

  const submit = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    setFieldErrors({});
    const result = await apiClient.PATCH("/api/v1/appointment-status-configs/{code}", {
      params: { path: { code: status.code } },
      body: {
        label,
        color: color.toUpperCase(),
        manual_admin: manualAdmin,
        manual_reception: manualReception,
        manual_podologist: manualPodologist,
        version: status.version ?? 1,
      },
      headers: csrfHeaders(),
    }).catch(() => null);
    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(result.error.message);
      setFieldErrors(result.error.fields);
    } else {
      onSaved(result.data);
    }
    setIsSaving(false);
  };

  return (
    <div className="modal-layer" role="dialog" aria-modal="true" aria-labelledby="status-editor-title">
      <form className="modal-card status-editor" onSubmit={(event) => void submit(event)}>
        <header className="modal-card__header">
          <div><p className="eyebrow">Системний код · {status.code}</p><h2 id="status-editor-title">Налаштувати статус</h2></div>
          <button className="icon-button" onClick={onClose} type="button" aria-label="Закрити форму статусу"><Icon name="close" /></button>
        </header>
        <p className="modal-intro">Код і сам статус захищені від перейменування та видалення. Змінюються лише назва, колір і ролі для ручного встановлення.</p>
        {error === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div>}
        <div className="status-editor__identity">
          <label className="form-field"><span>Зрозуміла назва</span><input autoFocus maxLength={80} onChange={(event) => { setLabel(event.target.value); }} required value={label} />{fieldErrors.label?.[0] === undefined ? null : <small className="field-error">{fieldErrors.label[0]}</small>}</label>
          <label className="form-field status-color-field"><span>Колір статусу</span><span><input onChange={(event) => { setColor(event.target.value.toUpperCase()); }} type="color" value={color} /><code>{color.toUpperCase()}</code></span>{fieldErrors.color?.[0] === undefined ? null : <small className="field-error">{fieldErrors.color[0]}</small>}</label>
        </div>
        <fieldset className="status-role-fieldset">
          <legend>Хто може встановлювати вручну</legend>
          <label className="settings-check"><input checked={manualAdmin} onChange={(event) => { setManualAdmin(event.target.checked); }} type="checkbox" /><span><strong>Адміністратор</strong><small>Повне керування записом.</small></span></label>
          <label className="settings-check"><input checked={manualReception} onChange={(event) => { setManualReception(event.target.checked); }} type="checkbox" /><span><strong>Рецепція</strong><small>Операційна робота з календарем.</small></span></label>
          <label className="settings-check"><input checked={manualPodologist} onChange={(event) => { setManualPodologist(event.target.checked); }} type="checkbox" /><span><strong>Подолог</strong><small>Лише власні дозволені записи.</small></span></label>
        </fieldset>
        {isDirty ? <p className="unsaved-note" role="status"><Icon name="warning" />Є незбережені зміни.</p> : null}
        <div className="modal-actions"><button className="button button--secondary" disabled={isSaving} onClick={onClose} type="button">Скасувати</button><button className="button button--primary" disabled={isSaving || !isDirty} type="submit">{isSaving ? "Зберігаємо…" : "Зберегти статус"}</button></div>
      </form>
    </div>
  );
}

export function StatusSettings() {
  const [statuses, setStatuses] = useState<readonly StatusConfig[] | null>(null);
  const [editor, setEditor] = useState<StatusConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    const result = await apiClient.GET("/api/v1/appointment-status-configs").catch(() => null);
    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(result.error.message);
    } else {
      setStatuses(result.data.statuses);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const orderedStatuses = useMemo(() => statuses === null ? [] : [...statuses].sort(
    (left, right) => statusOrder.indexOf(left.code as typeof statusOrder[number]) - statusOrder.indexOf(right.code as typeof statusOrder[number]),
  ), [statuses]);

  const saved = (updated: StatusConfig) => {
    setStatuses((current) => current?.map((item) => item.code === updated.code ? updated : item) ?? [updated]);
    setEditor(null);
    setError(null);
    setSuccess(`Статус «${updated.label}» збережено.`);
  };

  return (
    <section className="panel statuses-panel">
      <header><div><p className="eyebrow">Workflow запису</p><h2>Системні статуси</h2><p>Вісім незмінних кодів зі специфікації §6.9. Назви й кольори використовуватимуться в календарі та історії.</p></div><span className="protected-count"><Icon name="lock" />8 захищених</span></header>
      {error === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span><button className="text-action" onClick={() => void load()} type="button">Повторити</button></div>}
      {success === null ? null : <div className="form-message form-message--success" role="status"><Icon name="settings" /><span>{success}</span></div>}
      {statuses === null && error === null ? <div className="settings-state"><span className="spinner" /><p>Завантажуємо системні статуси…</p></div> : null}
      {statuses !== null ? <div className="status-grid">{orderedStatuses.map((status, index) => {
        const enabledRoles = (Object.keys(roleLabels) as (keyof typeof roleLabels)[]).filter((role) => status[role]);
        return <article className="status-card" key={status.code}><span className="status-sequence">{String(index + 1).padStart(2, "0")}</span><span className="status-swatch" style={{ backgroundColor: status.color }} /><div className="status-card__copy"><strong>{status.label}</strong><code>{status.code}</code><span>{enabledRoles.length === 0 ? "Ручна зміна вимкнена" : enabledRoles.map((role) => roleLabels[role]).join(" · ")}</span></div><button className="button button--secondary" onClick={() => { setEditor(status); setSuccess(null); }} type="button" aria-label={`Налаштувати ${status.label}`}>Налаштувати</button></article>;
      })}</div> : null}
      <footer className="rooms-history-note"><Icon name="lock" /><span><strong>Системний workflow захищено</strong><small>API не має create/delete і не приймає code у mutation; PostgreSQL trigger блокує update коду та видалення рядка.</small></span></footer>
      {editor === null ? null : <StatusEditor onClose={() => { setEditor(null); }} onSaved={saved} status={editor} />}
    </section>
  );
}
