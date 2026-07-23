import { useCallback, useEffect, useMemo, useRef, useState, type SyntheticEvent } from "react";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { useModalLifecycle } from "../app/useModalLifecycle";
import { csrfHeaders } from "../auth/AuthContext";

export type Supplier = components["schemas"]["Supplier"];
type ErrorFields = Readonly<Record<string, readonly string[]>>;
type SupplierStatus = "all" | "active" | "inactive";
type EditorState =
  | { readonly mode: "create" }
  | { readonly mode: "edit"; readonly supplier: Supplier };

interface SupplierForm {
  readonly name: string;
  readonly contactName: string;
  readonly phone: string;
  readonly email: string;
  readonly address: string;
  readonly note: string;
  readonly isActive: boolean;
}

function initialForm(editor: EditorState): SupplierForm {
  const supplier = editor.mode === "edit" ? editor.supplier : undefined;
  return {
    name: supplier?.name ?? "",
    contactName: supplier?.contact_name ?? "",
    phone: supplier?.phone ?? "",
    email: supplier?.email ?? "",
    address: supplier?.address ?? "",
    note: supplier?.note ?? "",
    isActive: supplier?.is_active ?? true,
  };
}

function fieldMessage(fields: ErrorFields, field: string): string | null {
  return fields[field]?.[0] ?? null;
}

function supplierInitials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toLocaleUpperCase("uk");
}

function displayOr(value: string | undefined, fallback: string): string {
  return value === undefined || value.trim() === "" ? fallback : value;
}

