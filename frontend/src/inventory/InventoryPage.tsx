import { useCallback, useEffect, useMemo, useRef, useState, type SyntheticEvent } from "react";
import { useSearchParams } from "react-router";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders } from "../auth/AuthContext";
import { MovementJournal } from "./InventoryMovements";
import { ReceiptDialog, WriteoffDialog } from "./InventoryOperations";
import { StocktakeDialog } from "./InventoryStocktake";

type Material = components["schemas"]["Material"];
type MaterialLot = components["schemas"]["MaterialLot"];
type InventoryOperation = components["schemas"]["InventoryOperation"];
type StockStatus = components["schemas"]["StockStatusEnum"];
type ErrorFields = Readonly<Record<string, readonly string[]>>;

type EditorState =
  | { readonly mode: "create" }
  | { readonly mode: "edit"; readonly material: Material };

const statusLabels: Record<StockStatus, string> = {
  out_of_stock: "Немає в наявності",
  low: "Низький залишок",
  expired: "Є прострочена партія",
  expiring: "Закінчується термін",
  healthy: "В наявності",
};

const lotStatusLabels: Readonly<Record<string, string>> = {
  empty: "Вичерпана",
  expired: "Прострочена",
  expiring: "Термін спливає",
  usable: "Доступна",
};

function quantity(value: string | undefined, unit: string): string {
  return `${Number(value ?? 0).toLocaleString("uk-UA", { maximumFractionDigits: 3 })} ${unit}`;
}

function dateLabel(value: string | null | undefined): string {
  if (value == null) return "Без строку";
  return new Intl.DateTimeFormat("uk-UA", { day: "2-digit", month: "2-digit", year: "numeric" })
    .format(new Date(`${value}T12:00:00`));
}

function fieldMessage(fields: ErrorFields, name: string): string | null {
  return fields[name]?.[0] ?? null;
}

interface MaterialEditorDialogProps {
  readonly editor: EditorState;
  readonly onClose: () => void;
  readonly onSaved: (material: Material, message: string) => void;
}

