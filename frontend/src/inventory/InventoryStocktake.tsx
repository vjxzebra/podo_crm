import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders } from "../auth/AuthContext";

type Stocktake = components["schemas"]["Stocktake"];
type StocktakePreviewLot = components["schemas"]["StocktakePreviewLot"];
type StocktakeCreateRequest = components["schemas"]["StocktakeCreateRequest"];
type ErrorFields = Readonly<Record<string, readonly string[]>>;

interface StocktakeDialogProps {
  readonly initialMaterialId?: string;
  readonly onClose: () => void;
  readonly onPosted: (stocktake: Stocktake) => void;
}

function quantity(value: string, unit: string): string {
  return `${Number(value).toLocaleString("uk-UA", { maximumFractionDigits: 3 })} ${unit}`;
}

function signedQuantity(value: number, unit: string): string {
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toLocaleString("uk-UA", { maximumFractionDigits: 3 })} ${unit}`;
}

function moneyFromMinor(value: number): string {
  return new Intl.NumberFormat("uk-UA", { style: "currency", currency: "UAH" }).format(value / 100);
}

function lineError(fields: ErrorFields, index: number): string | null {
  return fields[`lines.${String(index)}.actual_quantity`]?.[0] ?? null;
}

export function StocktakeDialog({ initialMaterialId, onClose, onPosted }: StocktakeDialogProps) {
  const createKey = useRef(crypto.randomUUID());
  const postKey = useRef(crypto.randomUUID());
  const firstInput = useRef<HTMLInputElement>(null);
  const [lots, setLots] = useState<readonly StocktakePreviewLot[]>([]);
  const [actuals, setActuals] = useState<Readonly<Record<string, string>>>({});
  const [comment, setComment] = useState("");
  const [search, setSearch] = useState("");
  const [draft, setDraft] = useState<Stocktake | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<ErrorFields>({});
  const [confirmClose, setConfirmClose] = useState(false);

  const countedLots = useMemo(
    () => initialMaterialId === undefined
      ? lots
      : lots.filter((lot) => lot.material_id === initialMaterialId),
    [initialMaterialId, lots],
  );
  const visibleLots = useMemo(() => {
    const normalized = search.trim().toLocaleLowerCase("uk");
    if (normalized === "") return countedLots;
    return countedLots.filter((lot) => [lot.material_name, lot.material_sku, lot.lot_number]
      .some((value) => value.toLocaleLowerCase("uk").includes(normalized)));
  }, [countedLots, search]);
  const isDirty = comment !== "" || countedLots.some(
    (lot) => (actuals[lot.id] ?? lot.system_quantity) !== lot.system_quantity,
  );
  const requestClose = useCallback(() => {
    if (isSaving) return;
    if (isDirty || draft?.status === "DRAFT") {
      setConfirmClose(true);
      return;
    }
    onClose();
  }, [draft?.status, isDirty, isSaving, onClose]);

  useEffect(() => {
    let active = true;
    void apiClient.GET("/api/v1/inventory/stocktakes/preview").then((result) => {
      if (!active) return;
      if (result.data === undefined) {
        setError(result.error.message);
      } else {
        setLots(result.data.lots);
        setActuals(Object.fromEntries(result.data.lots.map((lot) => [lot.id, lot.system_quantity])));
        queueMicrotask(() => { firstInput.current?.focus(); });
      }
      setIsLoading(false);
    }).catch(() => {
      if (!active) return;
      setError("Немає зв’язку із сервером. Не вдалося завантажити залишки.");
      setIsLoading(false);
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") requestClose();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("keydown", closeOnEscape); };
  }, [requestClose]);

  const createDraft = async () => {
    const invalid = countedLots.some((lot) => {
      const value = Number(actuals[lot.id]);
      return actuals[lot.id] === "" || !Number.isFinite(value) || value < 0;
    });
    if (countedLots.length === 0 || invalid) {
      setError(countedLots.length === 0
        ? "Для цього підрахунку немає партій."
        : "Фактичний залишок кожної партії має бути числом від нуля.");
      return;
    }
    setIsSaving(true);
    setError(null);
    setFields({});
    const body: StocktakeCreateRequest = {
      comment,
      lines: countedLots.map((lot) => ({
        lot_id: lot.id,
        actual_quantity: actuals[lot.id] ?? lot.system_quantity,
      })),
    };
    const result = await apiClient.POST("/api/v1/inventory/stocktakes", {
      body,
      headers: csrfHeaders(),
      params: { header: { "Idempotency-Key": createKey.current } },
    }).catch(() => null);
    setIsSaving(false);
    if (result === null) {
      setError("Немає зв’язку із сервером. Повторіть дію — ключ чернетки збережено.");
    } else if (result.data === undefined) {
      setError(result.error.message);
      setFields(result.error.fields);
      if (result.error.code === "idempotency_payload_mismatch") {
        createKey.current = crypto.randomUUID();
      }
    } else {
      setDraft(result.data);
      setConfirmClose(false);
    }
  };

  const postDraft = async () => {
    if (draft === null) return;
    setIsSaving(true);
    setError(null);
    const result = await apiClient.POST("/api/v1/inventory/stocktakes/{stocktake_id}/post", {
      headers: csrfHeaders(),
      params: {
        header: { "Idempotency-Key": postKey.current },
        path: { stocktake_id: draft.id },
      },
    }).catch(() => null);
    setIsSaving(false);
    if (result === null) {
      setError("Немає зв’язку із сервером. Повторіть проведення — ключ операції збережено.");
    } else if (result.data === undefined) {
      setError(result.error.message);
      if (result.error.code === "stocktake_balance_changed") {
        setError("Залишки змінилися після підрахунку. Закрийте чернетку та створіть нову інвентаризацію.");
      }
    } else {
      onPosted(result.data);
    }
  };

  const previewSummary = useMemo(() => countedLots.reduce((summary, lot) => {
    const difference = Number(actuals[lot.id] ?? lot.system_quantity) - Number(lot.system_quantity);
    return {
      changed: summary.changed + Number(difference !== 0),
      surplus: summary.surplus + Number(difference > 0),
      shortage: summary.shortage + Number(difference < 0),
      valueMinor: summary.valueMinor + (lot.purchase_price_minor === null
        || lot.purchase_price_minor === undefined ? 0 : difference * lot.purchase_price_minor),
    };
  }, { changed: 0, surplus: 0, shortage: 0, valueMinor: 0 }), [actuals, countedLots]);

  return (
    <div className="modal-layer" onMouseDown={(event) => {
      if (event.currentTarget === event.target) requestClose();
    }} role="presentation">
      <section aria-labelledby="stocktake-title" aria-modal="true" className="modal-card stocktake-dialog" role="dialog">
        <header className="modal-card__header">
          <div><p className="eyebrow">Склад · Фізичний контроль</p><h2 id="stocktake-title">{draft === null ? "Нова інвентаризація" : `Інвентаризація ${draft.public_number}`}</h2><p>{draft === null ? "Звірте обліковий і фактичний залишок кожної партії." : "Чернетку зафіксовано й більше не можна редагувати."}</p></div>
          <button aria-label="Закрити інвентаризацію" className="icon-button" disabled={isSaving} onClick={requestClose} type="button"><Icon name="close" /></button>
        </header>
        {isLoading ? <div className="inventory-empty inventory-empty--compact" role="status"><span className="spinner" /><h3>Завантажуємо залишки…</h3></div> : null}
        {!isLoading && draft === null ? <>
          <div className="stocktake-toolbar"><label className="form-field"><span>Пошук у підрахунку</span><span className="input-with-icon"><Icon name="search" /><input onChange={(event) => { setSearch(event.target.value); }} placeholder="Матеріал, артикул або партія" value={search} /></span></label><label className="form-field"><span>Коментар</span><input maxLength={2000} onChange={(event) => { setComment(event.target.value); }} placeholder="Наприклад, щомісячний контроль" value={comment} /></label></div>
          <div className="stocktake-summary" aria-label="Попередній результат"><article><span>Партій</span><strong>{countedLots.length}</strong></article><article><span>Розбіжностей</span><strong>{previewSummary.changed}</strong></article><article className="stocktake-surplus"><span>Надлишок</span><strong>{previewSummary.surplus}</strong></article><article className="stocktake-shortage"><span>Нестача</span><strong>{previewSummary.shortage}</strong></article><article><span>Оцінка</span><strong>{moneyFromMinor(previewSummary.valueMinor)}</strong></article></div>
          {countedLots.length === 0 ? <div className="inventory-empty inventory-empty--compact"><Icon name="empty" /><h3>Партій ще немає</h3><p>Спершу проведіть надходження матеріалу.</p></div> : <div className="stocktake-table"><div className="stocktake-table__head" aria-hidden="true"><span>Матеріал / партія</span><span>Обліковий</span><span>Фактичний</span><span>Різниця</span><span>Оцінка</span></div>{visibleLots.map((lot, visibleIndex) => {
            const actual = actuals[lot.id] ?? lot.system_quantity;
            const difference = Number(actual) - Number(lot.system_quantity);
            const originalIndex = countedLots.findIndex((item) => item.id === lot.id);
            return <article className={`stocktake-row${difference > 0 ? " stocktake-row--surplus" : difference < 0 ? " stocktake-row--shortage" : ""}`} key={lot.id}><span data-label="Матеріал"><strong>{lot.material_name}</strong><small>ART {lot.material_sku} · партія №{lot.lot_number}{lot.is_expired ? " · прострочена" : ""}</small></span><span data-label="Обліковий"><strong>{quantity(lot.system_quantity, lot.material_unit)}</strong></span><label data-label="Фактичний"><span className="sr-only">Фактичний залишок, {lot.material_name}, партія {lot.lot_number}</span><input min="0" onChange={(event) => { setActuals((current) => ({ ...current, [lot.id]: event.target.value })); setError(null); }} ref={visibleIndex === 0 ? firstInput : undefined} required step="0.001" type="number" value={actual} />{lineError(fields, originalIndex) === null ? null : <small className="field-error">{lineError(fields, originalIndex)}</small>}</label><span data-label="Різниця"><b>{signedQuantity(difference, lot.material_unit)}</b><small>{difference > 0 ? "Надлишок" : difference < 0 ? "Нестача" : "Збігається"}</small></span><span data-label="Оцінка">{difference === 0 ? "—" : lot.purchase_price_minor == null ? "Без ціни" : moneyFromMinor(difference * lot.purchase_price_minor)}</span></article>;
          })}</div>}
        </> : null}
        {draft === null ? null : <div className="stocktake-confirmation"><div className="stocktake-lock-note"><Icon name="lock" /><span><strong>Підрахунок зафіксовано</strong><small>{draft.line_count} партій · {draft.adjusted_line_count} розбіжностей · створив(-ла) {draft.created_by_name}</small></span><b>Чернетка</b></div><div className="stocktake-table"><div className="stocktake-table__head" aria-hidden="true"><span>Матеріал / партія</span><span>Обліковий</span><span>Фактичний</span><span>Різниця</span><span>Оцінка</span></div>{draft.lines.map((line) => <article className={`stocktake-row stocktake-row--readonly${line.difference_kind === "SURPLUS" ? " stocktake-row--surplus" : line.difference_kind === "SHORTAGE" ? " stocktake-row--shortage" : ""}`} key={line.id}><span data-label="Матеріал"><strong>{line.material_name}</strong><small>ART {line.material_sku} · партія №{line.lot_number}</small></span><span data-label="Обліковий">{quantity(line.system_quantity, line.material_unit)}</span><span data-label="Фактичний">{quantity(line.actual_quantity, line.material_unit)}</span><span data-label="Різниця"><b>{signedQuantity(Number(line.difference), line.material_unit)}</b></span><span data-label="Оцінка">{line.adjustment_value_minor === null ? "Без ціни" : moneyFromMinor(line.adjustment_value_minor)}</span></article>)}</div><div className="stocktake-post-warning"><Icon name="warning" /><span><strong>Проведення змінить залишки</strong><small>Партії будуть повторно заблоковані й звірені. Проведену інвентаризацію не можна редагувати; виправлення — лише новою операцією.</small></span></div></div>}
        {error === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div>}
        {confirmClose ? <div className="patient-close-warning" role="alert"><span><strong>{draft === null ? "Є незбережений підрахунок" : "Чернетку ще не проведено"}</strong><small>{draft === null ? "Відкинути введені фактичні залишки?" : "Вона лишиться незмінною, але залишки складу не зміняться."}</small></span><div><button className="button button--secondary" onClick={() => { setConfirmClose(false); }} type="button">Продовжити</button><button className="button button--danger" onClick={onClose} type="button">Закрити</button></div></div> : null}
        <footer className="modal-card__footer inventory-operation-footer"><span><Icon name="lock" />Проведення створює лише append-only рухи.</span><div><button className="button button--secondary" disabled={isSaving} onClick={requestClose} type="button">Скасувати</button>{draft === null ? <button className="button button--primary" disabled={isLoading || isSaving || countedLots.length === 0} onClick={() => void createDraft()} type="button">{isSaving ? "Фіксуємо…" : "Зафіксувати підрахунок"}</button> : <button className="button button--primary" disabled={isSaving} onClick={() => void postDraft()} type="button">{isSaving ? "Проводимо…" : "Провести інвентаризацію"}</button>}</div></footer>
      </section>
    </div>
  );
}