function SupplierEditorDialog({
  editor,
  onClose,
  onSaved,
}: {
  readonly editor: EditorState;
  readonly onClose: () => void;
  readonly onSaved: (supplier: Supplier, message: string) => void;
}) {
  const initial = useRef(initialForm(editor));
  const [form, setForm] = useState<SupplierForm>(initial.current);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<ErrorFields>({});
  const [confirmClose, setConfirmClose] = useState(false);
  const dialogRef = useRef<HTMLElement>(null);
  const firstInputRef = useRef<HTMLInputElement>(null);
  const isDirty = JSON.stringify(form) !== JSON.stringify(initial.current);

  const requestClose = useCallback(() => {
    if (isSaving) return;
    if (isDirty) {
      setConfirmClose(true);
      return;
    }
    onClose();
  }, [isDirty, isSaving, onClose]);

  useModalLifecycle({ dialogRef, initialFocusRef: firstInputRef, onEscape: requestClose });

  const update = <Key extends keyof SupplierForm>(key: Key, value: SupplierForm[Key]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setError(null);
    setFields({});
    setConfirmClose(false);
  };

  const submit = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    setFields({});
    const body = {
      name: form.name,
      contact_name: form.contactName,
      phone: form.phone,
      email: form.email,
      address: form.address,
      note: form.note,
      is_active: form.isActive,
    };
    const result = editor.mode === "create"
      ? await apiClient.POST("/api/v1/inventory/suppliers", {
        body,
        headers: csrfHeaders(),
      }).catch(() => null)
      : await apiClient.PATCH("/api/v1/inventory/suppliers/{supplier_id}", {
        params: { path: { supplier_id: editor.supplier.id } },
        body: { ...body, version: editor.supplier.version ?? 1 },
        headers: csrfHeaders(),
      }).catch(() => null);
    setIsSaving(false);
    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(result.error.message);
      setFields(result.error.fields);
    } else {
      onSaved(
        result.data,
        editor.mode === "create"
          ? "Постачальника додано до довідника."
          : result.data.is_active
            ? "Картку постачальника оновлено."
            : "Постачальника деактивовано; історичні партії не змінено.",
      );
    }
  };

  return (
    <div className="modal-layer" onMouseDown={(event) => { if (event.currentTarget === event.target) requestClose(); }} role="presentation">
      <section aria-labelledby="supplier-editor-title" aria-modal="true" className="modal-card supplier-editor" ref={dialogRef} role="dialog" tabIndex={-1}>
        <header className="modal-card__header">
          <div><p className="eyebrow">Склад · TP-1001</p><h2 id="supplier-editor-title">{editor.mode === "create" ? "Новий постачальник" : "Редагувати постачальника"}</h2><p>Деактивація прибирає запис із нових надходжень, але зберігає історію партій.</p></div>
          <button aria-label="Закрити постачальника" className="icon-button" disabled={isSaving} onClick={requestClose} type="button"><Icon name="close" /></button>
        </header>
        <form onSubmit={(event) => void submit(event)}>
          <div className="supplier-editor__body">
            {error === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div>}
            <div className="supplier-editor__grid">
              <label className="form-field supplier-editor__wide"><span>Назва</span><input maxLength={180} onChange={(event) => { update("name", event.target.value); }} ref={firstInputRef} required value={form.name} />{fieldMessage(fields, "name") === null ? null : <small className="field-error">{fieldMessage(fields, "name")}</small>}</label>
              <label className="form-field"><span>Контактна особа</span><input maxLength={180} onChange={(event) => { update("contactName", event.target.value); }} value={form.contactName} />{fieldMessage(fields, "contact_name") === null ? null : <small className="field-error">{fieldMessage(fields, "contact_name")}</small>}</label>
              <label className="form-field"><span>Телефон</span><input autoComplete="tel" maxLength={32} onChange={(event) => { update("phone", event.target.value); }} value={form.phone} />{fieldMessage(fields, "phone") === null ? null : <small className="field-error">{fieldMessage(fields, "phone")}</small>}</label>
              <label className="form-field"><span>Email</span><input autoComplete="email" onChange={(event) => { update("email", event.target.value); }} type="email" value={form.email} />{fieldMessage(fields, "email") === null ? null : <small className="field-error">{fieldMessage(fields, "email")}</small>}</label>
              <label className="form-field supplier-editor__wide"><span>Адреса</span><input maxLength={300} onChange={(event) => { update("address", event.target.value); }} value={form.address} />{fieldMessage(fields, "address") === null ? null : <small className="field-error">{fieldMessage(fields, "address")}</small>}</label>
              <label className="form-field supplier-editor__wide"><span>Примітка</span><textarea maxLength={2000} onChange={(event) => { update("note", event.target.value); }} rows={3} value={form.note} />{fieldMessage(fields, "note") === null ? null : <small className="field-error">{fieldMessage(fields, "note")}</small>}</label>
              <label className="toggle-field supplier-editor__wide"><input checked={form.isActive} onChange={(event) => { update("isActive", event.target.checked); }} type="checkbox" /><span /><strong>Активний постачальник</strong><small>Лише активні записи доступні у формі нового надходження.</small></label>
            </div>
            {confirmClose ? <div className="patient-close-warning" role="alert"><span><strong>Є незбережені зміни</strong><small>Відкинути їх і закрити форму?</small></span><div><button className="button button--secondary" onClick={() => { setConfirmClose(false); }} type="button">Продовжити</button><button className="button button--danger" onClick={onClose} type="button">Відкинути</button></div></div> : null}
          </div>
          <footer className="modal-card__footer"><button className="button button--secondary" disabled={isSaving} onClick={requestClose} type="button">Скасувати</button><button className="button button--primary" disabled={isSaving} type="submit">{isSaving ? "Зберігаємо…" : editor.mode === "create" ? "Створити постачальника" : "Зберегти зміни"}</button></footer>
        </form>
      </section>
    </div>
  );
}