function MaterialEditorDialog({ editor, onClose, onSaved }: MaterialEditorDialogProps) {
  const source = editor.mode === "edit" ? editor.material : null;
  const [sku, setSku] = useState(source?.sku ?? "");
  const [name, setName] = useState(source?.name ?? "");
  const [category, setCategory] = useState(source?.category ?? "");
  const [unit, setUnit] = useState(source?.unit ?? "шт.");
  const [minimumQuantity, setMinimumQuantity] = useState(source?.minimum_quantity ?? "0");
  const [isActive, setIsActive] = useState(source?.is_active ?? true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<ErrorFields>({});
  const [confirmClose, setConfirmClose] = useState(false);
  const firstInput = useRef<HTMLInputElement>(null);
  const isDirty = sku !== (source?.sku ?? "")
    || name !== (source?.name ?? "")
    || category !== (source?.category ?? "")
    || unit !== (source?.unit ?? "шт.")
    || minimumQuantity !== (source?.minimum_quantity ?? "0")
    || isActive !== (source?.is_active ?? true);
  const requestClose = useCallback(() => {
    if (isSaving) return;
    if (isDirty) {
      setConfirmClose(true);
      return;
    }
    onClose();
  }, [isDirty, isSaving, onClose]);

  useEffect(() => {
    firstInput.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") requestClose();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("keydown", closeOnEscape); };
  }, [requestClose]);

  const submit = async (event: SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    setFields({});
    const body = {
      sku,
      name,
      category,
      unit,
      minimum_quantity: minimumQuantity,
      is_active: isActive,
    };
    const result = editor.mode === "create"
      ? await apiClient.POST("/api/v1/inventory/materials", {
        body,
        headers: csrfHeaders(),
      }).catch(() => null)
      : await apiClient.PATCH("/api/v1/inventory/materials/{material_id}", {
        params: { path: { material_id: editor.material.id } },
        body: { ...body, version: editor.material.version ?? 1 },
        headers: csrfHeaders(),
      }).catch(() => null);
    if (result === null) {
      setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    } else if (result.data === undefined) {
      setError(result.error.message);
      setFields(result.error.fields);
    } else {
      onSaved(
        result.data,
        editor.mode === "create" ? "Матеріал додано до каталогу." : "Картку матеріалу оновлено.",
      );
    }
    setIsSaving(false);
  };

  const unitIsLocked = source !== null && source.lots_count > 0;
  return (
    <div className="modal-layer" role="presentation" onMouseDown={(event) => {
      if (event.currentTarget === event.target) requestClose();
    }}>
      <section aria-labelledby="material-editor-title" aria-modal="true" className="modal-card material-editor" role="dialog">
        <header className="modal-card__header">
          <div><p className="eyebrow">Склад · Картка матеріалу</p><h2 id="material-editor-title">{editor.mode === "create" ? "Новий матеріал" : "Редагувати матеріал"}</h2><p>Постачальник належить партії, а не окремому довіднику.</p></div>
          <button aria-label="Закрити" className="icon-button" disabled={isSaving} onClick={requestClose} type="button"><Icon name="close" /></button>
        </header>
        <form onSubmit={(event) => void submit(event)}>
          {error === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div>}
          <div className="material-editor__grid">
            <label className="form-field"><span>Артикул</span><input maxLength={48} onChange={(event) => { setSku(event.target.value); }} ref={firstInput} required value={sku} />{fieldMessage(fields, "sku") === null ? null : <small className="field-error">{fieldMessage(fields, "sku")}</small>}</label>
            <label className="form-field material-editor__wide"><span>Назва</span><input maxLength={180} onChange={(event) => { setName(event.target.value); }} required value={name} />{fieldMessage(fields, "name") === null ? null : <small className="field-error">{fieldMessage(fields, "name")}</small>}</label>
            <label className="form-field"><span>Категорія</span><input maxLength={100} onChange={(event) => { setCategory(event.target.value); }} required value={category} />{fieldMessage(fields, "category") === null ? null : <small className="field-error">{fieldMessage(fields, "category")}</small>}</label>
            <label className="form-field"><span>Одиниця виміру</span><input disabled={unitIsLocked} maxLength={24} onChange={(event) => { setUnit(event.target.value); }} required value={unit} />{unitIsLocked ? <small>Захищено після першої партії.</small> : null}{fieldMessage(fields, "unit") === null ? null : <small className="field-error">{fieldMessage(fields, "unit")}</small>}</label>
            <label className="form-field"><span>Мінімальний залишок</span><input min="0" onChange={(event) => { setMinimumQuantity(event.target.value); }} required step="0.001" type="number" value={minimumQuantity} />{fieldMessage(fields, "minimum_quantity") === null ? null : <small className="field-error">{fieldMessage(fields, "minimum_quantity")}</small>}</label>
            <label className="toggle-field material-editor__active"><input checked={isActive} onChange={(event) => { setIsActive(event.target.checked); }} type="checkbox" /><span /><strong>Активний матеріал</strong><small>Неактивний лишається в історії та партіях.</small></label>
          </div>
          {confirmClose ? <div className="patient-close-warning" role="alert"><span><strong>Є незбережені зміни</strong><small>Відкинути їх і закрити форму?</small></span><div><button className="button button--secondary" onClick={() => { setConfirmClose(false); }} type="button">Продовжити</button><button className="button button--danger" onClick={onClose} type="button">Відкинути</button></div></div> : null}
          <footer className="modal-card__footer"><button className="button button--secondary" disabled={isSaving} onClick={requestClose} type="button">Скасувати</button><button className="button button--primary" disabled={isSaving} type="submit">{isSaving ? "Зберігаємо…" : editor.mode === "create" ? "Створити матеріал" : "Зберегти зміни"}</button></footer>
        </form>
      </section>
    </div>
  );
}

interface MaterialDetailsDialogProps {
  readonly material: Material;
  readonly lots: readonly MaterialLot[];
  readonly onClose: () => void;
  readonly onEdit: (material: Material) => void;
  readonly onStocktake: (material: Material) => void;
  readonly onWriteoff: (material: Material, lots: readonly MaterialLot[]) => void;
}

function MaterialDetailsDialog({ material, lots, onClose, onEdit, onStocktake, onWriteoff }: MaterialDetailsDialogProps) {
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeButton.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("keydown", closeOnEscape); };
  }, [onClose]);

  return (
    <div className="modal-layer" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }}>
      <section aria-labelledby="material-details-title" aria-modal="true" className="modal-card material-details" role="dialog">
        <header className="modal-card__header material-details__header">
          <div className="material-details__identity"><span className="inventory-monogram">{material.name.slice(0, 1).toLocaleUpperCase("uk")}</span><span><p className="eyebrow">ART {material.sku}</p><h2 id="material-details-title">{material.name}</h2><p>{material.category} · {material.unit}</p></span></div>
          <div><span className={`inventory-status inventory-status--${material.stock_status}`}>{statusLabels[material.stock_status]}</span><button aria-label="Закрити" className="icon-button" onClick={onClose} ref={closeButton} type="button"><Icon name="close" /></button></div>
        </header>
        <div className="material-summary-grid">
          <article><span>Загальний залишок</span><strong>{quantity(material.total_quantity, material.unit)}</strong><small>Разом у всіх партіях</small></article>
          <article><span>Доступно для прийому</span><strong>{quantity(material.available_quantity, material.unit)}</strong><small>Без прострочених партій</small></article>
          <article><span>Мінімальний запас</span><strong>{quantity(material.minimum_quantity, material.unit)}</strong><small>Поріг попередження</small></article>
          <article><span>Найближчий термін</span><strong>{dateLabel(material.nearest_expiry)}</strong><small>Серед доступних партій</small></article>
        </div>
        <section className="material-lots" aria-labelledby="material-lots-title">
          <header><div><h3 id="material-lots-title">Партії та терміни</h3><p>FEFO рекомендує першою партію з найближчим придатним строком.</p></div><span>{lots.length} партій</span></header>
          {lots.length === 0 ? <div className="inventory-empty inventory-empty--compact"><Icon name="empty" /><h3>Партій ще немає</h3><p>Проведіть перше надходження, щоб створити партію.</p></div> : (
            <div className="lot-table">
              <div className="lot-table__head" aria-hidden="true"><span>Партія</span><span>Надійшла</span><span>Залишок</span><span>Термін</span><span>Постачальник</span><span>Стан</span></div>
              {lots.map((lot) => <article className={`lot-row${lot.is_usable ? "" : " lot-row--unusable"}`} key={lot.id}><span data-label="Партія"><strong>№{lot.lot_number}</strong><small>{lot.fefo_rank === null ? "Не пропонується" : lot.fefo_rank === 1 ? "FEFO · першою" : `FEFO · ${String(lot.fefo_rank)}`}</small></span><span data-label="Надійшла">{dateLabel(lot.received_on)}</span><span data-label="Залишок"><strong>{quantity(lot.current_quantity, material.unit)}</strong><small>з {quantity(lot.initial_quantity, material.unit)}</small></span><span data-label="Термін">{dateLabel(lot.expires_on)}</span><span data-label="Постачальник">{lot.supplier_name === "" ? "Не вказано" : lot.supplier_name}</span><span data-label="Стан"><b className={`lot-status lot-status--${lot.status}`}>{lotStatusLabels[lot.status] ?? lot.status}</b></span></article>)}
            </div>
          )}
        </section>
        <footer className="modal-card__footer material-details__footer"><span><Icon name="lock" />Проведені рухи незмінні; залишок оновлює лише операція.</span><div><button className="button button--secondary" disabled={lots.length === 0} onClick={() => { onStocktake(material); }} type="button">Перерахувати</button><button className="button button--danger" disabled={!lots.some((lot) => Number(lot.current_quantity) > 0)} onClick={() => { onWriteoff(material, lots); }} type="button">Ручне списання</button><button className="button button--primary" onClick={() => { onEdit(material); }} type="button">Редагувати картку</button></div></footer>
      </section>
    </div>
  );
}

