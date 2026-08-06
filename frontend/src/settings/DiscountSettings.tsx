import { useCallback, useEffect, useMemo, useRef, useState, type SyntheticEvent } from "react";

import { Icon } from "../app/Icon";
import { useModalLifecycle } from "../app/useModalLifecycle";
import {
  createDiscount,
  getLoyaltyPolicy,
  listDiscounts,
  updateDiscount,
  updateLoyaltyPolicy,
  type Discount,
  type DiscountApiError,
  type DiscountStatus,
  type LoyaltyPolicy,
} from "../discounts/discountApi";

type FieldErrors = Readonly<Record<string, readonly string[]>>;
type DiscountEditor =
  | { readonly mode: "create" }
  | { readonly mode: "edit"; readonly discount: Discount };

interface PolicyDraft {
  readonly isActive: boolean;
  readonly everyN: string;
  readonly discountId: string;
}

function fieldMessage(errors: FieldErrors, field: string): string | null {
  return errors[field]?.[0] ?? null;
}

function sortDiscounts(discounts: readonly Discount[]): readonly Discount[] {
  return [...discounts].sort((left, right) => (
    Number(right.is_active) - Number(left.is_active)
    || left.name.localeCompare(right.name, "uk")
  ));
}

function policyDraft(policy: LoyaltyPolicy): PolicyDraft {
  return {
    isActive: policy.is_active,
    everyN: String(policy.every_n),
    discountId: policy.discount?.id ?? "",
  };
}

function errorMessage(error: DiscountApiError): string {
  if (error.code === "stale_version") {
    return "Дані вже змінено в іншій сесії. Оновіть каталог і повторіть дію.";
  }
  return error.message;
}

