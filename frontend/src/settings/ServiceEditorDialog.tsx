import { useState, type SyntheticEvent } from "react";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders } from "../auth/AuthContext";

type Service = components["schemas"]["Service"];
type FieldErrors = Readonly<Record<string, readonly string[]>>;

export type ServiceEditor =
  | { readonly mode: "create" }
  | { readonly mode: "edit"; readonly service: Service };

const SERVICE_COLORS = [
  { value: "#0F766E", label: "Бірюзовий" },
  { value: "#2563EB", label: "Синій" },
  { value: "#7C3AED", label: "Фіолетовий" },
  { value: "#DB2777", label: "Рожевий" },
  { value: "#EA580C", label: "Помаранчевий" },
  { value: "#CA8A04", label: "Жовтий" },
  { value: "#16A34A", label: "Зелений" },
  { value: "#475569", label: "Графітовий" },
] as const;

function fieldMessage(errors: FieldErrors, field: string): string | null {
  return errors[field]?.[0] ?? null;
}

function priceDraft(priceMinor: number): string {
  return (priceMinor / 100).toFixed(2).replace(".", ",");
}

function priceMinor(value: string): number | null {
  const normalized = value.replaceAll(" ", "").replace(",", ".");
  if (!/^\d+(?:\.\d{1,2})?$/.test(normalized)) {
    return null;
  }
  const parsed = Number(normalized);
  return Number.isSafeInteger(Math.round(parsed * 100)) ? Math.round(parsed * 100) : null;
}

export function ServiceEditorDialog({
  editor,
  onClose,
  onSaved,
}: {
  readonly editor: ServiceEditor;
  readonly onClose: () => void;
  readonly onSaved: (service: Service, message: string) => void;
}) {
  const isCreate = editor.mode === "create";
  const current = editor.mode === "edit" ? editor.service : null;
  const [code, setCode] = useState(current?.code ?? "");
  const [name, setName] = useState(current?.name ?? "");
  const [duration, setDuration] = useState(String(current?.duration_minutes ?? 45));
  const [price, setPrice] = useState(priceDraft(current?.price_minor ?? 0));
  const [color, setColor] = useState(current?.color ?? SERVICE_COLORS[0].value);
  const [isActive, setIsActive] = useState(current?.is_active ?? true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const submit = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    const parsedPrice = priceMinor(price);
    const parsedDuration = Number(duration);
    if (parsedPrice === null) {
      setFieldErrors({ price_minor: ["Укажіть суму у гривнях із не більш ніж двома знаками після коми."] });
      return;
    }
    if (!Number.isInteger(parsedDuration) || parsedDuration < 1) {
      setFieldErrors({ duration_minutes: ["Тривалість має бути додатною кількістю хвилин."] });
      return;
    }

    setIsSaving(true);
    setError(null);
    setFieldErrors({});
    const body = {
      code,
      name,
      duration_minutes: parsedDuration,
      price_minor: parsedPrice,
      color,
      is_active: isActive,
    };
    const result = editor.mode === "create"
      ? await apiClient.POST("/api/v1/services", {
          body,
          headers: csrfHeaders(),
        }).catch(() => null)
      : await apiClient.PATCH("/api/v1/services/{service_id}", {
          params: { path: { service_id: editor.service.id } },
          body: { ...body, version: editor.service.version ?? 1 },
          headers: csrfHeaders(),
        }).catch(() => null);

    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(result.error.message);
      setFieldErrors(result.error.fields);
    } else {
      const changedActiveState = current !== null && current.is_active !== result.data.is_active;
      const message = changedActiveState
        ? result.data.is_active
          ? `Послугу «${result.data.name}» активовано.`
          : `Послугу «${result.data.name}» деактивовано.`
        : isCreate
          ? `Послугу «${result.data.name}» створено.`
          : `Послугу «${result.data.name}» оновлено.`;
      onSaved(result.data, message);
    }
    setIsSaving(false);
  };

  const deactivating = current?.is_active === true && !isActive;

  return (
    <div className="modal-layer" role="dialog" aria-modal="true" aria-labelledby="service-editor-title">
      <form className="modal-card service-editor" onSubmit={(event) => void submit(event)}>
        <header className="modal-card__header">
          <div>
            <p className="eyebrow">Каталог · TP-205</p>
            <h2 id="service-editor-title">{isCreate ? "Нова послуга" : "Редагувати послугу"}</h2>
          </div>
          <button className="icon-button" onClick={onClose} type="button" aria-label="Закрити форму послуги"><Icon name="close" /></button>
        </header>
        <p className="modal-intro">Ціна зберігається в копійках, тривалість — у хвилинах. Колір буде використано в календарі.</p>

        {error === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div>}

        <div className="service-editor__grid">
          <label className="form-field"><span>Код послуги</span><input autoFocus autoCapitalize="characters" maxLength={32} onChange={(event) => { setCode(event.target.value.toUpperCase()); }} placeholder="NAIL-CARE" required value={code} />{fieldMessage(fieldErrors, "code") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "code")}</small>}</label>
          <label className="form-field"><span>Назва</span><input maxLength={160} onChange={(event) => { setName(event.target.value); }} required value={name} />{fieldMessage(fieldErrors, "name") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "name")}</small>}</label>
          <label className="form-field"><span>Тривалість, хв</span><input inputMode="numeric" min={1} max={1440} onChange={(event) => { setDuration(event.target.value); }} required type="number" value={duration} />{fieldMessage(fieldErrors, "duration_minutes") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "duration_minutes")}</small>}</label>
          <label className="form-field"><span>Ціна, ₴</span><input inputMode="decimal" onChange={(event) => { setPrice(event.target.value); }} placeholder="0,00" required value={price} />{fieldMessage(fieldErrors, "price_minor") === null ? null : <small className="field-error">{fieldMessage(fieldErrors, "price_minor")}</small>}</label>
        </div>

        <fieldset className="service-palette">
          <legend>Колір у календарі</legend>
          <div>{SERVICE_COLORS.map((option) => <label key={option.value} title={option.label}><input checked={color === option.value} name="service-color" onChange={() => { setColor(option.value); }} type="radio" value={option.value} /><span style={{ backgroundColor: option.value }} /><small>{option.label}</small></label>)}</div>
        </fieldset>

        <label className="settings-check"><input checked={isActive} onChange={(event) => { setIsActive(event.target.checked); }} type="checkbox" /><span><strong>Активна послуга</strong><small>Доступна для вибору в нових записах і візитах.</small></span></label>
        {deactivating ? <div className="room-warning"><Icon name="warning" /><span><strong>Послуга зникне з нових записів.</strong><small>Історичні візити та їхні snapshot-дані залишаться без змін.</small></span></div> : null}

        <div className="modal-actions"><button className="button button--secondary" disabled={isSaving} onClick={onClose} type="button">Скасувати</button><button className={`button ${deactivating ? "button--danger" : "button--primary"}`} disabled={isSaving} type="submit">{isSaving ? "Зберігаємо…" : isCreate ? "Створити послугу" : "Зберегти зміни"}</button></div>
      </form>
    </div>
  );
}