export function InventoryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [view, setView] = useState<"catalog" | "movements">("catalog");
  const [materials, setMaterials] = useState<readonly Material[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [stockStatus, setStockStatus] = useState<"all" | StockStatus>("all");
  const [catalogStatus, setCatalogStatus] = useState<"all" | "active" | "inactive">("all");
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [details, setDetails] = useState<{ readonly material: Material; readonly lots: readonly MaterialLot[] } | null>(null);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [receiptOpen, setReceiptOpen] = useState(false);
  const [stocktakeScope, setStocktakeScope] = useState<string | null>(null);
  const [stocktakeOpen, setStocktakeOpen] = useState(false);
  const [writeoff, setWriteoff] = useState<{ readonly material: Material; readonly lots: readonly MaterialLot[] } | null>(null);
  const detailRequestSequence = useRef(0);
  const detailTriggerRef = useRef<HTMLButtonElement | null>(null);

  const loadMaterials = async () => {
    setIsLoading(true);
    setError(null);
    const result = await apiClient.GET("/api/v1/inventory/materials").catch(() => null);
    if (result === null) setError("Немає зв’язку із сервером. Спробуйте ще раз.");
    else if (result.data === undefined) setError(result.error.message);
    else setMaterials(result.data.materials);
    setIsLoading(false);
  };

  useEffect(() => { void loadMaterials(); }, []);

  const categories = useMemo(() => [...new Set(materials.map((item) => item.category))].sort((left, right) => left.localeCompare(right, "uk")), [materials]);
  const visible = useMemo(() => {
    const normalized = search.trim().toLocaleLowerCase("uk");
    return materials.filter((item) => {
      const matchesSearch = normalized === "" || item.name.toLocaleLowerCase("uk").includes(normalized) || item.sku.toLocaleLowerCase("uk").includes(normalized);
      const matchesCategory = category === "all" || item.category === category;
      const matchesStock = stockStatus === "all" || item.stock_status === stockStatus;
      const matchesCatalog = catalogStatus === "all" || (catalogStatus === "active" ? item.is_active : !item.is_active);
      return matchesSearch && matchesCategory && matchesStock && matchesCatalog;
    });
  }, [catalogStatus, category, materials, search, stockStatus]);

  const loadDetails = useCallback(async (materialId: string) => {
    const sequence = detailRequestSequence.current + 1;
    detailRequestSequence.current = sequence;
    setIsLoadingDetails(true);
    setDetailError(null);
    setDetails(null);
    const [detailResult, lotsResult] = await Promise.all([
      apiClient.GET("/api/v1/inventory/materials/{material_id}", { params: { path: { material_id: materialId } } }).catch(() => null),
      apiClient.GET("/api/v1/inventory/materials/{material_id}/lots", { params: { path: { material_id: materialId } } }).catch(() => null),
    ]);
    if (sequence !== detailRequestSequence.current) return;
    if (detailResult === null || lotsResult === null) setDetailError("Немає зв’язку із сервером. Не вдалося відкрити матеріал.");
    else if (detailResult.data === undefined || lotsResult.data === undefined) setDetailError("Матеріал не знайдено або він недоступний у межах вашої ролі.");
    else setDetails({ material: detailResult.data, lots: lotsResult.data.lots });
    setIsLoadingDetails(false);
  }, []);

  const requestedMaterialId = searchParams.get("material");
  useEffect(() => {
    if (requestedMaterialId === null) return;
    setView("catalog");
    void loadDetails(requestedMaterialId);
    return () => { detailRequestSequence.current += 1; };
  }, [loadDetails, requestedMaterialId]);

  const openDetails = (materialId: string, trigger: HTMLButtonElement) => {
    detailTriggerRef.current = trigger;
    const next = new URLSearchParams(searchParams);
    next.set("material", materialId);
    setSearchParams(next);
  };
  const closeDetails = (restoreFocus = true) => {
    detailRequestSequence.current += 1;
    setDetails(null);
    setDetailError(null);
    setIsLoadingDetails(false);
    const next = new URLSearchParams(searchParams);
    next.delete("material");
    setSearchParams(next, { replace: true });
    if (restoreFocus) window.setTimeout(() => { detailTriggerRef.current?.focus(); }, 0);
  };

  const replaceMaterial = (material: Material, message: string) => {
    setMaterials((current) => {
      const found = current.some((item) => item.id === material.id);
      const next = found ? current.map((item) => item.id === material.id ? material : item) : [...current, material];
      return [...next].sort((left, right) => Number(right.is_active) - Number(left.is_active) || left.name.localeCompare(right.name, "uk"));
    });
    setEditor(null);
    setDetails(null);
    setSuccess(message);
    setError(null);
  };

  const filtersActive = search !== "" || category !== "all" || stockStatus !== "all" || catalogStatus !== "all";
  const attentionCount = materials.filter((item) => item.stock_status !== "healthy").length;
  const expiringCount = materials.filter((item) => item.stock_status === "expiring" || item.stock_status === "expired").length;
  const clearFilters = () => { setSearch(""); setCategory("all"); setStockStatus("all"); setCatalogStatus("all"); };
  const operationPosted = (operation: InventoryOperation, label: string) => {
    setReceiptOpen(false);
    setWriteoff(null);
    setDetails(null);
    setSuccess(`${label} · ${operation.public_number}. Залишки оновлено.`);
    setError(null);
    void loadMaterials();
  };

  return (
    <>
      <header className="page-heading inventory-heading"><div><p className="eyebrow">Облік матеріалів · TP-503</p><h1>Склад і матеріали</h1><p>Партійні залишки, фізична інвентаризація та append-only журнал рухів.</p></div><div><span className="admin-only-badge"><Icon name="lock" />Тільки адміністратор</span><button className="button button--secondary" onClick={() => { setEditor({ mode: "create" }); setSuccess(null); }} type="button"><Icon name="plus" />Додати матеріал</button><button className="button button--secondary" onClick={() => { setStocktakeScope(null); setStocktakeOpen(true); setSuccess(null); }} type="button">Інвентаризація</button><button className="button button--primary" onClick={() => { setReceiptOpen(true); setSuccess(null); }} type="button"><Icon name="plus" />Нове надходження</button></div></header>
      {error === null ? null : <div className="form-message form-message--error page-message" role="alert"><Icon name="warning" /><span>{error}</span><button className="text-action" onClick={() => void loadMaterials()} type="button">Повторити</button></div>}
      {success === null ? null : <div className="form-message form-message--success page-message" role="status"><Icon name="check" /><span>{success}</span></div>}
      <nav aria-label="Розділи складу" className="inventory-section-nav"><button aria-current={view === "catalog" ? "page" : undefined} className={view === "catalog" ? "active" : ""} onClick={() => { setView("catalog"); }} type="button">Каталог і залишки</button><button aria-current={view === "movements" ? "page" : undefined} className={view === "movements" ? "active" : ""} onClick={() => { setView("movements"); }} type="button">Журнал рухів</button></nav>
      {view === "catalog" ? <><section className="inventory-stats" aria-label="Зведення складу"><article className="panel"><span>Найменувань</span><strong>{materials.length}</strong><small>{materials.filter((item) => item.is_active).length} активних</small></article><article className="panel"><span>Потребують уваги</span><strong>{attentionCount}</strong><small>Низькі, відсутні або прострочені</small></article><article className="panel"><span>Контроль термінів</span><strong>{expiringCount}</strong><small>Спливають або вже минули</small></article><article className="panel"><span>Партій</span><strong>{materials.reduce((total, item) => total + item.lots_count, 0)}</strong><small>Залишки змінюють лише проведені операції</small></article></section>
      <section className="panel inventory-catalog">
        <header><div><p className="eyebrow">Каталог</p><h2>Залишки матеріалів</h2><p>Доступний залишок не включає прострочені партії.</p></div></header>
        <div className="inventory-toolbar"><label className="form-field inventory-search"><span>Пошук</span><span className="input-with-icon"><Icon name="search" /><input onChange={(event) => { setSearch(event.target.value); }} placeholder="Назва або артикул" value={search} /></span></label><label className="form-field"><span>Категорія</span><select onChange={(event) => { setCategory(event.target.value); }} value={category}><option value="all">Усі категорії</option>{categories.map((item) => <option key={item} value={item}>{item}</option>)}</select></label><label className="form-field"><span>Стан запасу</span><select onChange={(event) => { setStockStatus(event.target.value as "all" | StockStatus); }} value={stockStatus}><option value="all">Усі стани</option>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="form-field"><span>Картка</span><select onChange={(event) => { setCatalogStatus(event.target.value as typeof catalogStatus); }} value={catalogStatus}><option value="all">Усі картки</option><option value="active">Активні</option><option value="inactive">Неактивні</option></select></label><button aria-label="Скинути фільтри" className="icon-button" disabled={!filtersActive} onClick={clearFilters} type="button"><Icon name="refresh" /></button></div>
        {isLoading ? <div className="inventory-empty"><span className="spinner" /><h3>Завантажуємо склад…</h3></div> : null}
        {!isLoading && visible.length === 0 ? <div className="inventory-empty"><Icon name="empty" /><h3>{materials.length === 0 ? "Матеріалів ще немає" : "Матеріалів не знайдено"}</h3><p>{materials.length === 0 ? "Створіть першу картку матеріалу; партії з’являться після надходження." : "Змініть пошук або скиньте фільтри."}</p>{materials.length === 0 ? <button className="button button--primary" onClick={() => { setEditor({ mode: "create" }); }} type="button">Створити матеріал</button> : <button className="button button--secondary" onClick={clearFilters} type="button">Скинути фільтри</button>}</div> : null}
        {!isLoading && visible.length > 0 ? <div className="inventory-table"><div className="inventory-table__head" aria-hidden="true"><span>Матеріал</span><span>Категорія</span><span>Доступно</span><span>Мінімум</span><span>Найближчий термін</span><span>Стан</span><span /></div>{visible.map((material) => <button aria-label={`Відкрити ${material.name}`} className={`inventory-row${material.is_active ? "" : " inventory-row--inactive"}`} key={material.id} onClick={(event) => { openDetails(material.id, event.currentTarget); }} type="button"><span className="inventory-identity"><i className="inventory-monogram">{material.name.slice(0, 1).toLocaleUpperCase("uk")}</i><span><strong>{material.name}</strong><small>ART {material.sku} · {material.unit}</small></span></span><span data-label="Категорія">{material.category}</span><span data-label="Доступно"><strong>{quantity(material.available_quantity, material.unit)}</strong><small>усього {quantity(material.total_quantity, material.unit)}</small></span><span data-label="Мінімум">{quantity(material.minimum_quantity, material.unit)}</span><span data-label="Термін">{dateLabel(material.nearest_expiry)}</span><span data-label="Стан"><b className={`inventory-status inventory-status--${material.stock_status}`}>{statusLabels[material.stock_status]}</b>{material.is_active ? null : <small>Неактивна картка</small>}</span><Icon name="chevron" /></button>)}</div> : null}
      </section></> : <MovementJournal materials={materials} />}
      {isLoadingDetails ? <div className="inventory-detail-loading" role="status"><span className="spinner" />Відкриваємо матеріал…</div> : null}
      {detailError === null ? null : <div className="inventory-detail-loading inventory-detail-loading--error" role="alert"><Icon name="warning" /><span>{detailError}</span><button className="button button--secondary" onClick={() => { if (requestedMaterialId !== null) void loadDetails(requestedMaterialId); }} type="button">Повторити</button><button className="button button--secondary" onClick={() => { closeDetails(); }} type="button">Закрити</button></div>}
      {editor === null ? null : <MaterialEditorDialog editor={editor} onClose={() => { setEditor(null); }} onSaved={replaceMaterial} />}
      {details === null ? null : <MaterialDetailsDialog material={details.material} lots={details.lots} onClose={() => { closeDetails(); }} onEdit={(material) => { closeDetails(false); setEditor({ mode: "edit", material }); }} onStocktake={(material) => { closeDetails(false); setStocktakeScope(material.id); setStocktakeOpen(true); }} onWriteoff={(material, lots) => { closeDetails(false); setWriteoff({ material, lots }); }} />}
      {receiptOpen ? <ReceiptDialog materials={materials} onClose={() => { setReceiptOpen(false); }} onPosted={(operation) => { operationPosted(operation, operation.replayed ? "Надходження вже було проведено" : "Надходження проведено"); }} /> : null}
      {writeoff === null ? null : <WriteoffDialog lots={writeoff.lots} material={writeoff.material} onClose={() => { setWriteoff(null); }} onPosted={(operation) => { operationPosted(operation, operation.replayed ? "Списання вже було проведено" : "Списання проведено"); }} />}
      {stocktakeOpen ? <StocktakeDialog {...(stocktakeScope === null ? {} : { initialMaterialId: stocktakeScope })} onClose={() => { setStocktakeOpen(false); setStocktakeScope(null); }} onPosted={(stocktake) => { setStocktakeOpen(false); setStocktakeScope(null); setSuccess(`${stocktake.replayed ? "Інвентаризацію вже було проведено" : "Інвентаризацію проведено"} · ${stocktake.public_number}. Залишки звірено.`); setError(null); void loadMaterials(); }} /> : null}
    </>
  );
}