function DiscountEditorDialog({
  editor,
  onClose,
  onConflict,
  onSaved,
}: Readonly<{
  editor: DiscountEditor;
  onClose: () => void;
  onConflict: () => void;
  onSaved: (discount: Discount, message: string) => void;
}>) {
  const isCreate = editor.mode === "create";
  const [name, setName] = useState(editor.mode === "edit" ? editor.discount.name : "");
  const [percent, setPercent] = useState(
    editor.mode === "edit" ? String(editor.discount.percent) : "",
  );
  const [isActive, setIsActive] = useState(
    editor.mode === "edit" ? editor.discount.is_active : true,
  );
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<DiscountApiError | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const dialogRef = useRef<HTMLDivElement>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);

  useModalLifecycle({
    dialogRef,
    initialFocusRef: nameInputRef,
    onEscape: () => { if (!isSaving) onClose(); },
  });

  const submit = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    const parsedPercent = Number(percent);
    if (!Number.isInteger(parsedPercent) || parsedPercent < 1 || parsedPercent > 99) {
      setFieldErrors({ percent: ["Укажіть цілий відсоток від 1 до 99."] });
      return;
    }
    setIsSaving(true);
    setError(null);
    setFieldErrors({});
    try {
      const result = editor.mode === "create"
        ? await createDiscount({ name: name.trim(), percent: parsedPercent, is_active: isActive })
        : await updateDiscount(editor.discount.id, {
            name: name.trim(),
            percent: parsedPercent,
            is_active: isActive,
            version: editor.discount.version,
          });
      if (!result.ok) {
        setError(result.error);
        setFieldErrors(result.error.fields);
        return;
      }
      const stateChanged = editor.mode === "edit"
        && editor.discount.is_active !== result.data.is_active;
      const message = stateChanged
        ? result.data.is_active
          ? `Знижку «${result.data.name}» активовано.`
          : `Знижку «${result.data.name}» деактивовано.`
        : isCreate
          ? `Знижку «${result.data.name}» створено.`
          : `Знижку «${result.data.name}» оновлено.`;
      onSaved(result.data, message);
    } catch {
      setError({
        code: "network_error",
        correlation_id: "",
        fields: {},
        message: "Немає зв’язку із сервером. Спробуйте ще раз.",
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="modal-layer" role="presentation">
      <div
        aria-labelledby="discount-editor-title"
        aria-modal="true"
        className="modal-card discount-editor"
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        <form onSubmit={(event) => { void submit(event); }}>
        <div className="modal-card__header">
          <div>
            <p className="eyebrow">Каталог знижок · TP-1018</p>
            <h2 id="discount-editor-title">{isCreate ? "Нова знижка" : "Редагувати знижку"}</h2>
          </div>
          <button
            aria-label="Закрити форму знижки"
            className="icon-button"
            disabled={isSaving}
            onClick={onClose}
            type="button"
          ><Icon name="close" /></button>
        </div>

        <p className="modal-intro">
          Відсоток діє на всю суму послуг. Історичні розрахунки зберігають власний snapshot.
        </p>

        {error === null ? null : (
          <div className="form-message form-message--error" role="alert">
            <Icon name="warning" />
            <span>{errorMessage(error)}</span>
            {error.code === "stale_version" ? (
              <button className="text-action" onClick={onConflict} type="button">Оновити каталог</button>
            ) : null}
          </div>
        )}

        <div className="discount-editor__fields">
          <label className="form-field">
            <span>Назва знижки</span>
            <input
              maxLength={120}
              onChange={(event) => { setName(event.target.value); setError(null); }}
              ref={nameInputRef}
              required
              value={name}
            />
            {fieldMessage(fieldErrors, "name") === null ? null : (
              <small className="field-error">{fieldMessage(fieldErrors, "name")}</small>
            )}
          </label>
          <label className="form-field">
            <span>Відсоток</span>
            <span className="discount-percent-input">
              <input
                inputMode="numeric"
                max={99}
                min={1}
                onChange={(event) => { setPercent(event.target.value); setError(null); }}
                required
                type="number"
                value={percent}
              />
              <span aria-hidden="true">%</span>
            </span>
            {fieldMessage(fieldErrors, "percent") === null ? null : (
              <small className="field-error">{fieldMessage(fieldErrors, "percent")}</small>
            )}
          </label>
          <label className="settings-check discount-editor__active">
            <input
              checked={isActive}
              onChange={(event) => { setIsActive(event.target.checked); setError(null); }}
              type="checkbox"
            />
            <span>
              <strong>Активна знижка</strong>
              <small>Доступна подологу під час finish і рецепції під час оплати.</small>
            </span>
          </label>
        </div>

        <div className="modal-actions">
          <button className="button button--secondary" disabled={isSaving} onClick={onClose} type="button">
            Скасувати
          </button>
          <button className="button button--primary" disabled={isSaving} type="submit">
            {isSaving ? "Зберігаємо…" : isCreate ? "Створити знижку" : "Зберегти зміни"}
          </button>
        </div>
        </form>
      </div>
    </div>
  );
}

export function DiscountSettings() {
  const [discounts, setDiscounts] = useState<readonly Discount[]>([]);
  const [policy, setPolicy] = useState<LoyaltyPolicy | null>(null);
  const [draft, setDraft] = useState<PolicyDraft | null>(null);
  const [status, setStatus] = useState<DiscountStatus>("all");
  const [isLoading, setIsLoading] = useState(true);
  const [isSavingPolicy, setIsSavingPolicy] = useState(false);
  const [mutatingDiscountId, setMutatingDiscountId] = useState<string | null>(null);
  const [error, setError] = useState<DiscountApiError | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [policyFieldErrors, setPolicyFieldErrors] = useState<FieldErrors>({});
  const [editor, setEditor] = useState<DiscountEditor | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setIsLoading(true);
    setError(null);
    try {
      const [catalogResult, policyResult] = await Promise.all([
        listDiscounts("all", signal),
        getLoyaltyPolicy(signal),
      ]);
      if (!catalogResult.ok) {
        setError(catalogResult.error);
        return;
      }
      if (!policyResult.ok) {
        setError(policyResult.error);
        return;
      }
      setDiscounts(sortDiscounts(catalogResult.data.discounts));
      setPolicy(policyResult.data);
      setDraft(policyDraft(policyResult.data));
    } catch (reason: unknown) {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setError({
        code: "network_error",
        correlation_id: "",
        fields: {},
        message: "Немає зв’язку із сервером. Спробуйте ще раз.",
      });
    } finally {
      if (signal?.aborted !== true) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => { controller.abort(); };
  }, [load]);

  const replaceDiscount = (discount: Discount, message: string) => {
    setDiscounts((current) => sortDiscounts(
      current.some((item) => item.id === discount.id)
        ? current.map((item) => item.id === discount.id ? discount : item)
        : [...current, discount],
    ));
    setPolicy((current) => current === null || current.discount?.id !== discount.id
      ? current
      : { ...current, discount });
    setEditor(null);
    setError(null);
    setSuccess(message);
  };

  const toggleDiscount = async (discount: Discount) => {
    setMutatingDiscountId(discount.id);
    setError(null);
    setSuccess(null);
    try {
      const result = await updateDiscount(discount.id, {
        is_active: !discount.is_active,
        version: discount.version,
      });
      if (!result.ok) {
        setError(result.error);
        return;
      }
      replaceDiscount(
        result.data,
        result.data.is_active
          ? `Знижку «${result.data.name}» активовано.`
          : `Знижку «${result.data.name}» деактивовано.`,
      );
    } catch {
      setError({
        code: "network_error",
        correlation_id: "",
        fields: {},
        message: "Немає зв’язку із сервером. Спробуйте ще раз.",
      });
    } finally {
      setMutatingDiscountId(null);
    }
  };

  const savePolicy = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    if (policy === null || draft === null) return;
    const everyN = Number(draft.everyN);
    const nextErrors: Record<string, string[]> = {};
    if (!Number.isInteger(everyN) || everyN < 1 || everyN > 10000) {
      nextErrors.every_n = ["Укажіть ціле число від 1 до 10000."];
    }
    if (draft.isActive && !discounts.some((discount) => (
      discount.id === draft.discountId && discount.is_active
    ))) {
      nextErrors.discount_id = ["Для активної програми оберіть активну знижку."];
    }
    if (Object.keys(nextErrors).length > 0) {
      setPolicyFieldErrors(nextErrors);
      return;
    }
    setIsSavingPolicy(true);
    setPolicyFieldErrors({});
    setError(null);
    setSuccess(null);
    try {
      const result = await updateLoyaltyPolicy({
        is_active: draft.isActive,
        every_n: everyN,
        discount_id: draft.discountId === "" ? null : draft.discountId,
        version: policy.version,
      });
      if (!result.ok) {
        setError(result.error);
        setPolicyFieldErrors(result.error.fields);
        return;
      }
      setPolicy(result.data);
      setDraft(policyDraft(result.data));
      setSuccess(result.data.is_active
        ? `Програму лояльності увімкнено: знижка на кожен ${String(result.data.every_n)}-й візит.`
        : "Програму лояльності вимкнено. Накопичений прогрес збережено.");
    } catch {
      setError({
        code: "network_error",
        correlation_id: "",
        fields: {},
        message: "Немає зв’язку із сервером. Спробуйте ще раз.",
      });
    } finally {
      setIsSavingPolicy(false);
    }
  };

  const activeDiscounts = useMemo(
    () => discounts.filter((discount) => discount.is_active),
    [discounts],
  );
  const visibleDiscounts = useMemo(
    () => discounts.filter((discount) => (
      status === "all" || (status === "active" ? discount.is_active : !discount.is_active)
    )),
    [discounts, status],
  );
  const isPolicyDirty = policy !== null && draft !== null && (
    policy.is_active !== draft.isActive
    || String(policy.every_n) !== draft.everyN
    || (policy.discount?.id ?? "") !== draft.discountId
  );

  if (isLoading) {
    return (
      <section aria-label="Знижки" className="panel settings-state" role="status">
        <span className="spinner" />
        <p>Завантажуємо каталог знижок і програму лояльності…</p>
      </section>
    );
  }

  if (error !== null && policy === null) {
    return (
      <section className="panel settings-state discount-settings__fatal" role="alert">
        <Icon name="warning" />
        <h2>Не вдалося завантажити знижки</h2>
        <p>{errorMessage(error)}</p>
        <button className="button button--secondary" onClick={() => { void load(); }} type="button">
          <Icon name="refresh" />Повторити
        </button>
      </section>
    );
  }

  return (
    <div className="discount-settings">
      {error === null ? null : (
        <div className="form-message form-message--error page-message" role="alert">
          <Icon name="warning" />
          <span>{errorMessage(error)}</span>
          {error.code === "stale_version" || error.code === "discount_used_by_active_loyalty" ? (
            <button className="text-action" onClick={() => { void load(); }} type="button">Оновити дані</button>
          ) : null}
        </div>
      )}
      {success === null ? null : (
        <div className="form-message form-message--success page-message" role="status">
          <Icon name="check" /><span>{success}</span>
        </div>
      )}

      <section className="panel discount-catalog" aria-labelledby="discount-catalog-title">
        <header>
          <div>
            <p className="eyebrow">Каталог · TP-1018</p>
            <h2 id="discount-catalog-title">Знижки</h2>
            <p>Одна активна знижка може бути застосована до всього прийому. Знижки не сумуються.</p>
          </div>
          <button
            className="button button--primary"
            onClick={() => { setEditor({ mode: "create" }); setSuccess(null); }}
            type="button"
          ><Icon name="plus" />Додати знижку</button>
        </header>

        <div className="discount-catalog__summary">
          <span><strong>{discounts.length}</strong> усього</span>
          <span><strong>{activeDiscounts.length}</strong> активних</span>
          <span><strong>{discounts.length - activeDiscounts.length}</strong> неактивних</span>
        </div>

        <div aria-label="Фільтр статусу знижок" className="discount-filter" role="group">
          {(["all", "active", "inactive"] as const).map((value) => (
            <button
              aria-pressed={status === value}
              className={status === value ? "active" : undefined}
              key={value}
              onClick={() => { setStatus(value); }}
              type="button"
            >{value === "all" ? "Усі" : value === "active" ? "Активні" : "Неактивні"}</button>
          ))}
        </div>

        {visibleDiscounts.length === 0 ? (
          <div className="settings-state discount-catalog__empty">
            <Icon name="empty" />
            <h3>{discounts.length === 0 ? "Знижок ще немає" : "У цьому статусі знижок немає"}</h3>
            <p>{discounts.length === 0
              ? "Створіть першу знижку, щоб вона з’явилася у виборі під час прийому."
              : "Оберіть інший статус каталогу."}</p>
            {discounts.length === 0 ? (
              <button className="button button--primary" onClick={() => { setEditor({ mode: "create" }); }} type="button">
                Створити знижку
              </button>
            ) : null}
          </div>
        ) : (
          <div className="discount-list">
            {visibleDiscounts.map((discount) => (
              <article className={discount.is_active ? "discount-row" : "discount-row discount-row--inactive"} key={discount.id}>
                <div className="discount-row__value" aria-label={`${String(discount.percent)} відсотків`}>
                  <strong>{discount.percent}</strong><span>%</span>
                </div>
                <div className="discount-row__identity">
                  <strong>{discount.name}</strong>
                  <small>Версія {discount.version} · історичні snapshots незмінні</small>
                </div>
                <span className={`profile-status profile-status--${discount.is_active ? "active" : "inactive"}`}>
                  <span />{discount.is_active ? "Активна" : "Неактивна"}
                </span>
                <div className="discount-row__actions">
                  <button
                    className="button button--secondary"
                    onClick={() => { setEditor({ mode: "edit", discount }); setSuccess(null); }}
                    type="button"
                  >Редагувати</button>
                  <button
                    className={discount.is_active ? "button button--danger-ghost" : "button button--secondary"}
                    disabled={mutatingDiscountId !== null}
                    onClick={() => { void toggleDiscount(discount); }}
                    type="button"
                  >{mutatingDiscountId === discount.id
                    ? "Зберігаємо…"
                    : discount.is_active ? "Деактивувати" : "Активувати"}</button>
                </div>
              </article>
            ))}
          </div>
        )}

        <footer className="rooms-history-note">
          <Icon name="lock" />
          <span><strong>Без фізичного видалення</strong><small>Деактивація прибирає знижку з нових розрахунків, але не змінює історію.</small></span>
        </footer>
      </section>

      {policy === null || draft === null ? null : (
        <form className="panel loyalty-policy" onSubmit={(event) => { void savePolicy(event); }}>
          <div className="loyalty-policy__header">
            <div>
              <p className="eyebrow">Постійні клієнти · TP-1019</p>
              <h2>Програма лояльності</h2>
              <p>Автоматична знижка на кожен N-й новий завершений візит. Старі візити не враховуються.</p>
            </div>
            <span className={`profile-status profile-status--${policy.is_active ? "active" : "inactive"}`}>
              <span />{policy.is_active ? "Увімкнено" : "Вимкнено"}
            </span>
          </div>

          <div className="loyalty-policy__fields">
            <label className="settings-check loyalty-policy__toggle">
              <input
                checked={draft.isActive}
                disabled={isSavingPolicy}
                onChange={(event) => {
                  setDraft((current) => current === null ? current : { ...current, isActive: event.target.checked });
                  setError(null);
                }}
                type="checkbox"
              />
              <span><strong>Програма активна</strong><small>Під час паузи нові завершені візити не збільшують лічильник.</small></span>
            </label>
            <label className="form-field">
              <span>Кожен N-й візит</span>
              <input
                disabled={isSavingPolicy}
                inputMode="numeric"
                max={10000}
                min={1}
                onChange={(event) => {
                  setDraft((current) => current === null ? current : { ...current, everyN: event.target.value });
                  setPolicyFieldErrors({});
                }}
                required
                type="number"
                value={draft.everyN}
              />
              {fieldMessage(policyFieldErrors, "every_n") === null ? null : (
                <small className="field-error">{fieldMessage(policyFieldErrors, "every_n")}</small>
              )}
            </label>
            <label className="form-field loyalty-policy__discount">
              <span>Знижка для N-го візиту</span>
              <select
                disabled={isSavingPolicy}
                onChange={(event) => {
                  setDraft((current) => current === null ? current : { ...current, discountId: event.target.value });
                  setPolicyFieldErrors({});
                }}
                required={draft.isActive}
                value={draft.discountId}
              >
                <option value="">Не обрано</option>
                {activeDiscounts.map((discount) => (
                  <option key={discount.id} value={discount.id}>{discount.name} · {discount.percent}%</option>
                ))}
                {policy.discount !== null && !policy.discount.is_active ? (
                  <option disabled value={policy.discount.id}>{policy.discount.name} · неактивна</option>
                ) : null}
              </select>
              {fieldMessage(policyFieldErrors, "discount_id") === null ? null : (
                <small className="field-error">{fieldMessage(policyFieldErrors, "discount_id")}</small>
              )}
              {activeDiscounts.length === 0 ? <small>Спочатку створіть або активуйте знижку.</small> : null}
            </label>
          </div>

          <div className="loyalty-policy__rule" role="status">
            <Icon name="settings" />
            <span>
              <strong>{draft.isActive
                ? `Знижка спрацює на кожен ${draft.everyN || "N"}-й врахований візит.`
                : "Програма на паузі."}</strong>
              <small>Зміна N або відсотка не скидає прогрес; бонус не переноситься після ручної заміни.</small>
            </span>
          </div>

          <footer>
            <span>{isPolicyDirty ? "Є незбережені зміни" : `Версія налаштувань: ${String(policy.version)}`}</span>
            <button
              className="button button--primary"
              disabled={!isPolicyDirty || isSavingPolicy || (draft.isActive && !activeDiscounts.some((discount) => discount.id === draft.discountId))}
              type="submit"
            >{isSavingPolicy ? "Зберігаємо…" : "Зберегти програму"}</button>
          </footer>
        </form>
      )}

      {editor === null ? null : (
        <DiscountEditorDialog
          editor={editor}
          onClose={() => { setEditor(null); }}
          onConflict={() => { setEditor(null); void load(); }}
          onSaved={replaceDiscount}
        />
      )}
    </div>
  );
}
