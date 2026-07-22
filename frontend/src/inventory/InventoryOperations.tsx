import { useCallback, useEffect, useMemo, useRef, useState, type SyntheticEvent } from "react";

import { apiClient } from "../api/client";
import type { components } from "../api/schema";
import { Icon } from "../app/Icon";
import { csrfHeaders } from "../auth/AuthContext";

type Material = components["schemas"]["Material"];
type MaterialLot = components["schemas"]["MaterialLot"];
type InventoryOperation = components["schemas"]["InventoryOperation"];
type ReceiptRequest = components["schemas"]["ReceiptCreateRequest"];
type ManualWriteoffRequest = components["schemas"]["ManualWriteoffCreateRequest"];
type ErrorFields = Readonly<Record<string, readonly string[]>>;

interface ReceiptLineForm {
  readonly key: string;
  readonly materialQuery: string;
  readonly materialId: string;
  readonly lotNumber: string;
  readonly expiresOn: string;
  readonly quantity: string;
  readonly purchasePrice: string;
  readonly supplierName: string;
  readonly allowExistingLot: boolean;
}

function newReceiptLine(): ReceiptLineForm {
  return {
    key: crypto.randomUUID(),
    materialQuery: "",
    materialId: "",
    lotNumber: "",
    expiresOn: "",
    quantity: "",
    purchasePrice: "",
    supplierName: "",
    allowExistingLot: false,
  };
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function fieldError(fields: ErrorFields, path: string): string | null {
  return fields[path]?.[0] ?? null;
}

function positive(value: string): boolean {
  return value !== "" && Number.isFinite(Number(value)) && Number(value) > 0;
}

interface ReceiptDialogProps {
  readonly materials: readonly Material[];
  readonly onClose: () => void;
  readonly onPosted: (operation: InventoryOperation) => void;
}

export function ReceiptDialog({ materials, onClose, onPosted }: ReceiptDialogProps) {
  const initialDate = useRef(today());
  const idempotencyKey = useRef(crypto.randomUUID());
  const firstInput = useRef<HTMLInputElement>(null);
  const [receivedOn, setReceivedOn] = useState(initialDate.current);
  const [comment, setComment] = useState("");
  const [lines, setLines] = useState<readonly ReceiptLineForm[]>([newReceiptLine()]);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<ErrorFields>({});
  const [confirmClose, setConfirmClose] = useState(false);

  const isDirty = receivedOn !== initialDate.current
    || comment !== ""
    || lines.length > 1
    || lines.some((line) => line.materialId !== ""
      || line.lotNumber !== ""
      || line.expiresOn !== ""
      || line.quantity !== ""
      || line.purchasePrice !== ""
      || line.supplierName !== ""
      || line.allowExistingLot);

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
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") requestClose(); };
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("keydown", closeOnEscape); };
  }, [requestClose]);

  const updateLine = (key: string, changes: Partial<ReceiptLineForm>) => {
    setLines((current) => current.map((line) => line.key === key ? { ...line, ...changes } : line));
    setError(null);
    setFields({});
    setConfirmClose(false);
  };

  const submit = async (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    const invalidIndex = lines.findIndex((line) => line.materialId === ""
      || line.lotNumber.trim() === ""
      || !positive(line.quantity)
      || (line.purchasePrice !== "" && Number(line.purchasePrice) < 0));
    if (invalidIndex >= 0) {
      setError(`Заповніть матеріал, партію та додатну кількість у рядку ${String(invalidIndex + 1)}.`);
      return;
    }
    setIsSaving(true);
    setError(null);
    setFields({});
    const body: ReceiptRequest = {
      received_on: receivedOn,
      comment,
      lines: lines.map((line) => ({
        material_id: line.materialId,
        lot_number: line.lotNumber,
        expires_on: line.expiresOn || null,
        quantity: line.quantity,
        purchase_price_minor: line.purchasePrice === ""
          ? null
          : Math.round(Number(line.purchasePrice) * 100),
        supplier_name: line.supplierName,
        allow_existing_lot: line.allowExistingLot,
      })),
    };
    const result = await apiClient.POST("/api/v1/inventory/receipts", {
      body,
      headers: csrfHeaders(),
      params: { header: { "Idempotency-Key": idempotencyKey.current } },
    }).catch(() => null);
    setIsSaving(false);
    if (result === null) {
      setError("Немає зв’язку із сервером. Повторіть submit — ключ операції збережено.");
    } else if (result.data === undefined) {
      setError(result.error.message);
      setFields(result.error.fields);
      if (result.error.code === "idempotency_payload_mismatch") {
        idempotencyKey.current = crypto.randomUUID();
      }
    } else {
      onPosted(result.data);
    }
  };

  return (
    <div className="modal-layer" onMouseDown={(event) => { if (event.currentTarget === event.target) requestClose(); }} role="presentation">
      <section aria-labelledby="receipt-title" aria-modal="true" className="modal-card inventory-operation-dialog" role="dialog">
        <header className="modal-card__header">
          <div><p className="eyebrow">Склад · TP-502</p><h2 id="receipt-title">Нове надходження</h2><p>Кожен рядок створить незмінний рух і оновить залишок партії.</p></div>
          <button aria-label="Закрити надходження" className="icon-button" disabled={isSaving} onClick={requestClose} type="button"><Icon name="close" /></button>
        </header>
        <form noValidate onSubmit={(event) => void submit(event)}>
          <div className="inventory-operation-body">
            <div className="inventory-operation-meta">
              <label className="form-field"><span>Дата надходження</span><input max={initialDate.current} onChange={(event) => { setReceivedOn(event.target.value); }} required type="date" value={receivedOn} /></label>
              <label className="form-field"><span>Коментар</span><input maxLength={2000} onChange={(event) => { setComment(event.target.value); }} placeholder="Необов’язково" value={comment} /></label>
            </div>
            <div className="receipt-lines-heading"><div><h3>Позиції надходження</h3><p>Матеріал і номер партії не можна повторювати в одному документі.</p></div><button className="button button--secondary" onClick={() => { setLines((current) => [...current, newReceiptLine()]); }} type="button"><Icon name="plus" />Додати рядок</button></div>
            <div className="receipt-lines">
              {lines.map((line, index) => {
                const query = line.materialQuery.trim().toLocaleLowerCase("uk");
                const options = materials.filter((material) => material.is_active && (
                  query === ""
                  || material.name.toLocaleLowerCase("uk").includes(query)
                  || material.sku.toLocaleLowerCase("uk").includes(query)
                  || material.id === line.materialId
                ));
                return <fieldset className="receipt-line" key={line.key}><legend>Позиція {index + 1}</legend><div className="receipt-line__title"><span>Рядок {index + 1}</span>{lines.length === 1 ? null : <button aria-label={`Видалити позицію ${String(index + 1)}`} className="icon-button" onClick={() => { setLines((current) => current.filter((item) => item.key !== line.key)); }} type="button"><Icon name="close" /></button>}</div><div className="receipt-line__grid"><label className="form-field receipt-line__search"><span>Пошук матеріалу</span><span className="input-with-icon"><Icon name="search" /><input aria-label={`Пошук матеріалу ${String(index + 1)}`} onChange={(event) => { updateLine(line.key, { materialQuery: event.target.value }); }} placeholder="Назва або артикул" ref={index === 0 ? firstInput : undefined} value={line.materialQuery} /></span></label><label className="form-field receipt-line__material"><span>Матеріал</span><select aria-label={`Матеріал ${String(index + 1)}`} onChange={(event) => { updateLine(line.key, { materialId: event.target.value }); }} required value={line.materialId}><option value="">Оберіть матеріал</option>{options.map((material) => <option key={material.id} value={material.id}>{material.sku} · {material.name} · {material.unit}</option>)}</select>{fieldError(fields, `lines.${String(index)}.material_id`) ? <small className="field-error">{fieldError(fields, `lines.${String(index)}.material_id`)}</small> : null}</label><label className="form-field"><span>Номер партії</span><input aria-label={`Номер партії ${String(index + 1)}`} maxLength={80} onChange={(event) => { updateLine(line.key, { lotNumber: event.target.value }); }} required value={line.lotNumber} />{fieldError(fields, `lines.${String(index)}.lot_number`) ? <small className="field-error">{fieldError(fields, `lines.${String(index)}.lot_number`)}</small> : null}</label><label className="form-field"><span>Строк придатності</span><input aria-label={`Строк придатності ${String(index + 1)}`} onChange={(event) => { updateLine(line.key, { expiresOn: event.target.value }); }} type="date" value={line.expiresOn} /></label><label className="form-field"><span>Кількість</span><input aria-label={`Кількість ${String(index + 1)}`} min="0.001" onChange={(event) => { updateLine(line.key, { quantity: event.target.value }); }} required step="0.001" type="number" value={line.quantity} />{fieldError(fields, `lines.${String(index)}.quantity`) ? <small className="field-error">{fieldError(fields, `lines.${String(index)}.quantity`)}</small> : null}</label><label className="form-field"><span>Ціна, грн/од.</span><input aria-label={`Ціна ${String(index + 1)}`} min="0" onChange={(event) => { updateLine(line.key, { purchasePrice: event.target.value }); }} step="0.01" type="number" value={line.purchasePrice} /></label><label className="form-field receipt-line__supplier"><span>Постачальник</span><input aria-label={`Постачальник ${String(index + 1)}`} maxLength={180} onChange={(event) => { updateLine(line.key, { supplierName: event.target.value }); }} placeholder="Необов’язково" value={line.supplierName} /></label><label className="toggle-field receipt-line__existing"><input checked={line.allowExistingLot} onChange={(event) => { updateLine(line.key, { allowExistingLot: event.target.checked }); }} type="checkbox" /><span /><strong>Поповнити наявну партію</strong><small>Підтверджуйте лише якщо строк, ціна й постачальник збігаються.</small></label></div></fieldset>;
              })}
            </div>
            {error === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div>}
            {confirmClose ? <div className="patient-close-warning" role="alert"><span><strong>Є незбережене надходження</strong><small>Відкинути всі позиції й закрити форму?</small></span><div><button className="button button--secondary" onClick={() => { setConfirmClose(false); }} type="button">Продовжити</button><button className="button button--danger" onClick={onClose} type="button">Відкинути</button></div></div> : null}
          </div>
          <footer className="modal-card__footer inventory-operation-footer"><span><Icon name="lock" />Повторний submit із тим самим ключем не дублює рухи.</span><div><button className="button button--secondary" disabled={isSaving} onClick={requestClose} type="button">Скасувати</button><button className="button button--primary" disabled={isSaving} type="submit">{isSaving ? "Проводимо…" : "Провести надходження"}</button></div></footer>
        </form>
      </section>
    </div>
  );
}