export function InventorySuppliers() {
  const [suppliers, setSuppliers] = useState<readonly Supplier[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<SupplierStatus>("all");
  const [editor, setEditor] = useState<EditorState | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const result = await apiClient.GET("/api/v1/inventory/suppliers").catch(() => null);
    if (result === null) setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    else if (result.data === undefined) setError(result.error.message);
    else setSuppliers(result.data.suppliers);
    setIsLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  const visible = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("uk");
    return suppliers.filter((supplier) => {
      const matchesStatus = status === "all" || supplier.is_active === (status === "active");
      const haystack = [supplier.name, supplier.contact_name, supplier.phone, supplier.email]
        .filter((item): item is string => typeof item === "string")
        .join(" ")
        .toLocaleLowerCase("uk");
      return matchesStatus && (term === "" || haystack.includes(term));
    });
  }, [search, status, suppliers]);

  const saved = (supplier: Supplier, message: string) => {
    setSuppliers((current) => {
      const found = current.some((item) => item.id === supplier.id);
      const next = found
        ? current.map((item) => item.id === supplier.id ? supplier : item)
        : [...current, supplier];
      return [...next].sort((left, right) => Number(right.is_active) - Number(left.is_active) || left.name.localeCompare(right.name, "uk"));
    });
    setEditor(null);
    setSuccess(message);
    setError(null);
  };

  const filtersActive = search !== "" || status !== "all";

  return (
    <>
      {error === null ? null : <div className="form-message form-message--error page-message" role="alert"><Icon name="warning" /><span>{error}</span><button className="text-action" onClick={() => void load()} type="button">Повторити</button></div>}
      {success === null ? null : <div className="form-message form-message--success page-message" role="status"><Icon name="check" /><span>{success}</span></div>}
      <section className="panel supplier-directory">
        <header><div><p className="eyebrow">Post-MVP · TP-1001</p><h2>Постачальники</h2><p>Контакти й активні записи для нових складських надходжень.</p></div><button className="button button--primary" onClick={() => { setEditor({ mode: "create" }); setSuccess(null); }} type="button"><Icon name="plus" />Додати постачальника</button></header>
        <div className="supplier-toolbar"><label className="form-field"><span>Пошук</span><span className="input-with-icon"><Icon name="search" /><input onChange={(event) => { setSearch(event.target.value); }} placeholder="Назва, контакт, телефон або email" value={search} /></span></label><label className="form-field"><span>Статус</span><select onChange={(event) => { setStatus(event.target.value as SupplierStatus); }} value={status}><option value="all">Усі постачальники</option><option value="active">Активні</option><option value="inactive">Неактивні</option></select></label><button aria-label="Скинути фільтри постачальників" className="icon-button" disabled={!filtersActive} onClick={() => { setSearch(""); setStatus("all"); }} type="button"><Icon name="refresh" /></button></div>
        {isLoading ? <div className="inventory-empty"><span className="spinner" /><h3>Завантажуємо постачальників…</h3></div> : null}
        {!isLoading && visible.length === 0 ? <div className="inventory-empty"><Icon name="empty" /><h3>{suppliers.length === 0 ? "Постачальників ще немає" : "Постачальників не знайдено"}</h3><p>{suppliers.length === 0 ? "Створіть перший запис, щоб обирати його у надходженнях." : "Змініть пошук або скиньте фільтри."}</p>{suppliers.length === 0 ? <button className="button button--primary" onClick={() => { setEditor({ mode: "create" }); }} type="button">Створити постачальника</button> : <button className="button button--secondary" onClick={() => { setSearch(""); setStatus("all"); }} type="button">Скинути фільтри</button>}</div> : null}
        {!isLoading && visible.length > 0 ? <div className="supplier-table"><div aria-hidden="true" className="supplier-table__head"><span>Постачальник</span><span>Контакт</span><span>Зв’язок</span><span>Партії</span><span>Статус</span><span /></div>{visible.map((supplier) => <article className={`supplier-row${supplier.is_active ? "" : " supplier-row--inactive"}`} key={supplier.id}><span className="supplier-identity"><i>{supplierInitials(supplier.name)}</i><span><strong>{supplier.name}</strong><small>{displayOr(supplier.address, "Адресу не вказано")}</small></span></span><span data-label="Контакт">{displayOr(supplier.contact_name, "Не вказано")}</span><span data-label="Зв’язок"><strong>{displayOr(supplier.phone, "Телефон не вказано")}</strong><small>{displayOr(supplier.email, "Email не вказано")}</small></span><span data-label="Партії"><strong>{supplier.lots_count}</strong><small>історичних партій</small></span><span data-label="Статус"><b className={`supplier-status supplier-status--${supplier.is_active ? "active" : "inactive"}`}>{supplier.is_active ? "Активний" : "Неактивний"}</b></span><button aria-label={`Редагувати ${supplier.name}`} className="icon-button" onClick={() => { setEditor({ mode: "edit", supplier }); setSuccess(null); }} type="button"><Icon name="chevron" /></button></article>)}</div> : null}
      </section>
      {editor === null ? null : <SupplierEditorDialog editor={editor} onClose={() => { setEditor(null); }} onSaved={saved} />}
    </>
  );
}