interface WriteoffDialogProps {
  readonly material: Material;
  readonly lots: readonly MaterialLot[];
  readonly onClose: () => void;
  readonly onPosted: (operation: InventoryOperation) => void;
}

export function WriteoffDialog({ material, lots, onClose, onPosted }: WriteoffDialogProps) {
  const availableLots = useMemo(() => lots.filter((lot) => Number(lot.current_quantity) > 0), [lots]);
  const initialLot = availableLots[0]?.id ?? "";
  const idempotencyKey = useRef(crypto.randomUUID());
  const quantityInput = useRef<HTMLInputElement>(null);
  const [lotId, setLotId] = useState(initialLot);
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState("");
  const [comment, setComment] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<ErrorFields>({});
  const [confirmClose, setConfirmClose] = useState(false);
  const selectedLot = availableLots.find((lot) => lot.id === lotId) ?? null;
  const isDirty = lotId !== initialLot || quantity !== "" || reason !== "" || comment !== "";

  const requestClose = useCallback(() => {
    if (isSaving) return;
    if (isDirty) {
      setConfirmClose(true);
      return;
    }
    onClose();
  }, [isDirty, isSaving, onClose]);

  useEffect(() => {
    quantityInput.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") requestClose(); };
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("keydown", closeOnEscape); };
  }, [requestClose]);

  const submit = async (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (selectedLot === null || !positive(quantity) || reason.trim() === "") {
      setError("Оберіть партію, введіть додатну кількість і причину списання.");
      return;
    }
    if (Number(quantity) > Number(selectedLot.current_quantity)) {
      setError(`Доступно лише ${Number(selectedLot.current_quantity).toLocaleString("uk-UA")} ${material.unit}`);
      return;
    }
    setIsSaving(true);
    setError(null);
    setFields({});
    const body: ManualWriteoffRequest = {
      reason,
      comment,
      lines: [{ lot_id: selectedLot.id, quantity }],
    };
    const result = await apiClient.POST("/api/v1/inventory/write-offs", {
      body,
      headers: csrfHeaders(),
      params: { header: { "Idempotency-Key": idempotencyKey.current } },
    }).catch(() => null);
    setIsSaving(false);
    if (result === null) {
      setError("Немає зв’язку із сервером. Повторіть submit — ключ операції збережено.");
    } else if (result.data === undefined) {
      setError(result.error.message);
      setFields(result.error.fields);
      if (result.error.code === "idempotency_payload_mismatch") {
        idempotencyKey.current = crypto.randomUUID();
      }
    } else {
      onPosted(result.data);
    }
  };

  return (
    <div className="modal-layer" onMouseDown={(event) => { if (event.currentTarget === event.target) requestClose(); }} role="presentation">
      <section aria-labelledby="writeoff-title" aria-modal="true" className="modal-card writeoff-dialog" role="dialog">
        <header className="modal-card__header"><div><p className="eyebrow">Склад · Ручна операція</p><h2 id="writeoff-title">Ручне списання</h2><p>{material.sku} · {material.name} · {material.unit}</p></div><button aria-label="Закрити списання" className="icon-button" disabled={isSaving} onClick={requestClose} type="button"><Icon name="close" /></button></header>
        <form noValidate onSubmit={(event) => void submit(event)}>
          <div className="inventory-operation-body writeoff-body">
            {availableLots.length === 0 ? <div className="inventory-empty inventory-empty--compact"><Icon name="empty" /><h3>Немає партій із залишком</h3><p>Списання неможливе, доки залишок дорівнює нулю.</p></div> : <><label className="form-field"><span>Партія</span><select onChange={(event) => { setLotId(event.target.value); setError(null); }} value={lotId}>{availableLots.map((lot) => <option key={lot.id} value={lot.id}>№{lot.lot_number} · {Number(lot.current_quantity).toLocaleString("uk-UA")} {material.unit}{lot.is_expired ? " · прострочена" : ""}</option>)}</select></label><div className="writeoff-availability"><span>Доступний залишок</span><strong>{selectedLot === null ? "0" : Number(selectedLot.current_quantity).toLocaleString("uk-UA")} {material.unit}</strong><small>{selectedLot?.is_expired ? "Прострочену партію можна списати для утилізації." : "Залишок перевіряється повторно під блокуванням під час submit."}</small></div><label className="form-field"><span>Кількість</span><input aria-describedby="writeoff-quantity-hint" aria-label="Кількість списання" max={selectedLot?.current_quantity} min="0.001" onChange={(event) => { setQuantity(event.target.value); setError(null); }} ref={quantityInput} required step="0.001" type="number" value={quantity} /><small id="writeoff-quantity-hint">Не більше поточного залишку партії.</small>{fieldError(fields, "lines.0.quantity") ? <small className="field-error">{fieldError(fields, "lines.0.quantity")}</small> : null}</label><label className="form-field"><span>Причина</span><select onChange={(event) => { setReason(event.target.value); setError(null); }} required value={reason}><option value="">Оберіть причину</option><option value="Прострочення">Прострочення</option><option value="Пошкодження">Пошкодження</option><option value="Утилізація">Утилізація</option><option value="Помилка зберігання">Помилка зберігання</option><option value="Інше">Інше</option></select></label><label className="form-field"><span>Коментар</span><textarea maxLength={2000} onChange={(event) => { setComment(event.target.value); }} placeholder="Деталі списання" rows={3} value={comment} /></label></>}
            {error === null ? null : <div className="form-message form-message--error" role="alert"><Icon name="warning" /><span>{error}</span></div>}
            {confirmClose ? <div className="patient-close-warning" role="alert"><span><strong>Є незбережене списання</strong><small>Відкинути введені дані?</small></span><div><button className="button button--secondary" onClick={() => { setConfirmClose(false); }} type="button">Продовжити</button><button className="button button--danger" onClick={onClose} type="button">Відкинути</button></div></div> : null}
          </div>
          <footer className="modal-card__footer inventory-operation-footer"><span><Icon name="lock" />Партія блокується, а проведений рух не редагується.</span><div><button className="button button--secondary" disabled={isSaving} onClick={requestClose} type="button">Скасувати</button><button className="button button--danger" disabled={isSaving || availableLots.length === 0} type="submit">{isSaving ? "Проводимо…" : "Підтвердити списання"}</button></div></footer>
        </form>
      </section>
    </div>
  );
}
